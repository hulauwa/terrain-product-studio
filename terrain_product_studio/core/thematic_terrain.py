"""Thematic terrain analytics: Urban Construction Suitability and Landslide / RUSLE LS-Factor."""

from __future__ import annotations

import math
import numpy as np
from osgeo import gdal


def _write_raster(reference, path, array, gdal_type, nodata):
    driver = gdal.GetDriverByName("GTiff")
    dataset = driver.Create(
        path,
        reference.RasterXSize,
        reference.RasterYSize,
        1,
        gdal_type,
        options=["COMPRESS=DEFLATE", "TILED=YES", "BIGTIFF=IF_SAFER"],
    )
    if dataset is None:
        raise RuntimeError(f"Could not create raster: {path}")
    dataset.SetGeoTransform(reference.GetGeoTransform())
    dataset.SetProjection(reference.GetProjection())
    band = dataset.GetRasterBand(1)
    band.WriteArray(array)
    band.SetNoDataValue(nodata)
    band.FlushCache()
    dataset.FlushCache()
    band = None
    dataset = None


def calculate_slope_suitability(slope_path: str, output_path: str) -> dict:
    """Reclassify slope in degrees into 5 urban planning & engineering suitability classes.

    Class 1: 0 - 3 deg   -> Very High Suitability (Đất rất thuận lợi xây dựng)
    Class 2: 3 - 8 deg   -> High Suitability (Thuận lợi, thoát nước tự nhiên)
    Class 3: 8 - 15 deg  -> Moderate Suitability (Hạn chế, cần san nền)
    Class 4: 15 - 25 deg -> Restricted / Steep (Khó khăn, hạn chế xây dựng)
    Class 5: > 25 deg    -> Conservation / Steep (Cấm xây dựng kiên cố, bảo tồn)
    """
    ds = gdal.Open(slope_path, gdal.GA_ReadOnly)
    if ds is None:
        raise RuntimeError(f"Could not open slope raster: {slope_path}")

    band = ds.GetRasterBand(1)
    slope = band.ReadAsArray().astype(np.float32, copy=False)
    nodata = band.GetNoDataValue()

    valid = np.isfinite(slope)
    if nodata is not None and math.isfinite(float(nodata)):
        valid &= slope != float(nodata)

    suitability = np.zeros(slope.shape, dtype=np.uint8)

    # Classify
    c1 = valid & (slope >= 0.0) & (slope < 3.0)
    c2 = valid & (slope >= 3.0) & (slope < 8.0)
    c3 = valid & (slope >= 8.0) & (slope < 15.0)
    c4 = valid & (slope >= 15.0) & (slope < 25.0)
    c5 = valid & (slope >= 25.0)

    suitability[c1] = 1
    suitability[c2] = 2
    suitability[c3] = 3
    suitability[c4] = 4
    suitability[c5] = 5

    _write_raster(ds, output_path, suitability, gdal.GDT_Byte, 0)

    total_valid = max(1, int(np.count_nonzero(valid)))
    stats = {
        "class_1_pct": round(float(np.count_nonzero(c1)) / total_valid * 100.0, 2),
        "class_2_pct": round(float(np.count_nonzero(c2)) / total_valid * 100.0, 2),
        "class_3_pct": round(float(np.count_nonzero(c3)) / total_valid * 100.0, 2),
        "class_4_pct": round(float(np.count_nonzero(c4)) / total_valid * 100.0, 2),
        "class_5_pct": round(float(np.count_nonzero(c5)) / total_valid * 100.0, 2),
    }

    ds = None
    return stats


