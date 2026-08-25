"""Smart default suggestions derived from a DEM inspection report.

Pure logic (no QGIS imports at module level): ``compute_smart_defaults``
turns the dict returned by :func:`dem_info.inspect_dem_layer` into a list of
parameter suggestions with human-readable rationales.  The dock renders them
in the Assistant tab and applies them to the form.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from .math_utils import (
    river_depth_m,
    river_width_m,
    suggest_stream_threshold,
)


@dataclass
class SmartSuggestion:
    """One parameter suggestion with a human-readable rationale.

    ``value`` is usually a float (parameter value); the working-CRS
    suggestion carries its auth-id string instead.
    """

    key: str
    label: str
    value: object
    unit: str
    rationale: str


def _as_float(info: Dict, key: str, default: float) -> float:
    value = info.get(key)
    try:
        return float(value) if value is not None else default
    except (TypeError, ValueError):
        return default


def compute_smart_defaults(info: Dict) -> List[SmartSuggestion]:
    """Turn an ``inspect_dem_layer`` dict into ordered parameter suggestions.

    Every suggestion degrades gracefully: missing or degenerate metrics fall
    back to documented defaults with an honest rationale.
    """

    suggestions: List[SmartSuggestion] = []
    if not isinstance(info, dict):
        return suggestions
    relief = _as_float(info, "relief_m", 0.0)
    width_m = _as_float(info, "extent_width_m", 0.0)
    pixel_m = _as_float(info, "approx_pixel_m", 30.0)

    # --- Contour interval (reuses the existing map-scale heuristic) ---
    contour_interval = _as_float(
        info, "suggested_contour_interval", 10.0
    ) or _as_float(info, "recommended_contour_interval", 10.0)
    if relief > 0 and contour_interval > 0:
        approx_lines = max(1, int(round(relief / contour_interval)))
        suggestions.append(
            SmartSuggestion(
                key="contour_interval",
                label="Contour interval",
                value=float(contour_interval),
                unit="Z units",
                rationale=(
                    f"Relief {relief:,.0f} m across ~{max(width_m, 0) / 1000:.0f} km "
                    f"→ interval {contour_interval:g} m yields ≈{approx_lines} "
                    f"contour lines."
                ),
            )
        )

    # --- Stream extraction threshold ---
    threshold_ha, threshold_rationale = suggest_stream_threshold(pixel_m)
    suggestions.append(
        SmartSuggestion(
            key="stream_threshold",
            label="Stream threshold (min. contributing area)",
            value=float(threshold_ha),
            unit="ha",
            rationale=threshold_rationale,
        )
    )

    # --- River width/depth (default factors) ---
    headwater_width = river_width_m(threshold_ha, factor=1.0)
    headwater_depth = river_depth_m(headwater_width, factor=1.0)
    suggestions.append(
        SmartSuggestion(
            key="river_dimensions",
            label="River width/depth factors",
            value=1.0,
            unit="×",
            rationale=(
                f"At the headwater threshold ({threshold_ha:g} ha) the "
                f"Leopold/Horton relations give W ≈ {headwater_width:.1f} m, "
                f"D ≈ {headwater_depth:.1f} m — keep factor 1.0 for real "
                f"hydraulic geometry."
            ),
        )
    )

    # --- Working CRS ---
    working_crs = info.get("suggested_working_crs")
    if working_crs:
        if isinstance(working_crs, (list, tuple)) and len(working_crs) >= 1:
            auth_id = str(working_crs[0])
            reason = str(working_crs[1]) if len(working_crs) > 1 else ""
        else:
            auth_id, reason = str(working_crs), ""
        suggestions.append(
            SmartSuggestion(
                key="working_crs",
                label="Working CRS",
                value=auth_id,
                unit="",
                rationale=str(reason or "Suggested projected CRS for the analysis."),
            )
        )

    return suggestions
