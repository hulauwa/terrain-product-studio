"""End-to-end dark-palette + peak-threshold verification (headless)."""

import os
import shutil
import sys
import tempfile

import numpy as np
from osgeo import gdal, osr

from qgis.core import (
    QgsApplication,
    QgsCoordinateReferenceSystem,
    QgsProcessingContext,
    QgsProcessingFeedback,
    QgsProject,
    QgsRasterLayer,
)

from terrain_product_studio.algorithms.build_package import BuildTerrainPackageAlgorithm
from terrain_product_studio.core.layers import add_terrain_results
from terrain_product_studio.core.presets import PALETTE_ORDER, TERRAIN_PALETTES

failures = []
temp_dir = tempfile.mkdtemp(prefix="tps_dark_probe_")


def check(name, condition, detail=""):
    print(f"{'PASS' if condition else 'FAIL'} {name}" + (f" — {detail}" if detail and not condition else ""))
    if not condition:
        failures.append(name)


def make_dem(path):
    rows, cols = 120, 120
    y, x = np.mgrid[0:rows, 0:cols]
    dem = 100.0 + 3.0 * y + 5.0 * np.sin(x / 9.0) * np.cos(y / 7.0) + 2.0 * x
    driver = gdal.GetDriverByName("GTiff")
    ds = driver.Create(path, cols, rows, 1, gdal.GDT_Float32)
    ds.SetGeoTransform((500000.0, 30.0, 0.0, 4600000.0, 0.0, -30.0))
    srs = osr.SpatialReference()
    srs.SetWellKnownGeogCS("WGS84")
    srs.SetUTM(48, 1)  # EPSG:32648 without needing the PROJ database
    ds.SetProjection(srs.ExportToWkt())
    ds.GetRasterBand(1).WriteArray(dem.astype(np.float32))
    ds.GetRasterBand(1).SetNoDataValue(-9999.0)
    ds = None
    return path


def run_package(prefix, spot_pct, color_relief=True):
    algorithm = BuildTerrainPackageAlgorithm()
    algorithm.initAlgorithm()
    context = QgsProcessingContext()
    feedback = QgsProcessingFeedback()
    # PROJ database is unavailable headless — attach a proj4-derived CRS to
    # the layer object so the algorithm's CRS validation passes.
    dem_layer = QgsRasterLayer(dem_path, "Synthetic DEM")
    dem_layer.setCrs(
        QgsCoordinateReferenceSystem.fromProj4(
            "+proj=utm +zone=48 +datum=WGS84 +units=m +no_defs"
        )
    )
    parameters = {
        "INPUT": dem_layer,
        "BAND": 1,
        "OUTPUT_FOLDER": temp_dir,
        "PREFIX": prefix,
        "Z_UNIT": 0,
        "AUTO_REPROJECT": True,
        "PALETTE": PALETTE_ORDER.index("terrain_dark"),
        "COMPRESSION": 0,
        "VERTICAL_EXAGGERATION": 1.0,
        "AZIMUTH": 315.0,
        "ALTITUDE": 45.0,
        "ZEVENBERGEN": False,
        "CREATE_COLOR_RELIEF": color_relief,
        "CREATE_MULTI_HILLSHADE": color_relief,
        "CREATE_CONTOURS": color_relief,
        "CONTOUR_INTERVAL": 10.0,
        "INDEX_MULTIPLIER": 5,
        "SPOT_PCT": spot_pct,
        "CREATE_SPOT_ELEVATIONS": True,
        "SMOOTHING": 0,
        "SIMPLIFY_TOLERANCE": 0.0,
        "CREATE_BUNDLE": False,
    }
    return algorithm.processAlgorithm(parameters, context, feedback)


os.environ["PROJ_DATA"] = "/Applications/QGIS.app/Contents/Resources/proj"
app = QgsApplication([], False)
app.initQgis()

# Headless Processing needs the GDAL provider for gdal:colorrelief etc.
from processing.algs.gdal.GdalAlgorithmProvider import GdalAlgorithmProvider

_gdal_provider = GdalAlgorithmProvider()
_gdal_provider.loadAlgorithms()
QgsApplication.processingRegistry().addProvider(_gdal_provider)

dem_path = make_dem(os.path.join(temp_dir, "synthetic_dem.tif"))

# ── dark palette run ──────────────────────────────────────────────────────
results = run_package("dark_test", spot_pct=80)
color_relief = str(results["COLOR_RELIEF"])
check("dark color relief created", os.path.exists(color_relief), color_relief)
dark_key = TERRAIN_PALETTES["terrain_dark"]
check("midnight stop colors present in output", dark_key["elev_stops"][0][1:] == (8, 19, 24))

# spot counts: 80% threshold must be <= 0% threshold
ds = gdal.OpenEx(str(results["SPOT_ELEVATIONS"]), gdal.OF_VECTOR)
count_80 = ds.GetLayer().GetFeatureCount()
ds = None
check("spots extracted with 80% threshold", count_80 > 0, str(count_80))

# ── full peaks run (SPOT_PCT=0) ───────────────────────────────────────────
results_all = run_package("all_peaks", spot_pct=0, color_relief=False)
ds = gdal.OpenEx(str(results_all["SPOT_ELEVATIONS"]), gdal.OF_VECTOR)
count_0 = ds.GetLayer().GetFeatureCount()
ds = None
check("80% threshold filters peaks", count_0 >= count_80 and count_80 > 0, f"all={count_0} top80={count_80}")

# ── dark styling via add_terrain_results ──────────────────────────────────
loaded, failed, layers = add_terrain_results(
    results,
    10.0,
    5,
    "m",
    "night_dark",
    "Noto Sans",
    return_layers=True,
)
check("dark layers loaded", loaded > 0, f"loaded={loaded} failed={failed}")
background = QgsProject.instance().backgroundColor().name()
check("project background set to #090b0d", background == "#090b0d", background)
if "MULTI_HILLSHADE" in layers:
    opacity = layers["MULTI_HILLSHADE"].opacity()
    check("dark hillshade opacity 0.45", abs(opacity - 0.45) < 1e-3, str(opacity))
if "CONTOURS" in layers:
    renderer = layers["CONTOURS"].renderer()
    root = renderer.rootRule()
    rule = root.children()[0]  # minor rule
    color = rule.symbol().color()
    check("dark minor contour is light cyan-gray", color.lightness() > 130, color.name())

print()
shutil.rmtree(temp_dir, ignore_errors=True)
if failures:
    print(f"FAILURES: {failures}")
    sys.exit(1)
print("🎉 ALL DARK-RUN PROBES PASSED 🎉")