def calculate_landslide_hazard(
    slope_path: str,
    accumulation_path: str,
    output_hazard_path: str,
    output_ls_path: str | None = None,
) -> dict:
    """Compute RUSLE LS-factor and Landslide Susceptibility Index (4 tiers).

    RUSLE LS Factor:
      LS = (As / 22.13)^0.4 * (sin(slope_rad) / 0.0896)^1.3
    
    Landslide Hazard Index (1 to 4):
      Combines slope gradient, flow accumulation convergence, and slope energy.
      1: Low Hazard (An toàn / Thấp)
      2: Moderate Hazard (Trung bình)
      3: High Hazard (Nguy cơ cao)
      4: Very High Hazard (Nguy cơ rất cao / Cực kỳ nguy hiểm)
    """
    ds_slope = gdal.Open(slope_path, gdal.GA_ReadOnly)
    ds_acc = gdal.Open(accumulation_path, gdal.GA_ReadOnly)
    if ds_slope is None or ds_acc is None:
        raise RuntimeError("Could not open slope or accumulation raster for landslide hazard.")

    slope_band = ds_slope.GetRasterBand(1)
    acc_band = ds_acc.GetRasterBand(1)

    slope = slope_band.ReadAsArray().astype(np.float32, copy=False)
    acc = acc_band.ReadAsArray().astype(np.float32, copy=False)

    slope_nodata = slope_band.GetNoDataValue()
    acc_nodata = acc_band.GetNoDataValue()

    valid = np.isfinite(slope) & np.isfinite(acc)
    if slope_nodata is not None and math.isfinite(float(slope_nodata)):
        valid &= slope != float(slope_nodata)
    if acc_nodata is not None and math.isfinite(float(acc_nodata)):
        valid &= acc != float(acc_nodata)
    valid &= acc >= 1.0

    gt = ds_slope.GetGeoTransform()
    cell_size = max(abs(gt[1]), 1.0)
    
    # Specific catchment area As in meters
    As = np.maximum(acc * cell_size, cell_size)
    slope_rad = np.radians(np.clip(slope, 0.0, 89.0))
    sin_slope = np.sin(slope_rad)

    # RUSLE LS Factor
    # Moore & Wilson (1992) / Desmet & Govers (1996) formula
    ls_factor = np.zeros_like(slope, dtype=np.float32)
    ls_calc = ((As / 22.13) ** 0.4) * ((np.maximum(sin_slope, 0.001) / 0.0896) ** 1.3)
    ls_factor[valid] = np.clip(ls_calc[valid], 0.0, 200.0)

    if output_ls_path:
        ls_out = ls_factor.copy()
        ls_out[~valid] = -9999.0
        _write_raster(ds_slope, output_ls_path, ls_out, gdal.GDT_Float32, -9999.0)

    # Landslide Susceptibility Index (1 to 4)
    # Based on slope thresholds and moisture accumulation convergence
    hazard = np.zeros(slope.shape, dtype=np.uint8)

    # Weighted hazard score:
    # High slope + moderate/high flow accumulation = critical landslide slip plane
    score = np.zeros_like(slope, dtype=np.float32)
    score += (slope / 15.0) * 1.5
    score += np.log10(np.maximum(acc, 1.0)) * 0.5
    score += (ls_factor / 10.0) * 0.8

    h1 = valid & (slope < 12.0) & (score < 2.5)
    h2 = valid & (((slope >= 12.0) & (slope < 22.0)) | ((score >= 2.5) & (score < 4.5))) & ~h1
    h3 = valid & (((slope >= 22.0) & (slope < 35.0)) | ((score >= 4.5) & (score < 7.0))) & ~h1 & ~h2
    h4 = valid & ((slope >= 35.0) | (score >= 7.0)) & ~h1 & ~h2 & ~h3

    hazard[h1] = 1
    hazard[h2] = 2
    hazard[h3] = 3
    hazard[h4] = 4

    _write_raster(ds_slope, output_hazard_path, hazard, gdal.GDT_Byte, 0)

    total_valid = max(1, int(np.count_nonzero(valid)))
    stats = {
        "low_hazard_pct": round(float(np.count_nonzero(h1)) / total_valid * 100.0, 2),
        "moderate_hazard_pct": round(float(np.count_nonzero(h2)) / total_valid * 100.0, 2),
        "high_hazard_pct": round(float(np.count_nonzero(h3)) / total_valid * 100.0, 2),
        "very_high_hazard_pct": round(float(np.count_nonzero(h4)) / total_valid * 100.0, 2),
    }

    ds_slope = None
    ds_acc = None
    return stats


