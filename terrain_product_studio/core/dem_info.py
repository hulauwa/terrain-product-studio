"""DEM inspection routines which depend on the QGIS runtime."""

from __future__ import annotations

import math
from typing import Any, Dict, Tuple

from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsCsException,
    QgsPointXY,
    QgsProject,
)

from .math_utils import (
    estimate_output_bytes,
    human_bytes,
    nice_interval,
    suggest_contour_interval,
    utm_epsg_for_lon_lat,
)
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

    # Map-scale intelligence from the AOI footprint: extent width converted to
    # metres (approximate 111.32 km per degree at the central latitude for
    # geographic CRSs; projected CRSs are assumed to use metre units).
    if crs.isValid() and crs.isGeographic():
        mid_latitude = (extent.yMinimum() + extent.yMaximum()) / 2.0
        extent_width_m = abs(extent.width()) * 111320.0 * math.cos(math.radians(mid_latitude))
    else:
        extent_width_m = abs(extent.width())
    estimated_scale = extent_width_m / 0.297  # A4 landscape reference width
    suggested_interval = suggest_contour_interval(
        robust_maximum - robust_minimum, extent_width_m
    )

    # Scale-Aware Intelligence Metrics
    # Estimate pixel size in meters
    approx_px_m = pixel_x if not crs.isGeographic() else pixel_x * 111320.0
    if approx_px_m <= 3.0:
        rec_scale = "1:5,000 – 1:10,000 (Detailed Engineering / Site Plan)"
        rec_contour = 2.5 if (robust_maximum - robust_minimum) < 100 else 5.0
        rec_density = "25 – 40 points/km²"
    elif approx_px_m <= 8.0:
        rec_scale = "1:10,000 – 1:25,000 (Large-Scale Topographic Base)"
        rec_contour = 5.0 if (robust_maximum - robust_minimum) < 200 else 10.0
        rec_density = "15 – 25 points/km²"
    elif approx_px_m <= 15.0:
        rec_scale = "1:25,000 – 1:50,000 (Standard Regional Topography)"
        rec_contour = 10.0 if (robust_maximum - robust_minimum) < 500 else 20.0
        rec_density = "8 – 15 points/km²"
    elif approx_px_m <= 35.0:
        rec_scale = "1:50,000 – 1:100,000 (Regional Master Planning)"
        rec_contour = 20.0 if (robust_maximum - robust_minimum) < 1000 else 50.0
        rec_density = "4 – 8 points/km²"
    else:
        rec_scale = "1:100,000 – 1:250,000 (National / Synoptic Overview)"
        rec_contour = 50.0 if (robust_maximum - robust_minimum) < 2000 else 100.0
        rec_density = "1 – 3 points/km²"

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
        "approx_pixel_m": approx_px_m,
        "recommended_map_scale": rec_scale,
        "recommended_contour_interval": recommended or rec_contour,
        "suggested_contour_interval": suggested_interval,
        "estimated_map_scale": int(estimated_scale),
        "recommended_peak_density": rec_density,
        "crs": crs_name,
        "is_geographic": bool(crs.isGeographic()) if crs.isValid() else None,
        "suggested_working_crs": working_crs,
        "working_crs_reason": working_reason,
        "minimum": minimum,
        "maximum": maximum,
        "robust_minimum": robust_minimum,
        "robust_maximum": robust_maximum,
        "has_nodata": has_nodata,
        "nodata": nodata_value,
        "estimated_output_bytes": estimate,
        "estimated_output_size": human_bytes(estimate),
        "warnings": warnings,
    }


def format_dem_report(info: Dict[str, Any]) -> str:
    """Create a concise, human-readable inspection report with scale intelligence."""

    nodata = info["nodata"] if info["has_nodata"] else "not declared"
    lines = [
        f"DEM: {info['name']}",
        f"CRS: {info['crs']}",
        f"Working CRS: {info['suggested_working_crs'] or 'not available'}",
        f"Raster Size: {info['width']:,} × {info['height']:,} pixels · band {info['band']}/{info['bands']}",
        f"Pixel Resolution: {info['pixel_size_x']:.6g} × {info['pixel_size_y']:.6g} (~{info.get('approx_pixel_m', 0):.1f}m)",
        f"Elevation Range: {info['minimum']:.2f} m → {info['maximum']:.2f} m (Relief: {info['maximum'] - info['minimum']:.2f} m)",
        f"Robust 2–98% Range: {info['robust_minimum']:.2f} m → {info['robust_maximum']:.2f} m",
        f"NoData: {nodata}",
        f"Estimated Output Size: {info['estimated_output_size']}",
        "",
        "📐 SCALE & CARTOGRAPHY RECOMMENDATIONS:",
        f"• Recommended Map Scale: {info.get('recommended_map_scale', 'Auto')}",
        f"• Recommended Contour Interval: {info['recommended_contour_interval']:g} m (Index: {info['recommended_contour_interval']*5:g} m)",
        f"• Spot Elevation Density: {info.get('recommended_peak_density', 'Standard')}",
    ]
    if info["warnings"]:
        lines.append("")
        lines.append("Warnings:")
        lines.extend(f"• {warning}" for warning in info["warnings"])
    else:
        lines.extend(("", "No blocking issue was detected."))
    return "\n".join(lines)

