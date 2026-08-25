"""Pure-Python calculations shared by the UI and Processing algorithms."""

from __future__ import annotations

import math
import re
import unicodedata
from typing import List, Sequence, Tuple


NICE_STEPS: Tuple[float, ...] = (1.0, 2.0, 2.5, 5.0, 10.0)


def nice_interval(relief: float, desired_intervals: int = 30) -> float:
    """Return a readable contour interval which does not exceed the target density.

    ``relief`` and the return value use the DEM vertical unit.  The result follows
    the familiar 1, 2, 2.5, 5, 10 sequence at any power of ten.
    """

    if not math.isfinite(relief) or relief <= 0:
        return 1.0
    desired_intervals = max(1, int(desired_intervals))
    raw = relief / desired_intervals
    exponent = math.floor(math.log10(raw))
    scale = 10.0**exponent
    normalized = raw / scale
    for step in NICE_STEPS:
        if normalized <= step:
            return float(step * scale)
    return float(10.0 * scale)


def index_interval(minor_interval: float, multiplier: int = 5) -> float:
    """Return the index-contour interval."""

    if minor_interval <= 0:
        raise ValueError("minor_interval must be positive")
    return float(minor_interval * max(1, int(multiplier)))


STANDARD_INTERVALS: Tuple[float, ...] = (
    1.0, 2.0, 2.5, 5.0, 10.0, 20.0, 25.0, 50.0, 100.0, 200.0, 250.0, 500.0, 1000.0,
)


def snap_interval(value: float) -> float:
    """Round a contour interval up to the nearest standard cartographic step."""

    if not math.isfinite(value) or value <= 0:
        return 1.0
    for step in STANDARD_INTERVALS:
        if value <= step:
            return float(step)
    exponent = math.floor(math.log10(value))
    scale = 10.0**exponent
    return float(math.ceil(value / scale) * scale)


def suggest_contour_interval(
    relief: float,
    extent_width_m: float,
    paper_width_m: float = 0.297,
    desired_intervals: int = 25,
) -> float:
    """Suggest a publication contour interval from relief and AOI map scale.

    Small AOIs (large map scale, e.g. a town) can carry many contour lines;
    regional maps (small scale, e.g. a province) must thin them out to stay
    legible. The result snaps to a standard cartographic step so the interval
    reads naturally (1, 2, 2.5, 5, 10, 20, 25, 50 m ...).
    """

    scale = extent_width_m / max(paper_width_m, 0.001)
    if scale < 20000:
        target = max(1, int(desired_intervals))
    elif scale < 50000:
        target = 20
    elif scale < 150000:
        target = 15
    elif scale < 400000:
        target = 10
    else:
        target = 8
    return snap_interval(nice_interval(relief, target))


def suggest_stream_threshold(
    pixel_size_m: float,
    target_stream_density: float = 0.035,
    min_ha: float = 0.5,
    max_ha: float = 250.0,
) -> Tuple[float, str]:
    """Suggest a minimum contributing area (ha) for stream extraction.

    The stream-cell fraction decays as the threshold grows (drainage power
    law), so the suggestion keeps stream cells near a target fraction of the
    DEM, scaled by pixel size: fine pixels need a larger cell threshold so
    LiDAR-scale rill noise is suppressed; coarse pixels need a larger area
    threshold so only real channels appear. Returns ``(ha, rationale)``.
    """

    pixel = max(float(pixel_size_m), 0.0)
    if pixel <= 0 or not math.isfinite(pixel):
        return float(min_ha), "Pixel size unavailable; using the minimum threshold."
    density_frac = min(
        0.08,
        max(0.01, target_stream_density * math.sqrt(10.0 / max(pixel, 1.0))),
    )
    threshold_cells = max(1, int(round(1.0 / density_frac)))
    ha = threshold_cells * pixel * pixel / 10000.0
    ha = min(max(ha, min_ha), max_ha)
    rationale = (
        f"{pixel:g} m resolution: {ha:g} ha minimum (≈{threshold_cells:,} "
        f"contributing cells) to keep streams legible without rill noise."
    )
    return float(ha), rationale


def river_width_m(
    area_ha: float,
    factor: float = 1.0,
    clamp_min: float = 0.8,
    clamp_max: float = 400.0,
) -> float:
    """Bankfull river width from contributing area (Leopold/Horton scaling).

    ``W = 3.0 * sqrt(A_km2)`` metres — the classic downstream hydraulic
    geometry relation, scaled by ``factor`` and clamped so tiny headwaters
    stay visible and huge basins do not overflow the map.
    """

    if not math.isfinite(area_ha) or area_ha <= 0:
        return float(clamp_min)
    area_km2 = float(area_ha) / 100.0
    width = 3.0 * math.sqrt(area_km2) * max(float(factor), 0.0)
    return float(min(max(width, clamp_min), clamp_max))


