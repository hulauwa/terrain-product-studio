"""Local elevation maxima (spot height / peak marker) extraction from DEM rasters."""

from __future__ import annotations

import math
import os


def extract_spot_elevations(
    input_dem_path: str,
    band_number: int,
    output_path: str,
    min_prominence_m: float = 15.0,
    window_size: int = 15,
) -> int:
    """Extract local elevation peak points from DEM and save to GeoPackage.

    Returns the count of extracted spot elevation features.
    """

    import numpy as np
    from osgeo import gdal, ogr, osr

    source = gdal.Open(input_dem_path, gdal.GA_ReadOnly)
    if source is None:
        raise RuntimeError("Could not open input DEM for spot elevation extraction.")

    band = source.GetRasterBand(band_number)
    elevation = band.ReadAsArray().astype(np.float32, copy=False)
    nodata = band.GetNoDataValue()

    valid = np.isfinite(elevation)
    if nodata is not None and math.isfinite(float(nodata)):
        valid &= elevation != float(nodata)

    if not np.any(valid):
        return 0

    height, width = elevation.shape

    w = max(3, int(window_size))
    try:
        from scipy.ndimage import maximum_filter, uniform_filter

        local_max = maximum_filter(elevation, size=w, mode="nearest")
        is_peak = valid & (elevation == local_max)
        if min_prominence_m > 0:
            local_mean = uniform_filter(elevation, size=w * 2, mode="nearest")
            is_peak &= (elevation - local_mean) >= min_prominence_m
    except ImportError:
        pad = w // 2
        padded = np.pad(elevation, pad, mode="edge")
        local_max = np.copy(elevation)
        for dy in range(-pad, pad + 1):
            for dx in range(-pad, pad + 1):
                if dy == 0 and dx == 0:
                    continue
                neighbor = padded[pad + dy : pad + dy + height, pad + dx : pad + dx + width]
                local_max = np.maximum(local_max, neighbor)
        is_peak = valid & (elevation >= local_max)
        if min_prominence_m > 0:
            pad2 = w
            padded2 = np.pad(elevation, pad2, mode="edge")
            accum = np.zeros_like(elevation, dtype=np.float64)
            count = 0
            step = max(1, w // 3)
            for dy in range(-pad2, pad2 + 1, step):
                for dx in range(-pad2, pad2 + 1, step):
                    accum += padded2[pad2 + dy : pad2 + dy + height, pad2 + dx : pad2 + dx + width]
                    count += 1
            local_mean = (accum / max(1, count)).astype(np.float32)
            is_peak &= (elevation - local_mean) >= min_prominence_m

    peak_rows, peak_cols = np.nonzero(is_peak)

    if len(peak_rows) == 0:
        return 0

    geotransform = source.GetGeoTransform()
    projection = source.GetProjection()

    spatial_ref = osr.SpatialReference()
    if projection:
        spatial_ref.ImportFromWkt(projection)

    driver = ogr.GetDriverByName("GPKG")
    if os.path.exists(output_path):
        driver.DeleteDataSource(output_path)

    dataset = driver.CreateDataSource(output_path)
    layer = dataset.CreateLayer("spot_elevations", spatial_ref, ogr.wkbPoint)

    elev_field = ogr.FieldDefn("ELEV", ogr.OFTReal)
    elev_field.SetPrecision(1)
    layer.CreateField(elev_field)

    label_field = ogr.FieldDefn("LABEL", ogr.OFTString)
    label_field.SetWidth(32)
    layer.CreateField(label_field)

    count = 0
    layer.StartTransaction()
    for row, col in zip(peak_rows, peak_cols):
        z = float(elevation[row, col])
        x = geotransform[0] + (col + 0.5) * geotransform[1] + (row + 0.5) * geotransform[2]
        y = geotransform[3] + (col + 0.5) * geotransform[4] + (row + 0.5) * geotransform[5]

        point = ogr.Geometry(ogr.wkbPoint)
        point.AddPoint(x, y)

        feature = ogr.Feature(layer.GetLayerDefn())
        feature.SetGeometry(point)
        feature.SetField("ELEV", round(z, 1))
        feature.SetField("LABEL", f"▲ {round(z):,d}")
        layer.CreateFeature(feature)
        count += 1

    layer.CommitTransaction()
    dataset = None
    source = None
    return count
