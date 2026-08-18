"""Bundle all generated products into a single GeoPackage.

GDAL 3.2's GPKG driver only names raster layers after the output
filename (no -nln / LAYER_NAME support) and cannot append a second raster
coverage to an existing package (APPEND_SUBDATASET re-uses the basename
and collides). So each raster is first translated into its own temporary
``{layer_name}.gpkg`` — which names the layer correctly — and the layers
are then merged into the bundle with plain SQL: the tile/coverage table
plus the ``gpkg_contents`` / ``gpkg_tile_matrix`` / ``gpkg_extensions``
and coverage-extension metadata rows. Vectors are appended afterwards
with OGR CopyLayer in update mode. HTML/JSON deliverables are skipped —
the bundle is for data interchange, not for the viewer and report.
"""

from __future__ import annotations

import os
import shutil
import sqlite3
import tempfile

from osgeo import gdal, ogr

_SKIPPED_EXTENSIONS = (".html", ".htm", ".json")
_RASTER_EXTENSIONS = (".tif", ".tiff", ".vrt")
_VECTOR_EXTENSIONS = (".gpkg", ".shp", ".geojson", ".tab", ".sqlite")

# GPKG metadata tables whose rows reference a layer by name (the row is
# rewritten with the bundled layer name when merged). The third name column
# keys the gridded-coverage ancillary rows to their raster layer.
_METADATA_TABLES = (
    "gpkg_contents",
    "gpkg_tile_matrix",
    "gpkg_tile_matrix_set",
    "gpkg_extensions",
    "gpkg_2d_gridded_coverage_ancillary",
    "gpkg_2d_gridded_tile_ancillary",
)

_NAME_COLUMNS = ("table_name", "tpudt_name", "tile_matrix_set_name")


def _layer_name(path):
    """Sanitised basename (no extension, letters/digits/underscore)."""
    name = os.path.splitext(os.path.basename(path))[0]
    cleaned = "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in name)
    cleaned = cleaned.strip("_") or "layer"
    return cleaned[:60]


def _unique_name(source_name, existing):
    name, counter = source_name, 1
    while name.lower() in existing:
        name = f"{source_name[:56]}_{counter}"
        counter += 1
    return name


def _merge_raster_layer(raster_gpkg, layer_name, bundle_path, log=None):
    """Copy one raster layer from ``raster_gpkg`` into ``bundle_path`` via SQL.

    Copies the tile/coverage table and every metadata row referencing the
    layer, rewriting the reference to ``layer_name``. Every statement is
    qualified with ``main.``/``src.`` — unqualified names resolve against the
    attached database and the gridded-coverage ancillary tables of two
    rasters collide on their shared ``id`` sequence, so ids are re-assigned.
    Returns True on success.

    The identifiers interpolated below are never user-controlled: layer_name
    passes _layer_name() (alnum/underscore only), tables come from the fixed
    _METADATA_TABLES tuple and column names from PRAGMA introspection of
    those tables.  # nosec B608
    """

    db = sqlite3.connect(bundle_path)
    try:
        db.execute('ATTACH DATABASE ? AS src', (raster_gpkg,))
        # One explicit transaction for everything below: the tile-table
        # CREATE would otherwise autocommit while the metadata inserts run
        # in an implicit transaction, and a mid-merge failure would leave
        # orphaned tile tables behind.
        db.execute("BEGIN")
        db.execute(
            f'CREATE TABLE "main"."{layer_name}" AS SELECT * FROM src."{layer_name}"'  # nosec B608
        )
        for table in _METADATA_TABLES:
            src_columns = [
                row[1] for row in db.execute(f'PRAGMA src.table_info("{table}")').fetchall()
            ]
            if not src_columns:
                continue  # table absent in this source (e.g. no coverage extension)
            name_column = next((c for c in src_columns if c in _NAME_COLUMNS), None)
            if name_column is None:
                continue
            rows = db.execute(
                f'SELECT * FROM src."{table}" WHERE "{name_column}" = ?',  # nosec B608
                (layer_name,),
            ).fetchall()
            if not rows:
                continue
            main_columns = [
                row[1] for row in db.execute(f'PRAGMA main.table_info("{table}")').fetchall()
            ]
            if not main_columns:
                db.execute(
                    f'CREATE TABLE "main"."{table}" AS SELECT * FROM src."{table}" WHERE 0'  # nosec B608
                )
                main_columns = src_columns
            insert_columns = [c for c in main_columns if c != "id"]
            column_list = ", ".join(f'"{c}"' for c in insert_columns)
            placeholders = ", ".join("?" for _ in insert_columns)
            for row in rows:
                values = list(row)
                values[src_columns.index(name_column)] = layer_name
                if "id" in src_columns:
                    del values[src_columns.index("id")]
                db.execute(
                    f'INSERT INTO "main"."{table}" ({column_list}) VALUES ({placeholders})',  # nosec B608
                    values,
                )
        db.commit()
        try:
            db.execute("DETACH DATABASE src")
        except sqlite3.Error:
            pass  # the connection close below releases the schema anyway
        return True
    except sqlite3.Error as err:
        if log is not None:
            log(f"Bundle: SQL merge failed for {layer_name} ({err})")
        db.rollback()
        return False
    finally:
        db.close()


