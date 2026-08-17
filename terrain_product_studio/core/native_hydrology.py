"""D8 accumulation and drainage extraction using QGIS-bundled NumPy/GDAL.

The depression filling and direction raster are produced by QGIS' native Wang
& Liu algorithm.  This module turns its documented 0=N ... 7=NW directions
into accumulation, stream lines and optional topographic indices, without a
GRASS/SAGA installation dependency.
"""

from __future__ import annotations

import math
import os


MAX_HYDROLOGY_CELLS = 4_000_000


def _write_raster(reference, path, array, gdal_type, nodata):
    from osgeo import gdal

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


def _cell_center(geotransform, row, column):
    x = (
        geotransform[0]
        + (column + 0.5) * geotransform[1]
        + (row + 0.5) * geotransform[2]
    )
    y = (
        geotransform[3]
        + (column + 0.5) * geotransform[4]
        + (row + 0.5) * geotransform[5]
    )
    return float(x), float(y)


def _write_stream_segments(path, reference, stream_cells, downstream, accumulation, pixel_area_m2):
    import json
    import re

    width = reference.RasterXSize
    geotransform = reference.GetGeoTransform()
    projection = reference.GetProjection() or ""
    authority = re.search(r'(?:AUTHORITY|ID)\["EPSG",\s*"?(\d+)"?\]', projection)
    crs_name = f"EPSG:{authority.group(1)}" if authority else projection
    with open(path, "w", encoding="utf-8") as stream:
        stream.write('{"type":"FeatureCollection","name":"potential_streams",')
        stream.write(
            '"crs":{"type":"name","properties":{"name":'
            + json.dumps(crs_name)
            + '}},"features":['
        )
        first = True
        for flat_index in stream_cells:
            target = int(downstream[flat_index])
            if target < 0:
                continue
            row, column = divmod(int(flat_index), width)
            target_row, target_column = divmod(target, width)
            x1, y1 = _cell_center(geotransform, row, column)
            x2, y2 = _cell_center(geotransform, target_row, target_column)
            feature = {
                "type": "Feature",
                "properties": {
                    "acc_cells": float(accumulation[flat_index]),
                    "area_ha": float(accumulation[flat_index])
                    * pixel_area_m2
                    / 10000.0,
                },
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[x1, y1], [x2, y2]],
                },
            }
            if not first:
                stream.write(",")
            json.dump(feature, stream, ensure_ascii=False, separators=(",", ":"))
            first = False
        stream.write("]}")


