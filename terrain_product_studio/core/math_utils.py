"""Pure-Python calculations shared by the UI and Processing algorithms."""

from __future__ import annotations

import math
import re
import unicodedata
from typing import Iterable, List, Sequence, Tuple


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