def _calculate_hydrologic_index(accumulation_path, slope_path, output_path, kind):
    """Shared SPI / STI computation from a flow accumulation and slope raster.

    Specific catchment area As = accumulation × cell size (m). ``kind`` is
    either ``"spi"`` (Stream Power Index = ln(As · tan(slope))) or ``"sti"``
    (Sediment Transport Index = (As/22.13)^0.6 · (sin(slope)/0.0896)^1.3).
    """

    ds_acc = gdal.Open(accumulation_path, gdal.GA_ReadOnly)
    ds_slope = gdal.Open(slope_path, gdal.GA_ReadOnly)
    if ds_acc is None or ds_slope is None:
        raise RuntimeError(
            f"Could not open accumulation or slope raster for {kind.upper()}."
        )

    acc = ds_acc.GetRasterBand(1).ReadAsArray().astype(np.float32, copy=False)
    slope = ds_slope.GetRasterBand(1).ReadAsArray().astype(np.float32, copy=False)
    if acc.shape != slope.shape:
        ds_acc = None
        ds_slope = None
        raise RuntimeError(
            f"{kind.upper()} requires accumulation and slope rasters with identical grids."
        )

    acc_nodata = ds_acc.GetRasterBand(1).GetNoDataValue()
    slope_nodata = ds_slope.GetRasterBand(1).GetNoDataValue()
    valid = np.isfinite(acc) & np.isfinite(slope)
    if acc_nodata is not None and math.isfinite(float(acc_nodata)):
        valid &= acc != float(acc_nodata)
    if slope_nodata is not None and math.isfinite(float(slope_nodata)):
        valid &= slope != float(slope_nodata)
    valid &= acc >= 1.0

    geotransform = ds_slope.GetGeoTransform()
    cell_size = max(abs(geotransform[1]), 1.0)
    As = np.maximum(acc * cell_size, cell_size)
    slope_rad = np.radians(np.clip(slope, 0.0, 89.0))
    sin_slope = np.sin(slope_rad)

    index = np.zeros_like(acc, dtype=np.float32)
    if kind == "spi":
        index[valid] = np.log(
            np.maximum(As[valid] * np.maximum(np.tan(slope_rad[valid]), 1e-9), 1e-9)
        )
    else:  # sti — Moore & Wilson (1992) / Desmet & Govers (1996) form
        index[valid] = ((As[valid] / 22.13) ** 0.6) * (
            (np.maximum(sin_slope[valid], 0.001) / 0.0896) ** 1.3
        )

    output = index.copy()
    output[~valid] = -9999.0
    _write_raster(ds_slope, output_path, output, gdal.GDT_Float32, -9999.0)
    ds_acc = None
    ds_slope = None

    if np.any(valid):
        return {
            "max": round(float(np.max(index[valid])), 3),
            "mean": round(float(np.mean(index[valid])), 3),
        }
    return {"max": 0.0, "mean": 0.0}


def calculate_spi(accumulation_path: str, slope_path: str, output_path: str) -> dict:
    """Stream Power Index — SPI = ln(As × tan(slope)); As = acc × cell size."""
    return _calculate_hydrologic_index(accumulation_path, slope_path, output_path, "spi")


def calculate_sti(accumulation_path: str, slope_path: str, output_path: str) -> dict:
    """Sediment Transport Index — STI = (As/22.13)^0.6 × (sin(slope)/0.0896)^1.3."""
    return _calculate_hydrologic_index(accumulation_path, slope_path, output_path, "sti")