def _condition_dem(
    input_dem_path,
    band_number,
    filled_dem_path,
    direction_path,
    horizontal_meters_per_unit,
    vertical_meters_per_unit,
):
    """Priority-flood a DEM and return valid cells for deterministic D8 flow."""

    import heapq

    import numpy as np
    from osgeo import gdal

    source = gdal.Open(input_dem_path, gdal.GA_ReadOnly)
    if source is None:
        raise RuntimeError("Could not open the working DEM for hydrology.")
    if band_number < 1 or band_number > source.RasterCount:
        raise RuntimeError("Hydrology band is outside the raster band range.")
    width, height = source.RasterXSize, source.RasterYSize
    if width * height > MAX_HYDROLOGY_CELLS:
        raise RuntimeError(
            f"Native hydrology is limited to {MAX_HYDROLOGY_CELLS:,} cells per run; "
            f"this DEM has {width * height:,}. Clip or resample the DEM first."
        )
    source_band = source.GetRasterBand(band_number)
    elevation = source_band.ReadAsArray().astype(np.float32, copy=False)
    nodata = source_band.GetNoDataValue()
    valid = np.isfinite(elevation)
    if nodata is not None and math.isfinite(float(nodata)):
        valid &= elevation != float(nodata)
    if not np.any(valid):
        raise RuntimeError("The selected DEM band contains no valid elevation cells.")

    filled = elevation.copy()
    visited = np.zeros((height, width), dtype=bool)
    parent_direction = np.full((height, width), -1, dtype=np.int16)
    seed = np.zeros((height, width), dtype=bool)
    seed[0, :] = valid[0, :]
    seed[-1, :] = valid[-1, :]
    seed[:, 0] = valid[:, 0]
    seed[:, -1] = valid[:, -1]
    # Valid cells touching a NoData void also act as drainage boundaries.
    invalid = ~valid
    seed[1:, :] |= valid[1:, :] & invalid[:-1, :]
    seed[:-1, :] |= valid[:-1, :] & invalid[1:, :]
    seed[:, 1:] |= valid[:, 1:] & invalid[:, :-1]
    seed[:, :-1] |= valid[:, :-1] & invalid[:, 1:]

    queue = []
    for flat_index in np.flatnonzero(seed.ravel()):
        row, column = divmod(int(flat_index), width)
        visited[row, column] = True
        heapq.heappush(queue, (float(filled[row, column]), int(flat_index)))

    geotransform = source.GetGeoTransform()
    x_size_m = abs(geotransform[1]) * horizontal_meters_per_unit
    y_size_m = abs(geotransform[5]) * horizontal_meters_per_unit
    base_step_m = max(min(x_size_m, y_size_m), 1e-9)
    epsilon_z = (
        math.tan(math.radians(0.05)) * base_step_m / max(vertical_meters_per_unit, 1e-9)
    )
    offsets = ((-1, 0), (-1, 1), (0, 1), (1, 1), (1, 0), (1, -1), (0, -1), (-1, -1))
    while queue:
        current_elevation, flat_index = heapq.heappop(queue)
        row, column = divmod(flat_index, width)
        for code, (row_offset, column_offset) in enumerate(offsets):
            neighbor_row = row + row_offset
            neighbor_column = column + column_offset
            if not (0 <= neighbor_row < height and 0 <= neighbor_column < width):
                continue
            if not valid[neighbor_row, neighbor_column] or visited[neighbor_row, neighbor_column]:
                continue
            visited[neighbor_row, neighbor_column] = True
            original = float(elevation[neighbor_row, neighbor_column])
            conditioned = max(original, current_elevation + epsilon_z)
            filled[neighbor_row, neighbor_column] = conditioned
            parent_direction[neighbor_row, neighbor_column] = (code + 4) % 8
            neighbor_flat = neighbor_row * width + neighbor_column
            heapq.heappush(queue, (conditioned, neighbor_flat))

    # Prefer the steepest local descent, retaining the flood parent for flats.
    directions = parent_direction.copy()
    best_slope = np.zeros((height, width), dtype=np.float32)
    for code, (row_offset, column_offset) in enumerate(offsets):
        source_row = slice(max(0, -row_offset), min(height, height - row_offset))
        source_column = slice(max(0, -column_offset), min(width, width - column_offset))
        target_row = slice(max(0, row_offset), min(height, height + row_offset))
        target_column = slice(max(0, column_offset), min(width, width + column_offset))
        distance = math.hypot(
            row_offset * y_size_m, column_offset * x_size_m
        )
        slope = (
            filled[source_row, source_column] - filled[target_row, target_column]
        ) / max(distance, 1e-9)
        eligible = (
            valid[source_row, source_column]
            & valid[target_row, target_column]
            & (slope > best_slope[source_row, source_column])
            & (slope > 0)
        )
        best_view = best_slope[source_row, source_column]
        direction_view = directions[source_row, source_column]
        best_view[eligible] = slope[eligible]
        direction_view[eligible] = code

    filled_output = filled.copy()
    filled_output[~valid] = -9999.0
    direction_output = directions.copy()
    direction_output[~valid] = -9999
    _write_raster(source, filled_dem_path, filled_output, gdal.GDT_Float32, -9999.0)
    _write_raster(source, direction_path, direction_output, gdal.GDT_Int16, -9999)
    source_band = None
    source = None
    return valid


