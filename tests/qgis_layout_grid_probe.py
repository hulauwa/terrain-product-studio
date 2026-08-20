"""Verify USA-standard grid annotations (outside frame, horizontal)."""

import os
import shutil
import sys
import tempfile

import numpy as np
from osgeo import gdal, osr

from qgis.core import QgsApplication, QgsProject, QgsRasterLayer
from qgis.PyQt.QtWidgets import QApplication

from terrain_product_studio.core.layouts import create_terrain_layout

failures = []
temp_dir = tempfile.mkdtemp(prefix="tps_grid_probe_")


def check(name, condition, detail=""):
    print(f"{'PASS' if condition else 'FAIL'} {name}" + (f" — {detail}" if detail and not condition else ""))
    if not condition:
        failures.append(name)


app = QgsApplication([], False)
app.initQgis()
_ = QApplication.instance() or QApplication([])

rows, cols = 80, 80
y, x = np.mgrid[0:rows, 0:cols]
dem = 100.0 + 3.0 * y + 2.0 * x
dem_path = os.path.join(temp_dir, "dem.tif")
ds = gdal.GetDriverByName("GTiff").Create(dem_path, cols, rows, 1, gdal.GDT_Float32)
ds.SetGeoTransform((500000.0, 30.0, 0.0, 4600000.0, 0.0, -30.0))
spatial_reference = osr.SpatialReference()
spatial_reference.ImportFromEPSG(32610)
ds.SetProjection(spatial_reference.ExportToWkt())
ds.GetRasterBand(1).WriteArray(dem.astype(np.float32))
ds = None

project = QgsProject.instance()
relief = QgsRasterLayer(dem_path, "Elevation color relief")
project.addMapLayer(relief)

config = {
    "preset": "natural_earth",
    "layout_template": "classic_topo",
    "palette_key": "natural",
    "font_family": "Noto Sans",
    "create_layout": True,
    "layout_name": "Terrain Map",
    "title": "TOPOGRAPHIC TERRAIN MAP",
    "subtitle": "Test",
    "author": "Test",
    "source": "DEM",
    "grid": True,
    "open_layout": False,
    "export_pdf": False,
    "export_png": False,
    "dpi": 300,
    "paper_size": "a4",
    "orientation": "auto",
    "export_prefix": "probe",
}

layout, exported = create_terrain_layout(
    project,
    {"COLOR_RELIEF": relief},
    temp_dir,
    config,
    north_arrow_path=os.path.join(
        os.path.dirname(__file__), "..", "terrain_product_studio", "icons", "north_arrow_classic.svg"
    ),
)
check("layout created", layout is not None)

from qgis.core import QgsLayoutItemMap

maps = [i for i in layout.items() if isinstance(i, QgsLayoutItemMap)]
check("map item found", len(maps) == 1, str(len(maps)))
if maps:
    grid_collection = maps[0].grids()
    grid_count = grid_collection.size() if hasattr(grid_collection, "size") else len(grid_collection.asList())
    check("grid added", grid_count == 1, str(grid_count))
    if grid_count == 1:
        grid = grid_collection.grid(0)
        # Version-aware getters: QGIS 4 takes a border side, QGIS 3 takes none.
        try:
            from qgis.core import Qgis

            position = int(grid.annotationPosition(Qgis.MapGridBorderSide.Left))
            direction = int(grid.annotationDirection(Qgis.MapGridBorderSide.Left))
            outside = int(Qgis.MapGridAnnotationPosition.OutsideMapFrame)
            horizontal = int(Qgis.MapGridAnnotationDirection.Horizontal)
        except AttributeError:
            from qgis.core import QgsLayoutItemMapGrid

            position = int(grid.annotationPosition())
            direction = int(grid.annotationDirection())
            try:
                outside = int(
                    QgsLayoutItemMapGrid.AnnotationPosition.OutsideMapFrame
                )
                horizontal = int(
                    QgsLayoutItemMapGrid.AnnotationDirection.Horizontal
                )
            except AttributeError:
                outside = int(getattr(QgsLayoutItemMapGrid, "OutsideMapFrame"))
                horizontal = int(getattr(QgsLayoutItemMapGrid, "Horizontal"))
        check("annotation enabled", grid.annotationEnabled(), str(grid.annotationEnabled()))
        check("annotation position = OutsideMapFrame", position == outside, str(position))
        check("annotation direction = Horizontal", direction == horizontal, str(direction))

dual_config = dict(config)
dual_config["layout_name"] = "Terrain Map Dual Grid"
dual_config["grid_mode"] = "dual"
dual_layout, _ = create_terrain_layout(
    project,
    {"COLOR_RELIEF": relief},
    temp_dir,
    dual_config,
    north_arrow_path=os.path.join(
        os.path.dirname(__file__), "..", "terrain_product_studio", "icons", "north_arrow_classic.svg"
    ),
)
dual_maps = [i for i in dual_layout.items() if isinstance(i, QgsLayoutItemMap)]
check("dual-grid map item found", len(dual_maps) == 1, str(len(dual_maps)))
if dual_maps:
    dual_collection = dual_maps[0].grids()
    dual_count = dual_collection.size() if hasattr(dual_collection, "size") else len(dual_collection.asList())
    check("dual grid adds projected plus WGS84 grids", dual_count == 2, str(dual_count))
    authids = {
        dual_collection.grid(index).crs().authid()
        for index in range(dual_count)
    }
    check("dual grid contains map CRS", "EPSG:32610" in authids, str(authids))
    check("dual grid contains WGS84", "EPSG:4326" in authids, str(authids))

print()
shutil.rmtree(temp_dir, ignore_errors=True)
if failures:
    print(f"FAILURES: {failures}")
    sys.exit(1)
print("🎉 ALL LAYOUT-GRID PROBES PASSED 🎉")
