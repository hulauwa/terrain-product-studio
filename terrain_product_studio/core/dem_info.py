"""DEM inspection routines which depend on the QGIS runtime."""

from __future__ import annotations

from typing import Any, Dict, Tuple

from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsCsException,
    QgsPointXY,
    QgsProject,
)

from .math_utils import estimate_output_bytes, human_bytes, nice_interval, utm_epsg_for_lon_lat
from .qgis_compat import all_raster_statistics_flag


def _robust_range(layer, band: int, fallback: Tuple[float, float]) -> Tuple[float, float]:
    provider = layer.dataProvider()
    try:
        low, high = provider.cumulativeCut(band, 0.02, 0.98, layer.extent(), 250000)
        if low < high:
            return float(low), float(high)
    except (AttributeError, TypeError, RuntimeError):
        pass
    return fallback


def suggested_working_crs(layer) -> Tuple[str, str]:
    """Return an auth id and explanation for projected terrain processing."""

    crs = layer.crs()
    if not crs.isValid():
        return "", "Input DEM has no valid CRS."
    if not crs.isGeographic():
        return crs.authid() or crs.toWkt(), "Input DEM already uses a projected CRS."

    center = QgsPointXY(layer.extent().center())
    wgs84 = QgsCoordinateReferenceSystem("EPSG:4326")
    try:
        if crs != wgs84:
            transform = QgsCoordinateTransform(crs, wgs84, QgsProject.instance())
            center = transform.transform(center)
    except QgsCsException:
        return "", "Could not transform the DEM center to WGS 84."

    epsg = utm_epsg_for_lon_lat(center.x(), center.y())
    return f"EPSG:{epsg}", "A local WGS 84 UTM CRS was selected from the DEM center."


def inspect_dem_layer(layer, band: int = 1, raster_outputs: int = 8) -> Dict[str, Any]:
    """Inspect a QGIS raster layer and return JSON-serializable metadata."""

    if layer is None or not layer.isValid():
        raise ValueError("The DEM layer is missing or invalid.")
    if band < 1 or band > layer.bandCount():
        raise ValueError(f"Band {band} is outside the raster band range.")

    provider = layer.dataProvider()
    stats = provider.bandStatistics(
        band,
        all_raster_statistics_flag(),
        layer.extent(),
        250000,
    )
    minimum = float(stats.minimumValue)
    maximum = float(stats.maximumValue)
    robust_minimum, robust_maximum = _robust_range(layer, band, (minimum, maximum))
    recommended = nice_interval(robust_maximum - robust_minimum)

    width = int(layer.width())
    height = int(layer.height())
    extent = layer.extent()
    pixel_x = abs(float(extent.width()) / width) if width else 0.0
    pixel_y = abs(float(extent.height()) / height) if height else 0.0

    crs = layer.crs()
    crs_name = crs.authid() or crs.description() if crs.isValid() else "Unknown"
    working_crs, working_reason = suggested_working_crs(layer)
    has_nodata = False
    nodata_value = None
    try:
        has_nodata = bool(provider.sourceHasNoDataValue(band))
        if has_nodata:
            nodata_value = float(provider.sourceNoDataValue(band))
    except (AttributeError, TypeError, ValueError):
        pass

    warnings = []
    if not crs.isValid():
        warnings.append("DEM has no valid CRS; terrain derivatives cannot be trusted.")
    elif crs.isGeographic():
        warnings.append("DEM uses angular coordinates and will be reprojected before processing.")
    if layer.bandCount() > 1:
        warnings.append(f"Raster has {layer.bandCount()} bands; verify that band {band} is elevation.")
    if not has_nodata:
        warnings.append("The source does not declare a NoData value; inspect edge/background pixels.")
    if pixel_x and pixel_y and abs(pixel_x - pixel_y) / max(pixel_x, pixel_y) > 0.01:
        warnings.append("Pixels are not square; derivatives may be directionally biased.")
    if minimum == maximum:
        warnings.append("The selected band has no elevation range.")

    estimate = estimate_output_bytes(width, height, raster_outputs)
    return {
        "name": layer.name(),
        "source": layer.source(),
        "band": band,
        "bands": int(layer.bandCount()),
        "width": width,
        "height": height,
        "cells": width * height,
        "pixel_size_x": pixel_x,
        "pixel_size_y": pixel_y,
        "crs": crs_name,
        "is_geographic": bool(crs.isGeographic()) if crs.isValid() else None,
        "suggested_working_crs": working_crs,
        "working_crs_reason": working_reason,
        "minimum": minimum,
        "maximum": maximum,
        "robust_minimum": robust_minimum,
        "robust_maximum": robust_maximum,
        "recommended_contour_interval": recommended,
        "has_nodata": has_nodata,
        "nodata": nodata_value,
        "estimated_output_bytes": estimate,
        "estimated_output_size": human_bytes(estimate),
        "warnings": warnings,
    }


def format_dem_report(info: Dict[str, Any]) -> str:
    """Create a concise, human-readable inspection report."""

    nodata = info["nodata"] if info["has_nodata"] else "not declared"
    lines = [
        f"DEM: {info['name']}",
        f"CRS: {info['crs']}",
        f"Working CRS: {info['suggested_working_crs'] or 'not available'}",
        f"Raster: {info['width']:,} × {info['height']:,} pixels · band {info['band']}/{info['bands']}",
        f"Pixel: {info['pixel_size_x']:.6g} × {info['pixel_size_y']:.6g}",
        f"Elevation: {info['minimum']:.3f} to {info['maximum']:.3f}",
        f"Robust 2–98% range: {info['robust_minimum']:.3f} to {info['robust_maximum']:.3f}",
        f"NoData: {nodata}",
        f"Suggested contour interval: {info['recommended_contour_interval']:g}",
        f"Estimated raster output: {info['estimated_output_size']}",
    ]
    if info["warnings"]:
        lines.append("")
        lines.append("Warnings:")
        lines.extend(f"• {warning}" for warning in info["warnings"])
    else:
        lines.extend(("", "No blocking issue was detected."))
    return "\n".join(lines)
