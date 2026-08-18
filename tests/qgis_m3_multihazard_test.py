"""QGIS-bound tests for M3: multi-hazard composite index and the
single-GeoPackage bundle."""

import os
import sqlite3
import sys
import tempfile
import unittest

import numpy as np
from osgeo import gdal, ogr, osr

sys.path.insert(0, os.path.dirname(__file__))
from qgis_m2_thematic_test import create_synthetic_dem  # noqa: E402

from terrain_product_studio.core.bundle import create_bundle  # noqa: E402
from terrain_product_studio.core.native_hydrology import (  # noqa: E402
    calculate_complete_hydrology,
)
from terrain_product_studio.core.thematic_terrain import (  # noqa: E402
    calculate_landslide_hazard,
    calculate_multihazard,
)


def _slope_and_accumulation(folder):
    dem = os.path.join(folder, "dem.tif")
    create_synthetic_dem(dem)
    slope_path = os.path.join(folder, "slope.tif")
    gdal.DEMProcessing(slope_path, dem, "slope", format="GTiff")
    calculate_complete_hydrology(
        input_dem_path=dem,
        band_number=1,
        filled_dem_path=os.path.join(folder, "filled.tif"),
        direction_path=os.path.join(folder, "dir.tif"),
        accumulation_path=os.path.join(folder, "acc.tif"),
        stream_raster_path=os.path.join(folder, "stream.tif"),
        stream_vector_path=os.path.join(folder, "stream.gpkg"),
        threshold_cells=20,
        pixel_area_m2=100.0,
        horizontal_meters_per_unit=1.0,
        vertical_meters_per_unit=1.0,
        twi_path=os.path.join(folder, "twi.tif"),
        basin_path=os.path.join(folder, "basins.tif"),
    )
    return dem, slope_path, os.path.join(folder, "acc.tif"), os.path.join(folder, "twi.tif")


class M3MultihazardTests(unittest.TestCase):
    def test_multihazard_classes_and_weights(self):
        with tempfile.TemporaryDirectory() as folder:
            dem, slope_path, acc_path, twi_path = _slope_and_accumulation(folder)
            hazard_path = os.path.join(folder, "landslide.tif")
            ls_path = os.path.join(folder, "ls.tif")
            calculate_landslide_hazard(slope_path, acc_path, hazard_path, ls_path)

            out = os.path.join(folder, "multi_hazard.tif")
            stats = calculate_multihazard(hazard_path, twi_path, slope_path, out)

            self.assertTrue(os.path.exists(out))
            self.assertAlmostEqual(
                stats["low_pct"] + stats["moderate_pct"] + stats["high_pct"],
                100.0,
                delta=0.5,
            )
            self.assertGreater(stats["high_pct"], 0.0)
            self.assertGreater(stats["low_pct"], 0.0)

            # With landslide weight 1 and the others 0, the composite must
            # reproduce the landslide classes: class 4 → High (score 1.0),
            # class 1 → Low (score 0.0).
            out_landslide_only = os.path.join(folder, "multi_landslide.tif")
            calculate_multihazard(
                hazard_path, twi_path, slope_path, out_landslide_only,
                weights=(1.0, 0.0, 0.0),
            )
            hazard_ds = gdal.Open(hazard_path)
            hazard = hazard_ds.GetRasterBand(1).ReadAsArray()
            hazard_ds = None
            composite_ds = gdal.Open(out_landslide_only)
            composite = composite_ds.GetRasterBand(1).ReadAsArray()
            composite_ds = None
            # (landslide - 1) / 3 > 0.66 → landslide >= 3; class 1 → landslide 1.
            self.assertEqual(int(np.count_nonzero(composite == 3)), int(np.count_nonzero(hazard >= 3)))
            self.assertEqual(int(np.count_nonzero(composite == 1)), int(np.count_nonzero(hazard == 1)))

    def test_multihazard_rejects_mismatched_grids(self):
        with tempfile.TemporaryDirectory() as folder:
            dem, slope_path, acc_path, twi_path = _slope_and_accumulation(folder)
            hazard_path = os.path.join(folder, "landslide.tif")
            ls_path = os.path.join(folder, "ls.tif")
            calculate_landslide_hazard(slope_path, acc_path, hazard_path, ls_path)
            shifted = os.path.join(folder, "shifted.tif")
            driver = gdal.GetDriverByName("GTiff")
            ds = driver.Create(shifted, 121, 120, 1, gdal.GDT_Float32)
            ds.SetGeoTransform([500000, 10, 0, 1200000, 0, -10])
            ds.GetRasterBand(1).WriteArray(np.zeros((120, 121), dtype=np.float32))
            ds = None

            with self.assertRaises(RuntimeError):
                calculate_multihazard(hazard_path, twi_path, shifted, os.path.join(folder, "bad.tif"))


