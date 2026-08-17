"""Comprehensive test for Strahler river network, TWI, Suitability, Landslide, 3D Web Viewer, and Intelligence Report."""

import os
import shutil
import tempfile
import numpy as np
from osgeo import gdal, osr

from terrain_product_studio.core.native_hydrology import calculate_complete_hydrology
from terrain_product_studio.core.thematic_terrain import calculate_slope_suitability, calculate_landslide_hazard
from terrain_product_studio.core.web_3d_viewer import generate_3d_web_viewer
from terrain_product_studio.core.intelligence_report import generate_intelligence_report


def create_synthetic_dem(path, width=80, height=80):
    driver = gdal.GetDriverByName("GTiff")
    ds = driver.Create(path, width, height, 1, gdal.GDT_Float32)
    ds.SetGeoTransform([500000, 10, 0, 1200000, 0, -10])
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(32648)
    ds.SetProjection(srs.ExportToWkt())
    
    # Create inclined valley terrain with peaks
    y, x = np.mgrid[0:height, 0:width]
    # General slope towards bottom-right + V-shaped valley + local peak
    elev = 500.0 - (x * 1.5 + y * 2.0) + np.abs(x - width / 2.0) * 2.5
    elev += 50.0 * np.exp(-((x - 20) ** 2 + (y - 20) ** 2) / 100.0)
    
    band = ds.GetRasterBand(1)
    band.WriteArray(elev.astype(np.float32))
    band.SetNoDataValue(-9999.0)
    band.FlushCache()
    ds.FlushCache()
    ds = None


def run_all_tests():
    tmp_dir = tempfile.mkdtemp(prefix="tps_test_")
    try:
        dem_path = os.path.join(tmp_dir, "test_dem.tif")
        create_synthetic_dem(dem_path)
        print("✅ Synthetic DEM created.")

        filled_path = os.path.join(tmp_dir, "filled.tif")
        dir_path = os.path.join(tmp_dir, "dir.tif")
        acc_path = os.path.join(tmp_dir, "acc.tif")
        stream_ras_path = os.path.join(tmp_dir, "stream.tif")
        stream_vec_path = os.path.join(tmp_dir, "stream.gpkg")
        twi_path = os.path.join(tmp_dir, "twi.tif")
        basin_path = os.path.join(tmp_dir, "basins.tif")

        # 1. Test Complete Hydrology with Strahler & TWI
        hydro_res = calculate_complete_hydrology(
            input_dem_path=dem_path,
            band_number=1,
            filled_dem_path=filled_path,
            direction_path=dir_path,
            accumulation_path=acc_path,
            stream_raster_path=stream_ras_path,
            stream_vector_path=stream_vec_path,
            threshold_cells=20,
            pixel_area_m2=100.0,
            horizontal_meters_per_unit=1.0,
            vertical_meters_per_unit=1.0,
            twi_path=twi_path,
            basin_path=basin_path,
        )
        print(f"✅ Hydrology completed: {hydro_res}")
        assert os.path.exists(stream_vec_path), "Stream GPKG not created!"
        assert os.path.exists(twi_path), "TWI raster not created!"

        # 2. Test Slope Suitability & Landslide
        # Generate slope raster using GDAL
        slope_path = os.path.join(tmp_dir, "slope.tif")
        gdal.DEMProcessing(slope_path, dem_path, "slope")
        
        suit_path = os.path.join(tmp_dir, "suitability.tif")
        suit_res = calculate_slope_suitability(slope_path, suit_path)
        print(f"✅ Slope suitability completed: {suit_res}")
        assert os.path.exists(suit_path), "Suitability raster not created!"

        hazard_path = os.path.join(tmp_dir, "hazard.tif")
        ls_path = os.path.join(tmp_dir, "ls.tif")
        hazard_res = calculate_landslide_hazard(slope_path, acc_path, hazard_path, ls_path)
        print(f"✅ Landslide hazard completed: {hazard_res}")
        assert os.path.exists(hazard_path), "Hazard raster not created!"

        # 3. Test 3D Web Viewer
        v3d_path = os.path.join(tmp_dir, "interactive_3d.html")
        generate_3d_web_viewer(
            dem_path=dem_path,
            output_html_path=v3d_path,
            title="Test 3D Terrain",
            stream_vector_path=stream_vec_path,
        )
        print(f"✅ 3D Web Viewer generated ({os.path.getsize(v3d_path)} bytes).")
        assert os.path.exists(v3d_path), "3D Web Viewer not created!"

        # 4. Test Topographic Intelligence Report
        intel_path = os.path.join(tmp_dir, "intelligence_report.html")
        generate_intelligence_report(
            dem_path=dem_path,
            output_html_path=intel_path,
            title="Test Intelligence Report",
            slope_path=slope_path,
            suitability_path=suit_path,
            hazard_path=hazard_path,
            stream_vector_path=stream_vec_path,
        )
        print(f"✅ Intelligence Report generated ({os.path.getsize(intel_path)} bytes).")
        assert os.path.exists(intel_path), "Intelligence Report not created!"

        print("\n🎉 ALL TESTS PASSED SUCCESSFULLY! 🎉")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    run_all_tests()