def calculate_native_hydrology(
    direction_path,
    filled_dem_path,
    accumulation_path,
    stream_raster_path,
    stream_vector_path,
    threshold_cells,
    pixel_area_m2,
    basin_path=None,
    feedback=None,
):
    """Calculate D8 products and return a compact processing summary."""

    import numpy as np
    from osgeo import gdal

    direction_dataset = gdal.Open(direction_path, gdal.GA_ReadOnly)
    if direction_dataset is None:
        raise RuntimeError("Could not open the native flow-direction raster.")
    width = direction_dataset.RasterXSize
    height = direction_dataset.RasterYSize
    cell_count = width * height
    if cell_count > MAX_HYDROLOGY_CELLS:
        raise RuntimeError(
            f"Native hydrology is limited to {MAX_HYDROLOGY_CELLS:,} cells per run; "
            f"this DEM has {cell_count:,}. Clip/resample the DEM or use an installed "
            "GRASS hydrology workflow for larger rasters."
        )

    direction_band = direction_dataset.GetRasterBand(1)
    directions = direction_band.ReadAsArray().astype(np.int16, copy=False)
    filled_dataset = gdal.Open(filled_dem_path, gdal.GA_ReadOnly)
    if filled_dataset is None:
        raise RuntimeError("Could not open the conditioned DEM.")
    filled_band = filled_dataset.GetRasterBand(1)
    filled = filled_band.ReadAsArray()
    filled_nodata = filled_band.GetNoDataValue()
    valid = np.isfinite(filled)
    if filled_nodata is not None and math.isfinite(float(filled_nodata)):
        valid &= filled != float(filled_nodata)
    valid_flat = valid.ravel()
    direction_flat = directions.ravel()
    total = direction_flat.size

    downstream = np.full(total, -1, dtype=np.int64)
    offsets = (-width, -width + 1, 1, width + 1, width, width - 1, -1, -width - 1)
    for code, offset in enumerate(offsets):
        cells = np.flatnonzero(valid_flat & (direction_flat == code))
        if cells.size == 0:
            continue
        rows = cells // width
        columns = cells - rows * width
        target_rows = rows + (-1, -1, 0, 1, 1, 1, 0, -1)[code]
        target_columns = columns + (0, 1, 1, 1, 0, -1, -1, -1)[code]
        inside = (
            (target_rows >= 0)
            & (target_rows < height)
            & (target_columns >= 0)
            & (target_columns < width)
        )
        cells = cells[inside]
        targets = cells + offset
        targets_valid = valid_flat[targets]
        downstream[cells[targets_valid]] = targets[targets_valid]

    indegree = np.zeros(total, dtype=np.int32)
    routed = downstream >= 0
    np.add.at(indegree, downstream[routed], 1)
    accumulation = np.zeros(total, dtype=np.float32)
    accumulation[valid_flat] = 1.0
    current = np.flatnonzero(valid_flat & (indegree == 0))
    processed = 0
    levels = []
    while current.size:
        levels.append(current)
        processed += int(current.size)
        targets = downstream[current]
        has_target = targets >= 0
        sources = current[has_target]
        targets = targets[has_target]
        if targets.size == 0:
            break
        unique_targets, inverse, counts = np.unique(
            targets, return_inverse=True, return_counts=True
        )
        additions = np.bincount(
            inverse, weights=accumulation[sources], minlength=unique_targets.size
        )
        accumulation[unique_targets] += additions.astype(np.float32)
        indegree[unique_targets] -= counts.astype(np.int32)
        current = unique_targets[indegree[unique_targets] == 0]

    unresolved = int(np.count_nonzero(valid_flat & (indegree > 0)))
    accumulation_2d = accumulation.reshape((height, width))
    accumulation_output = accumulation_2d.copy()
    accumulation_output[~valid] = -9999.0
    _write_raster(
        direction_dataset,
        accumulation_path,
        accumulation_output,
        gdal.GDT_Float32,
        -9999.0,
    )

    stream_mask = valid & (accumulation_2d >= max(1, int(threshold_cells)))
    stream_output = np.zeros((height, width), dtype=np.uint8)
    stream_output[stream_mask] = 1
    _write_raster(
        direction_dataset, stream_raster_path, stream_output, gdal.GDT_Byte, 0
    )
    stream_cells = np.flatnonzero(stream_mask.ravel() & (downstream >= 0))
    _write_stream_segments(
        stream_vector_path,
        direction_dataset,
        stream_cells,
        downstream,
        accumulation,
        pixel_area_m2,
    )

    if basin_path:
        basin_ids = np.zeros(total, dtype=np.int32)
        outlets = np.flatnonzero(valid_flat & (downstream < 0))
        basin_ids[outlets] = np.arange(1, outlets.size + 1, dtype=np.int32)
        for level in reversed(levels):
            targets = downstream[level]
            routed_level = targets >= 0
            basin_ids[level[routed_level]] = basin_ids[targets[routed_level]]
        basin_output = basin_ids.reshape((height, width))
        basin_output[~valid] = 0
        _write_raster(
            direction_dataset, basin_path, basin_output, gdal.GDT_Int32, 0
        )

    direction_band = None
    direction_dataset = None
    filled_band = None
    filled_dataset = None
    if feedback is not None:
        feedback.pushInfo(
            f"Native D8 hydrology created {stream_cells.size:,} stream segments."
        )
    return {
        "valid_cells": int(np.count_nonzero(valid_flat)),
        "processed_cells": processed,
        "unresolved_cells": unresolved,
        "stream_segments": int(stream_cells.size),
    }


