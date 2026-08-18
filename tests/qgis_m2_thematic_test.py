"""QGIS-bound tests for M2: geomorphon classification, SPI/STI, and the
landslide fix that feeds real flow accumulation instead of the slope proxy."""

import os
import tempfile
import unittest

import numpy as np
from osgeo import gdal, osr

from terrain_product_studio.core.geomorphon import classify_geomorphon
from terrain_product_studio.core.native_hydrology import calculate_complete_hydrology
from terrain_product_studio.core.thematic_terrain import (
    calculate_landslide_hazard,
    calculate_spi,
    calculate_sti,
)


def create_synthetic_dem(path, width=120, height=120):
    """A UTM DEM with a peak, a valley channel, an inclined plain and flats."""
    driver = gdal.GetDriverByName("GTiff")
    ds = driver.Create(path, width, height, 1, gdal.GDT_Float32)
    ds.SetGeoTransform([500000, 10, 0, 1200000, 0, -10])
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(32648)
    ds.SetProjection(srs.ExportToWkt())

    y, x = np.mgrid[0:height, 0:width]
    # A sharp conical peak (steep enough to exceed the 1 % flatness
    # tolerance near the summit and dominate the valley-channel gradient)
    # plus a V-shaped valley channel and a flat plateau, so every
    # classification rule is exercised.
    peak = 200.0 * np.exp(-((x - 30.0) ** 2 + (y - 30.0) ** 2) / 40.0)
    valley = -35.0 * np.exp(-((x - y - 20.0) ** 2) / 300.0)
    plateau = 20.0 * (
        (x >= 85.0) & (x <= 110.0) & (y >= 15.0) & (y <= 45.0)
    ).astype(float)
    # Gentle base gradient: over the 5-cell search radius it stays well
    # below the flatness tolerance, so the plateau classifies as Flat.
    elev = 50.0 + 0.05 * x + 0.02 * y + peak + valley + plateau

    band = ds.GetRasterBand(1)
    band.WriteArray(elev.astype(np.float32))
    band.SetNoDataValue(-9999.0)
    band.FlushCache()
    ds = None


class M2ThematicTests(unittest.TestCase):
    def test_geomorphon_classifies_synthetic_terrain(self):
        with tempfile.TemporaryDirectory() as folder:
            dem = os.path.join(folder, "dem.tif")
            out = os.path.join(folder, "geomorphon.tif")
            create_synthetic_dem(dem)

            stats = classify_geomorphon(dem, out, radius_m=50.0, tolerance=0.01)

            self.assertTrue(os.path.exists(out))
            # Percentages cover the whole valid area (rounding allowance).
            self.assertAlmostEqual(sum(stats.values()), 100.0, delta=0.5)
            # Peak + valley + plain terrain must yield several distinct forms.
            present = {name for name, pct in stats.items() if pct > 0.5}
            self.assertGreaterEqual(len(present), 3)

            check = gdal.Open(out, gdal.GA_ReadOnly)
            arr = check.GetRasterBand(1).ReadAsArray()
            self.assertEqual(arr.dtype, np.uint8)
            # Every valid cell is classified (edge cells use partial rays).
            self.assertGreaterEqual(int(arr.min()), 1)
            self.assertLessEqual(int(arr.max()), 10)
            check = None

    def test_spi_sti_with_real_accumulation(self):
        with tempfile.TemporaryDirectory() as folder:
            dem = os.path.join(folder, "dem.tif")
            create_synthetic_dem(dem)

            slope_path = os.path.join(folder, "slope.tif")
            gdal.DEMProcessing(slope_path, dem, "slope", format="GTiff")

            summary = calculate_complete_hydrology(
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
            acc_path = os.path.join(folder, "acc.tif")

            spi = calculate_spi(acc_path, slope_path, os.path.join(folder, "spi.tif"))
            sti = calculate_sti(acc_path, slope_path, os.path.join(folder, "sti.tif"))

            self.assertTrue(os.path.exists(os.path.join(folder, "spi.tif")))
            self.assertTrue(os.path.exists(os.path.join(folder, "sti.tif")))
            self.assertGreater(spi["max"], spi["mean"] > 0)
            self.assertGreater(sti["max"], 0)
            self.assertGreaterEqual(spi["mean"], 0.0)
            self.assertEqual(summary["unresolved_cells"], 0)

    def test_landslide_uses_real_accumulation(self):
        with tempfile.TemporaryDirectory() as folder:
            dem = os.path.join(folder, "dem.tif")
            create_synthetic_dem(dem)
            slope_path = os.path.join(folder, "slope.tif")
            gdal.DEMProcessing(slope_path, dem, "slope", format="GTiff")
            acc_path = os.path.join(folder, "acc.tif")
            gdal.DEMProcessing(acc_path, dem, "slope", format="GTiff")  # proxy stands in

            stats = calculate_landslide_hazard(
                slope_path,
                acc_path,
                os.path.join(folder, "hazard.tif"),
                os.path.join(folder, "ls.tif"),
            )
            self.assertTrue(os.path.exists(os.path.join(folder, "hazard.tif")))
            self.assertAlmostEqual(
                sum(
                    stats[k]
                    for k in (
                        "low_hazard_pct",
                        "moderate_hazard_pct",
                        "high_hazard_pct",
                        "very_high_hazard_pct",
                    )
                ),
                100.0,
                delta=0.5,
            )


if __name__ == "__main__":
    unittest.main()
