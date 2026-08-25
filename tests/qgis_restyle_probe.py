"""Runtime probe: restyle applies styles without re-running the pipeline.

Execute with the Python bundled inside QGIS:

    /Applications/QGIS.app/Contents/MacOS/QGIS --nocrashdialog \
        --headless --noplugins python3 tests/qgis_restyle_probe.py

Asserts:
- add_terrain_results + restyle_outputs leave exactly one package group
- a different palette changes the DEM renderer XML
- QML style packs are overwritten in place (no numbered siblings)
- layout style overrides can be applied to a plugin layout
"""

from __future__ import annotations

import json
import math
import os
import struct
import sys
import tempfile

WORKSPACE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, WORKSPACE)

from osgeo import gdal, ogr, osr  # noqa: E402


def make_dem(folder, name="dem.tif", size=48, res=10.0):
    path = os.path.join(folder, name)
    driver = gdal.GetDriverByName("GTiff")
    ds = driver.Create(path, size, size, 1, gdal.GDT_Float32)
    ds.SetGeoTransform((500000.0, res, 0.0, 2450000.0, 0.0, -res))
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(32648)
    ds.SetProjection(srs.ExportToWkt())
    band = ds.GetRasterBand(1)
    for row in range(size):
        scan = [
            100.0 * math.sin(math.pi * col / float(size)) + 20.0 * row / float(size) + 80.0
            for col in range(size)
        ]
        band.WriteRaster(0, row, size, 1, struct.pack("<%df" % size, *scan))
    band.FlushCache()
    ds = None
    return path


def make_contours(folder, name="contours.gpkg"):
    path = os.path.join(folder, name)
    driver = ogr.GetDriverByName("GPKG")
    ds = driver.CreateDataSource(path)
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(32648)
    layer = ds.CreateLayer("contours", srs, ogr.wkbLineString)
    layer.CreateField(ogr.FieldDefn("ELEV", ogr.OFTReal))
    for index, elev in enumerate(range(100, 200, 10)):
        feat = ogr.Feature(layer.GetLayerDefn())
        geom = ogr.Geometry(ogr.wkbLineString)
        geom.AddPoint_2D(500100.0, 2450000.0 - index * 30.0)
        geom.AddPoint_2D(500800.0, 2450000.0 - index * 30.0)
        feat.SetGeometry(geom)
        feat.SetField("ELEV", elev)
        layer.CreateFeature(feat)
    ds = None
    return path


def layer_style_xml(layer):
    from qgis.core import QgsMapLayerStyle

    style = QgsMapLayerStyle()
    style.readFromLayer(layer)
    return style.xmlData() or ""