def calculate_complete_hydrology(
    input_dem_path,
    band_number,
    filled_dem_path,
    direction_path,
    accumulation_path,
    stream_raster_path,
    stream_vector_path,
    threshold_cells,
    pixel_area_m2,
    horizontal_meters_per_unit,
    vertical_meters_per_unit,
    basin_path=None,
):
    _condition_dem(
        input_dem_path,
        band_number,
        filled_dem_path,
        direction_path,
        horizontal_meters_per_unit,
        vertical_meters_per_unit,
    )
    return calculate_native_hydrology(
        direction_path=direction_path,
        filled_dem_path=filled_dem_path,
        accumulation_path=accumulation_path,
        stream_raster_path=stream_raster_path,
        stream_vector_path=stream_vector_path,
        threshold_cells=threshold_cells,
        pixel_area_m2=pixel_area_m2,
        basin_path=basin_path,
    )


def create_contours_in_process(input_path, band_number, output_path, interval):
    """Create contour GeoPackage in the same GDAL runtime as D8 hydrology."""

    from osgeo import gdal, ogr, osr

    source = gdal.Open(input_path, gdal.GA_ReadOnly)
    if source is None:
        raise RuntimeError("Could not open DEM for contour generation.")
    source_band = source.GetRasterBand(int(band_number))
    driver = ogr.GetDriverByName("GPKG")
    if os.path.exists(output_path):
        driver.DeleteDataSource(output_path)
    destination = driver.CreateDataSource(output_path)
    spatial_ref = osr.SpatialReference()
    spatial_ref.ImportFromWkt(source.GetProjection())
    layer = destination.CreateLayer("contours", spatial_ref, ogr.wkbLineString)
    layer.CreateField(ogr.FieldDefn("ELEV", ogr.OFTReal))
    nodata = source_band.GetNoDataValue()
    options = [f"LEVEL_INTERVAL={float(interval):.12g}", "LEVEL_BASE=0", "ELEV_FIELD=0"]
    if nodata is not None:
        options.append(f"NODATA={float(nodata):.12g}")
    gdal.ContourGenerateEx(source_band, layer, options)
    layer = None
    spatial_ref = None
    destination = None
    source_band = None
    source = None


def _main():
    import argparse
    import json

    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dem-path", required=True)
    parser.add_argument("--band-number", required=True, type=int)
    parser.add_argument("--filled-dem-path", required=True)
    parser.add_argument("--direction-path", required=True)
    parser.add_argument("--accumulation-path", required=True)
    parser.add_argument("--stream-raster-path", required=True)
    parser.add_argument("--stream-vector-path", required=True)
    parser.add_argument("--threshold-cells", required=True, type=int)
    parser.add_argument("--pixel-area-m2", required=True, type=float)
    parser.add_argument("--horizontal-meters-per-unit", required=True, type=float)
    parser.add_argument("--vertical-meters-per-unit", required=True, type=float)
    parser.add_argument("--basin-path")
    options = parser.parse_args()
    summary = calculate_complete_hydrology(
        input_dem_path=options.input_dem_path,
        band_number=options.band_number,
        filled_dem_path=options.filled_dem_path,
        direction_path=options.direction_path,
        accumulation_path=options.accumulation_path,
        stream_raster_path=options.stream_raster_path,
        stream_vector_path=options.stream_vector_path,
        threshold_cells=options.threshold_cells,
        pixel_area_m2=options.pixel_area_m2,
        horizontal_meters_per_unit=options.horizontal_meters_per_unit,
        vertical_meters_per_unit=options.vertical_meters_per_unit,
        basin_path=options.basin_path,
    )
    print("TERRAIN_HYDROLOGY_RESULT=" + json.dumps(summary, separators=(",", ":")))


if __name__ == "__main__":
    _main()