def river_depth_m(
    width_m: float,
    factor: float = 1.0,
    clamp_min: float = 0.3,
    clamp_max: float = 40.0,
) -> float:
    """Mean river depth from bankfull width (power law).

    ``D = 0.55 * W**0.6`` metres, scaled by ``factor`` and clamped so very
    small channels remain representable.
    """

    if not math.isfinite(width_m) or width_m <= 0:
        return float(clamp_min)
    depth = 0.55 * float(width_m) ** 0.6 * max(float(factor), 0.0)
    return float(min(max(depth, clamp_min), clamp_max))


def suggest_vertical_exaggeration(
    relief_m: float,
    extent_width_m: float,
    target_fraction: float = 0.12,
) -> float:
    """Suggest a display vertical exaggeration from terrain relief.

    The heuristic aims for apparent relief ≈ 12% of the map width, so peaks,
    valleys and ridges are clearly visible without being distorted, and
    clamps to a sensible [0.5, 10.0] range. Returns 1.0 for degenerate input.
    """

    if (
        not math.isfinite(relief_m)
        or not math.isfinite(extent_width_m)
        or relief_m <= 0
        or extent_width_m <= 0
    ):
        return 1.0
    exag = float(target_fraction) * float(extent_width_m) / float(relief_m)
    return float(round(min(max(exag, 0.5), 10.0), 1))


def utm_epsg_for_lon_lat(longitude: float, latitude: float) -> int:
    """Return a WGS 84 UTM EPSG code for a longitude/latitude position."""

    if not (-180.0 <= longitude <= 180.0 and -90.0 <= latitude <= 90.0):
        raise ValueError("longitude/latitude is outside the valid range")
    zone = min(60, max(1, int(math.floor((longitude + 180.0) / 6.0)) + 1))
    return (32600 if latitude >= 0 else 32700) + zone


def sanitize_prefix(value: str, fallback: str = "terrain") -> str:
    """Create a portable, stable filename prefix from user text."""

    normalized = unicodedata.normalize("NFKD", (value or "").replace("Đ", "D").replace("đ", "d"))
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "_", ascii_value).strip("_-").lower()
    cleaned = re.sub(r"_+", "_", cleaned)
    return cleaned[:64] or fallback


def interpolate_color_stops(
    minimum: float,
    maximum: float,
    palette: Sequence[Tuple[float, int, int, int]],
) -> List[Tuple[float, int, int, int]]:
    """Turn percentage-based RGB stops into absolute elevation stops."""

    if not palette:
        raise ValueError("palette cannot be empty")
    if not (math.isfinite(minimum) and math.isfinite(maximum)):
        raise ValueError("minimum and maximum must be finite")
    if maximum <= minimum:
        maximum = minimum + 1.0
    span = maximum - minimum
    return [
        (minimum + span * float(position), int(red), int(green), int(blue))
        for position, red, green, blue in palette
    ]


def human_bytes(value: float) -> str:
    """Format a byte count for UI reports."""

    amount = max(0.0, float(value))
    units = ("B", "KB", "MB", "GB", "TB")
    for unit in units:
        if amount < 1024.0 or unit == units[-1]:
            precision = 0 if unit == "B" else 1
            return f"{amount:.{precision}f} {unit}"
        amount /= 1024.0
    return f"{amount:.1f} TB"


def estimate_output_bytes(
    width: int,
    height: int,
    raster_count: int,
    average_bytes_per_pixel: float = 3.0,
    compression_factor: float = 0.65,
) -> int:
    """Estimate disk usage; deliberately approximate but useful before a run."""

    cells = max(0, int(width)) * max(0, int(height))
    count = max(0, int(raster_count))
    return int(cells * count * max(0.0, average_bytes_per_pixel) * max(0.0, compression_factor))


def unique_path(path: str) -> str:
    """Return ``path`` or a numbered sibling without overwriting existing data."""

    import os

    if not os.path.exists(path):
        return path
    stem, extension = os.path.splitext(path)
    counter = 2
    while True:
        candidate = f"{stem}_{counter}{extension}"
        if not os.path.exists(candidate):
            return candidate
        counter += 1