def main():
    from qgis.core import QgsApplication

    prefix = os.environ.get("QGIS_PREFIX_PATH", "")
    if prefix:
        QgsApplication.setPrefixPath(prefix, True)
    application = QgsApplication([], False)
    application.initQgis()

    from qgis.core import (  # noqa: E402
        QgsLayoutItemMap,
        QgsLayoutSize,
        QgsPrintLayout,
        QgsProject,
    )
    from terrain_product_studio.core.layers import add_terrain_results  # noqa: E402
    from terrain_product_studio.core.restyle import (  # noqa: E402
        parse_run_manifest,
        restyle_outputs,
    )

    failures = []
    project = QgsProject.instance()
    with tempfile.TemporaryDirectory() as folder:
        dem = make_dem(folder)
        contours = make_contours(folder)
        results = {
            "WORKING_DEM": dem,
            "CONTOURS": contours,
        }
        report_path = os.path.join(folder, "terrain_report.json")
        with open(report_path, "w", encoding="utf-8") as stream:
            json.dump(
                {
                    "contour_interval": 10.0,
                    "index_contour_interval": 50.0,
                    "elevation_unit": "m",
                    "scene3d": {"texture_size": 3072, "basemap": "none"},
                    "outputs": {"WORKING_DEM": dem, "CONTOURS": contours},
                },
                stream,
            )
        plan = parse_run_manifest(report_path)
        if plan is None:
            failures.append("parse_run_manifest returned None on valid report")

        loaded, failed, layers = add_terrain_results(
            results,
            contour_interval=10.0,
            index_multiplier=5,
            z_unit="m",
            cartography_preset="usgs_classic",
            return_layers=True,
            palette_key="natural",
        )
        if loaded < 2 or failed:
            failures.append(f"add_terrain_results loaded={loaded} failed={failed}")
        dem_before = layer_style_xml(layers.get("WORKING_DEM"))
        contours_before = layer_style_xml(layers.get("CONTOURS"))
        group_count_before = len(
            [
                node
                for node in project.layerTreeRoot().children()
                if node.name() == "Terrain Product Studio"
            ]
        )

        # --- restyle with a different palette ---
        count, notes = restyle_outputs(
            plan,
            project=project,
            config={
                "preset": "usgs_classic",
                "palette_key": "usgs_topo",
                "font_family": None,
                "z_unit": "m",
                "contour_interval": 10.0,
                "index_multiplier": 5,
            },
            output_folder=folder,
            restyle_canvas=True,
            restyle_qml=True,
            restyle_layouts=True,
        )
        if count < 2:
            failures.append(f"restyle_outputs restyled {count} layers, expected >= 2")
        dem_after = layer_style_xml(layers.get("WORKING_DEM"))
        if dem_after == dem_before:
            failures.append("DEM renderer XML unchanged after palette restyle")
        group_count_after = len(
            [
                node
                for node in project.layerTreeRoot().children()
                if node.name() == "Terrain Product Studio"
            ]
        )
        if group_count_after != group_count_before:
            failures.append(
                f"restyle created a duplicate group: {group_count_before} -> {group_count_after}"
            )
        qml_path = os.path.join(folder, "styles", "usgs_classic", "working_dem.qml")
        if not os.path.isfile(qml_path):
            failures.append(f"restyle did not write {qml_path}")
        qml_mtime = os.path.getmtime(qml_path)
        siblings = [
            name
            for name in os.listdir(os.path.dirname(qml_path))
            if name.startswith("working_dem")
        ]
        if len(siblings) != 1:
            failures.append(f"QML restyle accumulated siblings: {siblings}")

        # --- restyle again: QML overwritten in place, no numbered sibling ---
        restyle_outputs(
            plan,
            project=project,
            config={
                "preset": "usgs_classic",
                "palette_key": "natural",
                "font_family": None,
                "z_unit": "m",
                "contour_interval": 10.0,
                "index_multiplier": 5,
            },
            output_folder=folder,
            restyle_canvas=True,
            restyle_qml=True,
            restyle_layouts=True,
        )
        siblings = [
            name
            for name in os.listdir(os.path.dirname(qml_path))
            if name.startswith("working_dem")
        ]
        if len(siblings) != 1 or os.path.getmtime(qml_path) == qml_mtime:
            failures.append("second restyle did not overwrite the QML in place")

        # --- layout overrides applied to a plugin layout ---
        layout = QgsPrintLayout(project)
        layout.setName("Probe Terrain Layout")
        layout.setCustomProperty("terrain_product_studio/probe", True)
        project.layoutManager().addLayout(layout)
        map_item = QgsLayoutItemMap(layout)
        map_item.attemptResize(QgsLayoutSize(100, 100))
        layout.addLayoutItem(map_item)
        layout_count, layout_notes = restyle_outputs(
            plan,
            project=project,
            config={
                "preset": "usgs_classic",
                "palette_key": "usgs_topo",
                "font_family": None,
                "z_unit": "m",
                "contour_interval": 10.0,
                "index_multiplier": 5,
            },
            output_folder=folder,
            restyle_canvas=False,
            restyle_qml=False,
            restyle_layouts=True,
        )
        updated_maps = [
            note for note in layout_notes if "map item(s) updated" in note
        ]
        if not updated_maps:
            failures.append(
                f"layout restyle found no map items to update ({layout_notes})"
            )

        # contour labels survived restyle (labeling is part of the style suite)
        if layers.get("CONTOURS") is not None and not layers["CONTOURS"].labeling():
            failures.append("CONTOURS lost its labeling after restyle")

    if failures:
        print("RESTYLE PROBE FAILURES:")
        for failure in failures:
            print(" -", failure)
        return 1
    print("RESTYLE PROBE OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
