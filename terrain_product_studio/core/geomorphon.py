"""Geomorphon terrain form classification (Jasiewicz & Stepinski 2013).

Plain ternary-pattern implementation: each of the 8 principal compass
directions is walked out to a search radius and classified as up / down /
flat / saddle relative to the centre cell; the resulting 8-symbol pattern
is mapped to one of the 10 canonical landforms using the counting rules of
the paper (the same rules exposed by the reference implementations):

  all flat            -> Flat
  all down            -> Peak
  all up              -> Pit
  no up,    >=6 down  -> Ridge
  no down,  >=6 up    -> Valley
  no up,    >=4 down  -> Shoulder
  no down,  >=4 up    -> Footslope
  down>up, >=5 down, <=1 up segment   -> Spur
  up>down, >=5 up,   <=1 down segment -> Hollow
  otherwise           -> Slope

Only cells whose search window stays inside the raster are classified;
border cells are nodata.
"""

from __future__ import annotations

import math

import numpy as np
from osgeo import gdal


GEOMORPHON_FORMS = (
    "Flat",
    "Peak",
    "Ridge",
    "Shoulder",
    "Spur",
    "Slope",
    "Hollow",
    "Footslope",
    "Valley",
    "Pit",
)

# Categorical palette: peak red, ridge orange, shoulder yellow, spur pale
# green, slope green, hollow deep green, footslope light blue, valley blue,
# pit dark blue (red-to-blue relief gradient from crest to drainage).
GEOMORPHON_COLORS = (
    "#bdbdbd",
    "#d7191c",
    "#fd8d3c",
    "#fee08b",
    "#d9f0a3",
    "#a6d96a",
    "#66bd63",
    "#74add1",
    "#2c7bb6",
    "#053061",
)

# Directions are ordered clockwise starting from north; only contiguity on
# the circular ring matters, so any consistent order is equivalent.
_DIRECTIONS = ((-1, 0), (-1, 1), (0, 1), (1, 1), (1, 0), (1, -1), (0, -1), (-1, -1))

_POPCOUNT = np.array([bin(i).count("1") for i in range(256)], dtype=np.uint8)


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


def _segments(pattern):
    """Number of contiguous runs of set bits around the 8-direction ring.

    Each segment contributes exactly two transitions on the ring, so the
    segment count is half the popcount of the XOR with its rotation.
    """
    rotated = ((pattern << 1) | (pattern >> 7)) & 0xFF
    return _POPCOUNT[pattern ^ rotated] // 2


def classify_geomorphon(
    dem_path: str,
    output_path: str,
    radius_m: float = 100.0,
    tolerance: float = 0.01,
    band_number: int = 1,
) -> dict:
    """Classify the 10 geomorphon landforms and write a GDT_Byte raster.

    ``radius_m`` is the search radius in ground meters; ``tolerance`` is the
    flatness threshold expressed as a fraction of the DEM relief (2nd–98th
    percentile), default 1 %. Returns per-form area percentages.
    """

    ds = gdal.Open(dem_path, gdal.GA_ReadOnly)
    if ds is None:
        raise RuntimeError(f"Could not open DEM for geomorphon: {dem_path}")
    band = ds.GetRasterBand(band_number)
    elev = band.ReadAsArray().astype(np.float32, copy=False)
    nodata = band.GetNoDataValue()
    valid = np.isfinite(elev)
    if nodata is not None and math.isfinite(float(nodata)):
        valid &= elev != float(nodata)

    geotransform = ds.GetGeoTransform()
    cell_size = max(abs(geotransform[1]), abs(geotransform[5]), 1e-9)
    radius_cells = max(1, int(round(radius_m / cell_size)))

    if valid.any():
        low, high = np.percentile(elev[valid], (2.0, 98.0))
        relief = max(float(high) - float(low), 1e-6)
    else:
        relief = 1.0
    flat_tol = max(float(tolerance) * relief, 1e-6)

    height, width = elev.shape
    forms = np.zeros((height, width), dtype=np.uint8)

    # Process in row chunks so memory stays bounded on large DEMs.
    for row_start in range(0, height, 256):
        row_end = min(row_start + 256, height)
        count = row_end - row_start
        base_rows = np.arange(row_start, row_end)[:, None]
        base_cols = np.arange(width)[None, :]
        centre = elev[base_rows, base_cols]

        up_count = np.zeros((count, width), dtype=np.uint8)
        down_count = np.zeros((count, width), dtype=np.uint8)
        flat_count = np.zeros((count, width), dtype=np.uint8)
        up_pattern = np.zeros((count, width), dtype=np.uint8)
        down_pattern = np.zeros((count, width), dtype=np.uint8)

        for direction, (row_offset, col_offset) in enumerate(_DIRECTIONS):
            max_dz = np.full((count, width), -np.inf, dtype=np.float32)
            min_dz = np.full((count, width), np.inf, dtype=np.float32)
            for step in range(1, radius_cells + 1):
                ray_rows = np.clip(base_rows + step * row_offset, 0, height - 1)
                ray_cols = np.clip(base_cols + step * col_offset, 0, width - 1)
                dz = elev[ray_rows, ray_cols] - centre
                np.maximum(max_dz, dz, out=max_dz)
                np.minimum(min_dz, dz, out=min_dz)
            up = max_dz > flat_tol
            down = min_dz < -flat_tol
            saddle = up & down
            up_only = up & ~saddle
            down_only = down & ~saddle
            neither = ~(up | down)
            up_count += up_only.astype(np.uint8)
            down_count += down_only.astype(np.uint8)
            flat_count += neither.astype(np.uint8)
            up_pattern |= up_only.astype(np.uint8) << direction
            down_pattern |= down_only.astype(np.uint8) << direction

        up_segments = _segments(up_pattern)
        down_segments = _segments(down_pattern)

        # The paper's rules are an if/elif chain (first match wins): a peak
        # cell (all 8 down) also satisfies Ridge, Shoulder and Spur, so the
        # special forms must be applied LAST. np.where is last-match-wins,
        # hence the rules are stacked from most general to most specific.
        form = np.full((count, width), 6, dtype=np.uint8)  # default: Slope
        form = np.where(
            (down_count > up_count) & (down_count >= 5) & (up_segments <= 1), 5, form
        )  # Spur
        form = np.where(
            (up_count > down_count) & (up_count >= 5) & (down_segments <= 1), 7, form
        )  # Hollow
        form = np.where((up_count == 0) & (down_count >= 4), 4, form)  # Shoulder
        form = np.where((down_count == 0) & (up_count >= 4), 8, form)  # Footslope
        form = np.where((up_count == 0) & (down_count >= 6), 3, form)  # Ridge
        form = np.where((down_count == 0) & (up_count >= 6), 9, form)  # Valley
        form = np.where(up_count == 8, 10, form)  # Pit
        form = np.where(down_count == 8, 2, form)  # Peak
        form = np.where(flat_count == 8, 1, form)  # Flat
        forms[row_start:row_end] = form

    forms[~valid] = 0
    _write_raster(ds, output_path, forms, gdal.GDT_Byte, 0)
    ds = None

    total = max(1, int(np.count_nonzero(valid)))
    stats = {}
    for code, name in enumerate(GEOMORPHON_FORMS, start=1):
        stats[name.lower()] = round(
            float(np.count_nonzero(forms == code)) / total * 100.0, 2
        )
    return stats