class M3BundleTests(unittest.TestCase):
    def _make_vector(self, path):
        driver = ogr.GetDriverByName("GPKG")
        ds = driver.CreateDataSource(path)
        srs = osr.SpatialReference()
        srs.ImportFromEPSG(32648)
        layer = ds.CreateLayer("lines", srs, ogr.wkbLineString)
        feature = ogr.Feature(layer.GetLayerDefn())
        feature.SetGeometry(ogr.CreateGeometryFromWkt("LINESTRING (0 0, 10 10)"))
        layer.CreateFeature(feature)
        feature = None
        ds = None

    def test_bundle_contains_raster_vector_and_skips_html(self):
        with tempfile.TemporaryDirectory() as folder:
            raster = os.path.join(folder, "slope.tif")
            ds = gdal.GetDriverByName("GTiff").Create(raster, 20, 20, 1, gdal.GDT_Float32)
            ds.SetGeoTransform([500000, 10, 0, 1200000, 0, -10])
            ds.GetRasterBand(1).WriteArray(np.ones((20, 20), dtype=np.float32))
            ds = None
            vector = os.path.join(folder, "streams.gpkg")
            self._make_vector(vector)
            viewer = os.path.join(folder, "viewer.html")
            with open(viewer, "w", encoding="utf-8") as stream:
                stream.write("<html>viewer</html>")
            report = os.path.join(folder, "report.json")
            with open(report, "w", encoding="utf-8") as stream:
                stream.write("{}")

            bundle = os.path.join(folder, "bundle.gpkg")
            written = create_bundle(
                {"SLOPE": raster, "STREAMS": vector, "VIEWER_3D": viewer, "REPORT": report},
                bundle,
            )

            kinds = [kind for _, _, kind in written]
            self.assertIn("raster", kinds)
            self.assertIn("vector", kinds)
            self.assertEqual(len(written), 2)  # html + json skipped

            # ogr lists only feature layers; raster layers live in
            # gpkg_contents and are readable through the raster driver.
            db = sqlite3.connect(bundle)
            contents = dict(
                db.execute("SELECT table_name, data_type FROM gpkg_contents").fetchall()
            )
            db.close()
            self.assertEqual(contents.get("slope"), "2d-gridded-coverage")
            self.assertEqual(contents.get("streams"), "features")

            raster_ds = gdal.Open(bundle)
            self.assertIsNotNone(raster_ds)
            self.assertEqual(int(raster_ds.GetRasterBand(1).ReadAsArray().sum()), 400)
            raster_ds = None

            ds = ogr.Open(bundle)
            names = {ds.GetLayer(i).GetName() for i in range(ds.GetLayerCount())}
            self.assertIn("streams", names)
            ds = None

    def test_bundle_merges_multiple_rasters_with_coverage(self):
        """Byte (tiles) and float (2d-gridded-coverage) rasters must merge
        into one package with their metadata rows intact."""
        with tempfile.TemporaryDirectory() as folder:
            byte_raster = os.path.join(folder, "geomorphon.tif")
            ds = gdal.GetDriverByName("GTiff").Create(byte_raster, 20, 20, 1, gdal.GDT_Byte)
            ds.SetGeoTransform([500000, 10, 0, 1200000, 0, -10])
            ds.GetRasterBand(1).WriteArray(np.ones((20, 20), dtype=np.uint8))
            ds = None
            float_raster = os.path.join(folder, "slope.tif")
            ds = gdal.GetDriverByName("GTiff").Create(float_raster, 20, 20, 1, gdal.GDT_Float32)
            ds.SetGeoTransform([500000, 10, 0, 1200000, 0, -10])
            ds.GetRasterBand(1).WriteArray(np.full((20, 20), 7.5, dtype=np.float32))
            ds = None

            bundle = os.path.join(folder, "bundle.gpkg")
            written = create_bundle(
                {"GEOMORPHON": byte_raster, "SLOPE": float_raster}, bundle
            )
            self.assertEqual(len(written), 2)

            db = sqlite3.connect(bundle)
            contents = dict(
                db.execute("SELECT table_name, data_type FROM gpkg_contents").fetchall()
            )
            db.close()
            self.assertEqual(contents.get("geomorphon"), "tiles")
            self.assertEqual(contents.get("slope"), "2d-gridded-coverage")

            ds = gdal.Open(bundle)
            sub = {s[0].split(":")[-1]: s[0] for s in ds.GetSubDatasets()}
            ds = None
            byte_ds = gdal.Open(sub["geomorphon"])
            self.assertEqual(int(byte_ds.GetRasterBand(1).ReadAsArray().sum()), 400)
            byte_ds = None
            float_ds = gdal.Open(sub["slope"])
            total = int(float_ds.GetRasterBand(1).ReadAsArray().sum())
            float_ds = None
            # PNG tiles quantize float data (scale/offset 16-bit), so the
            # value cannot round-trip exactly — only within ~10 %.
            self.assertAlmostEqual(total, 3000, delta=300)

    def test_bundle_unique_layer_names(self):
        with tempfile.TemporaryDirectory() as folder:
            raster = os.path.join(folder, "streams.tif")
            ds = gdal.GetDriverByName("GTiff").Create(raster, 10, 10, 1, gdal.GDT_Float32)
            ds.SetGeoTransform([500000, 10, 0, 1200000, 0, -10])
            ds.GetRasterBand(1).WriteArray(np.zeros((10, 10), dtype=np.float32))
            ds = None
            vector = os.path.join(folder, "streams.gpkg")
            self._make_vector(vector)

            bundle = os.path.join(folder, "bundle.gpkg")
            written = create_bundle({"A": raster, "B": vector}, bundle)
            names = [name for _, name, _ in written]
            self.assertEqual(len(names), len(set(name.lower() for name in names)))


if __name__ == "__main__":
    unittest.main()
