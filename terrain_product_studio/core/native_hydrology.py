"""D8 accumulation, Strahler stream network vectorization, and Topographic Wetness Index (TWI).

Features:
- Priority-flood depression conditioning and deterministic D8 flow routing.
- Continuous multi-point polyline chaining with Strahler stream ordering.
- Rich attribute vector output (GeoPackage and GeoJSON): ORDER, ORDER_NAME, LENGTH_M, AREA_HA.
- Native Topographic Wetness Index (TWI) calculation.
"""

from __future__ import annotations

import collections
import math
import os
import numpy as np
from osgeo import gdal, ogr, osr


MAX_HYDROLOGY_CELLS = 25_000_000


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


def _order_label(order: int) -> str:
    if order <= 1:
        return "Order 1 - Headwater Stream"
    elif order == 2:
        return "Order 2 - Secondary Tributary"
    elif order == 3:
        return "Order 3 - Sub-River"
    else:
        return f"Order {order} - Major River Channel"


def _write_continuous_stream_network(
    vector_path: str,
    reference: gdal.Dataset,
    stream_mask_flat: np.ndarray,
    downstream: np.ndarray,
    accumulation: np.ndarray,
    pixel_area_m2: float,
    cell_size_m: float,
):
    """Trace continuous stream polylines, calculate Strahler order, and export to GPKG & GeoJSON."""
    width = reference.RasterXSize
    height = reference.RasterYSize
    total = width * height
    geotransform = reference.GetGeoTransform()
    projection = reference.GetProjection() or ""

    is_stream = stream_mask_flat.copy()
    stream_cells = np.flatnonzero(is_stream)
    if stream_cells.size == 0:
        return 0, 0

    # Downstream target within stream network
    stream_downstream = np.full(total, -1, dtype=np.int32)
    stream_indegree = np.zeros(total, dtype=np.int32)

    for cell in stream_cells:
        target = int(downstream[cell])
        if target >= 0 and is_stream[target]:
            stream_downstream[cell] = target
            stream_indegree[target] += 1

    # Topological order calculation for Strahler Stream Order
    strahler_order = np.ones(total, dtype=np.int32)
    # Channel heads
    current_heads = [int(c) for c in stream_cells if stream_indegree[c] == 0]

    in_degrees = stream_indegree.copy()
    incoming_orders = collections.defaultdict(list)

    queue = collections.deque(current_heads)
    while queue:
        u = queue.popleft()
        target = stream_downstream[u]
        if target >= 0:
            incoming_orders[target].append(strahler_order[u])
            in_degrees[target] -= 1
            if in_degrees[target] == 0:
                # Compute Strahler order for target
                inc = incoming_orders[target]
                if len(inc) == 1:
                    strahler_order[target] = inc[0]
                elif len(inc) >= 2:
                    max_ord = max(inc)
                    cnt = inc.count(max_ord)
                    strahler_order[target] = max_ord + 1 if cnt >= 2 else max_ord
                queue.append(target)

    # Trace continuous river reaches (from heads and confluence points down to confluences or outlets)
    # Start points for reaches:
    # 1. Channel heads (indegree == 0)
    # 2. Immediate children of confluences (indegree >= 2)
    visited_edges = set()
    reaches = []

    def trace_reach(start_cell):
        curr = start_cell
        coords = []
        acc_max = 0.0
        order_val = int(strahler_order[curr])
        
        row, col = divmod(curr, width)
        coords.append(_cell_center(geotransform, row, col))
        acc_max = max(acc_max, float(accumulation[curr]))

        while True:
            target = stream_downstream[curr]
            if target < 0:
                break
            edge = (curr, target)
            if edge in visited_edges:
                break
            visited_edges.add(edge)

            t_row, t_col = divmod(target, width)
            coords.append(_cell_center(geotransform, t_row, t_col))
            acc_max = max(acc_max, float(accumulation[target]))
            curr = target

            # If target is a confluence point (indegree >= 2), finish current reach
            if stream_indegree[target] >= 2:
                break

        if len(coords) >= 2:
            # Calculate length
            length_m = 0.0
            for i in range(len(coords) - 1):
                dx = coords[i + 1][0] - coords[i][0]
                dy = coords[i + 1][1] - coords[i][1]
                length_m += math.hypot(dx, dy)

            area_ha = acc_max * pixel_area_m2 / 10000.0
            reaches.append({
                "coords": coords,
                "order": order_val,
                "order_name": _order_label(order_val),
                "length_m": round(length_m, 2),
                "area_ha": round(area_ha, 2),
                "acc_cells": int(acc_max),
            })

    # Start traces
    for c in stream_cells:
        if stream_indegree[c] == 0:
            trace_reach(c)
        elif stream_indegree[c] >= 2:
            # Trace downstream from this confluence
            trace_reach(c)

    # Export to GeoPackage if file extension is .gpkg, else GeoJSON
    spatial_ref = osr.SpatialReference()
    if projection:
        spatial_ref.ImportFromWkt(projection)

    is_gpkg = vector_path.lower().endswith(".gpkg")
    driver_name = "GPKG" if is_gpkg else "GeoJSON"
    driver = ogr.GetDriverByName(driver_name)
    if os.path.exists(vector_path):
        driver.DeleteDataSource(vector_path)

    ds = driver.CreateDataSource(vector_path)
    layer_name = "potential_streams"
    layer = ds.CreateLayer(layer_name, spatial_ref, ogr.wkbLineString)

    # Add fields
    layer.CreateField(ogr.FieldDefn("ORDER", ogr.OFTInteger))
    
    order_name_field = ogr.FieldDefn("ORDER_NAME", ogr.OFTString)
    order_name_field.SetWidth(64)
    layer.CreateField(order_name_field)

    layer.CreateField(ogr.FieldDefn("LENGTH_M", ogr.OFTReal))
    layer.CreateField(ogr.FieldDefn("AREA_HA", ogr.OFTReal))
    layer.CreateField(ogr.FieldDefn("ACC_CELLS", ogr.OFTInteger64))

    layer.StartTransaction()
    feature_defn = layer.GetLayerDefn()
    max_order_found = 1

    for reach in reaches:
        geom = ogr.Geometry(ogr.wkbLineString)
        for x, y in reach["coords"]:
            geom.AddPoint(x, y)

        feat = ogr.Feature(feature_defn)
        feat.SetGeometry(geom)
        feat.SetField("ORDER", reach["order"])
        feat.SetField("ORDER_NAME", reach["order_name"])
        feat.SetField("LENGTH_M", reach["length_m"])
        feat.SetField("AREA_HA", reach["area_ha"])
        feat.SetField("ACC_CELLS", reach["acc_cells"])
        layer.CreateFeature(feat)
        max_order_found = max(max_order_found, reach["order"])

    layer.CommitTransaction()
    ds = None

    # Also export accompanying geojson if GPKG was written
    if is_gpkg:
        geojson_path = os.path.splitext(vector_path)[0] + ".geojson"
        try:
            gjson_driver = ogr.GetDriverByName("GeoJSON")
            if os.path.exists(geojson_path):
                gjson_driver.DeleteDataSource(geojson_path)
            gjson_ds = gjson_driver.CreateDataSource(geojson_path)
            gjson_ds.CopyLayer(layer, "potential_streams")
            gjson_ds = None
        except Exception:
            gjson_ds = None

    return len(reaches), max_order_found


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

    directions = parent_direction.copy()
    best_slope = np.zeros((height, width), dtype=np.float32)
    for code, (row_offset, column_offset) in enumerate(offsets):
        source_row = slice(max(0, -row_offset), min(height, height - row_offset))
        source_column = slice(max(0, -column_offset), min(width, width - column_offset))
        target_row = slice(max(0, row_offset), min(height, height + row_offset))
        target_column = slice(max(0, column_offset), min(width, width + column_offset))
        distance = math.hypot(row_offset * y_size_m, column_offset * x_size_m)
        slope = (
            filled[source_row, source_column] - filled[target_row, target_column]
        ) / max(distance, 1e-9)
        eligible = (
            valid[source_row, source_column]
            & valid[target_row, target_column]
            & (slope > best_slope[source_row, source_column])
            & (slope > 0.0)
        )
        best_slope[source_row, source_column][eligible] = slope[eligible]
        directions[source_row, source_column][eligible] = code

    filled_output = filled.copy()
    filled_output[~valid] = -9999.0
    _write_raster(source, filled_dem_path, filled_output, gdal.GDT_Float32, -9999.0)
    direction_output = directions.copy()
    direction_output[~valid] = -1
    _write_raster(
        source, direction_path, direction_output.astype(np.int16), gdal.GDT_Int16, -1
    )
    source_band = None
    source = None


