"""Runtime probe: 2.7.1-style 3D WebGIS viewer emission (v1 inline template).

Execute with the Python bundled inside QGIS:

    /Applications/QGIS.app/Contents/MacOS/QGIS --nocrashdialog \
        --headless --noplugins python3 tests/qgis_scene_probe.py

Asserts:
- generate_3d_web_viewer (v1 API, no overlay/vertical-exaggeration params)
  emits a self-contained HTML with the inline template
- the terrain-data JSON block parses and carries grid + vector payloads
- no un-replaced template tokens remain
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


def make_dem(folder, name="dem.tif", size=96, res=10.0):
    """Small synthetic DEM with a ridge and a valley."""
    path = os.path.join(folder, name)
    driver = gdal.GetDriverByName("GTiff")
    ds = driver.Create(path, size, size, 1, gdal.GDT_Float32)
    ds.SetGeoTransform((500000.0, res, 0.0, 2450000.0, 0.0, -res))
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(32648)
    ds.SetProjection(srs.ExportToWkt())
    band = ds.GetRasterBand(1)
    for row in range(size):
        scan = []
        for col in range(size):
            x = col / float(size)
            y = row / float(size)
            z = 100.0 * math.sin(math.pi * x) + 20.0 * y + 80.0
            scan.append(z)
        band.WriteRaster(0, row, size, 1, struct.pack("<%df" % size, *scan))
    band.FlushCache()
    ds = None
    return path


def make_streams(folder, name="streams.gpkg"):
    """GeoPackage with an ORDER field like the hydrology export."""
    path = os.path.join(folder, name)
    driver = ogr.GetDriverByName("GPKG")
    ds = driver.CreateDataSource(path)
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(32648)
    layer = ds.CreateLayer("streams", srs, ogr.wkbLineString)
    layer.CreateField(ogr.FieldDefn("ORDER", ogr.OFTInteger))
    layer.CreateField(ogr.FieldDefn("ORDER_NAME", ogr.OFTString))
    layer.CreateField(ogr.FieldDefn("LENGTH_M", ogr.OFTReal))
    for order, dy in enumerate((0.1, 0.35, 0.7), start=1):
        feat = ogr.Feature(layer.GetLayerDefn())
        geom = ogr.Geometry(ogr.wkbLineString)
        # Streams must lie inside the DEM extent (x 500000..500960).
        base_y = 2450000.0 - dy * 400.0
        geom.AddPoint_2D(500100.0, base_y)
        geom.AddPoint_2D(500400.0, base_y)
        geom.AddPoint_2D(500700.0, base_y)
        feat.SetGeometry(geom)
        feat.SetField("ORDER", order)
        feat.SetField("ORDER_NAME", f"Order {order}")
        feat.SetField("LENGTH_M", 600.0)
        layer.CreateFeature(feat)
    ds = None
    return path


def main():
    from qgis.core import QgsApplication

    prefix = os.environ.get("QGIS_PREFIX_PATH", "")
    if prefix:
        QgsApplication.setPrefixPath(prefix, True)
    application = QgsApplication([], False)
    application.initQgis()

    from terrain_product_studio.core.web_3d_viewer import generate_3d_web_viewer  # noqa: E402

    failures = []
    with tempfile.TemporaryDirectory() as folder:
        dem = make_dem(folder)
        streams = make_streams(folder)

        html_path = os.path.join(folder, "scene.html")
        generate_3d_web_viewer(
            dem_path=dem,
            output_html_path=html_path,
            title="Probe Scene",
            stream_vector_path=streams,
            contour_vector_path=None,
            spot_peaks_path=None,
            grid_size=64,
        )
        if not os.path.isfile(html_path):
            failures.append("viewer HTML not written")
        else:
            html = open(html_path, encoding="utf-8").read()
            if "@@TERRAIN_DATA@@" in html or "@@TITLE@@" in html:
                failures.append("template token left un-replaced")
            if 'id="terrain-data"' not in html:
                failures.append("inline terrain-data block not found")
            start = html.index('id="terrain-data"')
            tag_end = html.index(">", start)
            json_end = html.index("</script>", tag_end)
            try:
                cfg = json.loads(html[tag_end + 1:json_end].strip())
            except ValueError:
                cfg = None
                failures.append("terrain-data JSON does not parse")
            if cfg is not None:
                for key in (
                    "gw", "gh", "min_z", "max_z", "world_height",
                    "elev_grid", "rivers_3d", "stream_count",
                    "contours_3d", "peaks_3d", "topo_palette",
                ):
                    if key not in cfg:
                        failures.append(f"CFG missing key {key}")
                if cfg.get("stream_count", 0) < 1:
                    failures.append("no rivers_3d emitted")
                if not isinstance(cfg.get("topo_palette"), list) or not cfg["topo_palette"]:
                    failures.append("topo_palette not emitted")
                elif not all(
                    isinstance(color, str) and color.startswith("#")
                    for color in cfg["topo_palette"]
                ):
                    failures.append("topo_palette entries are not hex strings")
                if not (0 < cfg.get("world_height", 0) < 1e6):
                    failures.append(f"bad world_height: {cfg.get('world_height')}")
                grid = cfg.get("elev_grid") or []
                if not grid or len(grid) != cfg.get("gh") or len(grid[0]) != cfg.get("gw"):
                    failures.append("elev_grid dimensions mismatch")

    if failures:
        print("PROBE FAILED:")
        for failure in failures:
            print(f"  ✗ {failure}")
        sys.exit(1)
    print("PROBE OK — 2.7.1 viewer emission verified")
    application.exitQgis()


if __name__ == "__main__":
    main()
