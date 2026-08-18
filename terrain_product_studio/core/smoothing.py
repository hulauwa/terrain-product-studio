"""Cartographic geometry smoothing for contour and river polylines.

Smoothing only ever writes a display copy (``*_smooth`` files); the raw
outputs keep their exact coordinates so analysis values are never distorted.
Chaikin corner cutting preserves the general terrain shape, and an optional
Douglas–Peucker pass removes pixel-staircase vertices before smoothing.
"""

from __future__ import annotations

import math
import os

from osgeo import ogr


def smooth_chaikin(coords, iterations: int = 2):
    """Corner cutting: every segment is replaced by two points at 25% / 75%."""

    points = [(float(x), float(y)) for x, y in coords]
    for _ in range(max(0, int(iterations))):
        if len(points) < 3:
            break
        smoothed = []
        for index in range(len(points) - 1):
            x1, y1 = points[index]
            x2, y2 = points[index + 1]
            smoothed.append((0.75 * x1 + 0.25 * x2, 0.75 * y1 + 0.25 * y2))
            smoothed.append((0.25 * x1 + 0.75 * x2, 0.25 * y1 + 0.75 * y2))
        points = smoothed
    return points


def _perpendicular_distance(point, start, end):
    x, y = point
    x1, y1 = start
    x2, y2 = end
    dx = x2 - x1
    dy = y2 - y1
    length_sq = dx * dx + dy * dy
    if length_sq <= 0:
        return math.hypot(x - x1, y - y1)
    return abs(dy * x - dx * y + x2 * y1 - y2 * x1) / math.sqrt(length_sq)


def simplify_dp(coords, tolerance: float):
    """Douglas–Peucker simplification, keeping the input point order."""

    points = [(float(x), float(y)) for x, y in coords]
    if len(points) <= 2 or tolerance <= 0:
        return points
    keep = [False] * len(points)
    keep[0] = keep[-1] = True
    stack = [(0, len(points) - 1)]
    while stack:
        start, end = stack.pop()
        if end - start < 2:
            continue
        max_distance = 0.0
        max_index = -1
        for index in range(start + 1, end):
            distance = _perpendicular_distance(points[index], points[start], points[end])
            if distance > max_distance:
                max_distance = distance
                max_index = index
        if max_distance > tolerance:
            keep[max_index] = True
            stack.append((start, max_index))
            stack.append((max_index, end))
    return [point for point, is_keep in zip(points, keep) if is_keep]


def _ring_points(geometry):
    points = []
    for index in range(geometry.GetPointCount()):
        point = geometry.GetPoint(index)
        # Returns a 3-tuple (x, y, z) for plain lines; never assume the
        # measure dimension is present.
        points.append((point[0], point[1]))
    return points


def _build_line(points, source_type, processor):
    processed = processor(points)
    if len(processed) < 2:
        return None
    is_25d = source_type in (ogr.wkbLineString25D, ogr.wkbMultiLineString25D)
    line = ogr.Geometry(ogr.wkbLineString25D if is_25d else ogr.wkbLineString)
    for x, y in processed:
        if is_25d:
            line.AddPoint(x, y, 0.0)
        else:
            line.AddPoint(x, y)
    return line


def _smooth_geometry(geometry, processor):
    """Return a smoothed copy of a line or multiline geometry (same type)."""

    geometry_type = geometry.GetGeometryType()
    # Strip the 25D flag bit so 2D and 25D variants compare equal (some
    # GDAL bindings no longer expose the ogr.wkbFlatten macro helper).
    flat_type = geometry_type & 0x7FFFFFFF
    if flat_type == ogr.wkbLineString:
        points = _ring_points(geometry)
        if len(points) < 2:
            return None
        return _build_line(points, geometry_type, processor)
    if flat_type == ogr.wkbMultiLineString:
        multi = ogr.Geometry(
            ogr.wkbMultiLineString25D
            if geometry_type == ogr.wkbMultiLineString25D
            else ogr.wkbMultiLineString
        )
        for index in range(geometry.GetGeometryCount()):
            part = geometry.GetGeometryRef(index)
            points = _ring_points(part)
            if len(points) < 2:
                continue
            line = _build_line(points, part.GetGeometryType(), processor)
            if line is not None:
                multi.AddGeometry(line)
        return multi if multi.GetGeometryCount() else None
    return None


def smooth_geometries(
    input_path: str,
    output_path: str,
    iterations: int = 2,
    simplify_tolerance: float = 0.0,
    layer_name: str | None = None,
) -> dict:
    """Copy a vector GeoPackage, smoothing and simplifying every line geometry.

    Attributes are preserved and empty geometries are dropped. Returns a
    summary dict with input/output feature counts.
    """

    source_ds = ogr.Open(input_path, 0)
    if source_ds is None:
        raise RuntimeError(f"Could not open vector for smoothing: {input_path}")
    source_layer = source_ds.GetLayer(0)
    layer_defn = source_layer.GetLayerDefn()

    if os.path.exists(output_path):
        ogr.GetDriverByName("GPKG").DeleteDataSource(output_path)
    target_ds = ogr.GetDriverByName("GPKG").CreateDataSource(output_path)
    target_layer = target_ds.CreateLayer(
        layer_name or source_layer.GetName(),
        source_layer.GetSpatialRef(),
        source_layer.GetGeomType(),
    )
    for index in range(layer_defn.GetFieldCount()):
        target_layer.CreateField(layer_defn.GetFieldDefn(index))

    def _processed(points):
        if simplify_tolerance > 0:
            points = simplify_dp(points, simplify_tolerance)
        if iterations > 0:
            points = smooth_chaikin(points, iterations)
        return points

    input_count = 0
    output_count = 0
    target_layer.StartTransaction()
    source_layer.ResetReading()
    try:
        for feature in source_layer:
            input_count += 1
            geometry = feature.GetGeometryRef()
            if geometry is None:
                continue
            new_geometry = _smooth_geometry(geometry, _processed)
            if new_geometry is None:
                continue
            new_feature = ogr.Feature(target_layer.GetLayerDefn())
            new_feature.SetGeometry(new_geometry)
            for index in range(layer_defn.GetFieldCount()):
                new_feature.SetField(index, feature.GetField(index))
            target_layer.CreateFeature(new_feature)
            output_count += 1
        target_layer.CommitTransaction()
    finally:
        # Release both datasources even on failure so the GPKG files are not
        # left locked (an uncommitted transaction rolls back on close).
        target_ds = None
        source_ds = None
    return {"input_features": input_count, "smoothed_features": output_count}