def calculate_native_hydrology(
    direction_path,
    filled_dem_path,
    accumulation_path,
    stream_raster_path,
    stream_vector_path,
    threshold_cells,
    pixel_area_m2,
    twi_path=None,
    basin_path=None,
    feedback=None,
):
    """Compute D8 accumulation, Strahler river polylines, watershed basins, and TWI."""
    direction_dataset = gdal.Open(direction_path, gdal.GA_ReadOnly)
    filled_dataset = gdal.Open(filled_dem_path, gdal.GA_ReadOnly)
    if direction_dataset is None or filled_dataset is None:
        raise RuntimeError("Could not open conditioned hydrology inputs.")

    width = direction_dataset.RasterXSize
    height = direction_dataset.RasterYSize
    total = width * height
    direction_band = direction_dataset.GetRasterBand(1)
    filled_band = filled_dataset.GetRasterBand(1)
    directions = direction_band.ReadAsArray().astype(np.int16, copy=False)
    filled = filled_band.ReadAsArray().astype(np.float32, copy=False)

    valid = directions >= 0
    valid_flat = valid.ravel()

    downstream = np.full(total, -1, dtype=np.int32)
    offsets_by_code = {
        0: -width,
        1: -width + 1,
        2: 1,
        3: width + 1,
        4: width,
        5: width - 1,
        6: -1,
        7: -width - 1,
    }
    for code, offset in offsets_by_code.items():
        mask = valid & (directions == code)
        cells = np.flatnonzero(mask.ravel())
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

    # Potential Stream Raster
    stream_mask = valid & (accumulation_2d >= max(1, int(threshold_cells)))
    stream_output = np.zeros((height, width), dtype=np.uint8)
    stream_output[stream_mask] = 1
    _write_raster(
        direction_dataset, stream_raster_path, stream_output, gdal.GDT_Byte, 0
    )

    gt = direction_dataset.GetGeoTransform()
    cell_size_m = max(abs(gt[1]), 1.0)

    # Continuous Strahler Stream Polyline Vectorization
    num_reaches, max_order = _write_continuous_stream_network(
        stream_vector_path,
        direction_dataset,
        stream_mask.ravel(),
        downstream,
        accumulation,
        pixel_area_m2,
        cell_size_m,
    )

    # Topographic Wetness Index (TWI)
    if twi_path:
        # Calculate slope from filled DEM
        dy, dx = np.gradient(filled, abs(gt[5]), abs(gt[1]))
        slope_tan = np.clip(np.hypot(dx, dy), 0.001, 20.0)
        # Specific Catchment Area As = (acc * pixel_area_m2) / cell_size_m
        As = np.maximum((accumulation_2d * pixel_area_m2) / cell_size_m, cell_size_m)
        twi = np.zeros((height, width), dtype=np.float32)
        twi[valid] = np.log(As[valid] / slope_tan[valid])
        twi_out = twi.copy()
        twi_out[~valid] = -9999.0
        _write_raster(direction_dataset, twi_path, twi_out, gdal.GDT_Float32, -9999.0)

    # Watershed Basins
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
            f"Strahler river network created {num_reaches:,} continuous reaches up to Order {max_order}."
        )
    return {
        "valid_cells": int(np.count_nonzero(valid_flat)),
        "processed_cells": processed,
        "unresolved_cells": unresolved,
        "stream_reaches": num_reaches,
        "max_strahler_order": max_order,
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
    twi_path=None,
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
        twi_path=twi_path,
        basin_path=basin_path,
    )