def create_bundle(output_paths, bundle_path, feedback=None):
    """Copy every raster/vector output into one GeoPackage.

    ``output_paths`` maps product keys to file paths; ``bundle_path`` is the
    destination .gpkg. Returns the list of ``(key, layer_name, kind)``
    tuples written. Missing or unsupported files are skipped, not fatal.
    """

    def log(message):
        if feedback is not None and hasattr(feedback, "pushInfo"):
            feedback.pushInfo(message)

    if os.path.exists(bundle_path):
        os.remove(bundle_path)

    existing = set()
    written = []

    raster_sources = []
    vector_sources = []
    for key, source in sorted(output_paths.items()):
        if not source:
            continue
        path = str(source)
        if not os.path.exists(path):
            continue
        ext = os.path.splitext(path)[1].lower()
        if ext in _SKIPPED_EXTENSIONS:
            continue
        if ext in _RASTER_EXTENSIONS:
            raster_sources.append((key, path))
        elif ext in _VECTOR_EXTENSIONS:
            vector_sources.append((key, path))

    # Rasters: one temporary GPKG per layer (names the layer after the
    # file), merged into the bundle in SQL order.
    with tempfile.TemporaryDirectory(prefix="terrain_bundle_") as scratch:
        for key, path in raster_sources:
            ds = gdal.Open(path, gdal.GA_ReadOnly)
            if ds is None:
                log(f"Bundle: skipped unreadable raster {path}")
                continue
            name = _unique_name(_layer_name(path), existing)
            raster_gpkg = os.path.join(scratch, f"{name}.gpkg")
            options = gdal.TranslateOptions(
                format="GPKG",
                creationOptions=["TILE_FORMAT=PNG"],
            )
            copied = gdal.Translate(raster_gpkg, ds, options=options)
            ds = None
            if copied is None:
                log(f"Bundle: failed to embed raster {path}")
                continue
            copied = None

            if not os.path.exists(bundle_path):
                shutil.copyfile(raster_gpkg, bundle_path)
            elif not _merge_raster_layer(raster_gpkg, name, bundle_path, log):
                log(f"Bundle: failed to merge raster {name}")
                continue
            existing.add(name.lower())
            written.append((key, name, "raster"))
            log(f"Bundle: {name} (raster)")

    if not vector_sources:
        if os.path.exists(bundle_path) and not written:
            os.remove(bundle_path)
        return written

    # Vectors appended in update mode against the package built above.
    driver = ogr.GetDriverByName("GPKG")
    vector_target = driver.Open(bundle_path, 1)
    if vector_target is None:
        log(f"Bundle: could not open {bundle_path} for vector layers")
        return written
    for key, path in vector_sources:
        src = ogr.Open(path, 0)
        if src is None:
            log(f"Bundle: skipped unreadable vector {path}")
            continue
        try:
            for layer_index in range(src.GetLayerCount()):
                layer = src.GetLayer(layer_index)
                if layer is None:
                    continue
                name = _unique_name(_layer_name(path), existing)
                if vector_target.CopyLayer(layer, name) is None:
                    log(f"Bundle: failed to copy layer from {path}")
                    continue
                existing.add(name.lower())
                written.append((key, name, "vector"))
                log(f"Bundle: {name} (vector)")
        except Exception as err:
            log(f"Bundle: skipped {path} ({err})")
        finally:
            src = None
    vector_target.SyncToDisk()
    vector_target = None

    if not written and os.path.exists(bundle_path):
        os.remove(bundle_path)
    return written
