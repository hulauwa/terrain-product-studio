"""Build transparent, JSON-serializable run provenance and assumptions."""

from __future__ import annotations

from typing import Iterable, Mapping, Optional, Sequence


def analytical_assumptions(
    selected_products: Iterable[str],
    *,
    accumulation_supplied: bool,
    smoothing_iterations: int,
):
    """Return explicit method/fitness notes for the selected derivatives."""

    selected = set(selected_products)
    notes = [
        {
            "scope": "terrain derivatives",
            "method": "Raster derivatives are calculated in the metric working CRS.",
            "fitness_note": "Results inherit DEM resolution, vertical accuracy and NoData quality.",
        },
        {
            "scope": "cartography",
            "method": "Display ranges use the robust 2nd–98th percentiles.",
            "fitness_note": "This changes visualization only; analytical raster values are preserved.",
        },
    ]
    if selected & {"LANDSLIDE_HAZARD", "SPI", "STI", "MULTIHAZARD"}:
        notes.append(
            {
                "scope": "flow-dependent products",
                "method": (
                    "A supplied flow-accumulation raster is used."
                    if accumulation_supplied
                    else "Slope is used as a temporary accumulation proxy."
                ),
                "fitness_note": (
                    "Suitable for the configured terrain-only screening workflow."
                    if accumulation_supplied
                    else "Screening only; run hydrology first for hydrologically valid results."
                ),
            }
        )
    if "SUITABILITY" in selected:
        notes.append(
            {
                "scope": "construction suitability",
                "method": "Classes are derived from slope thresholds only.",
                "fitness_note": "Not a substitute for geology, soils, drainage or geotechnical investigation.",
            }
        )
    if "LANDSLIDE_HAZARD" in selected:
        notes.append(
            {
                "scope": "landslide hazard",
                "method": "Terrain slope and flow convergence form a relative susceptibility index.",
                "fitness_note": "It is a terrain screening product, not a calibrated probability forecast.",
            }
        )
    if "GEOMORPHON" in selected:
        notes.append(
            {
                "scope": "geomorphon",
                "method": "Terrain forms are approximated from the configured search radius and tolerance.",
                "fitness_note": "Class boundaries are scale-sensitive; review parameters against DEM resolution.",
            }
        )
    if smoothing_iterations > 0:
        notes.append(
            {
                "scope": "vector smoothing",
                "method": f"Cartographic copies use {smoothing_iterations} smoothing iteration(s).",
                "fitness_note": "Smoothed lines are for display; raw vectors remain the analytical source.",
            }
        )
    return notes


def build_run_provenance(
    source_info: Mapping,
    *,
    source_path: str,
    source_band: int,
    source_crs: str,
    working_crs: str,
    auto_reproject: bool,
    compression: str,
    clip_extent: Optional[Sequence[float]],
    smoothing_iterations: int,
    simplify_tolerance: float,
):
    """Describe source identity, resolution, CRS and preprocessing choices."""

    return {
        "source_dem": {
            "path": source_path,
            "band": int(source_band),
            "dimensions_pixels": [
                int(source_info.get("width", 0)),
                int(source_info.get("height", 0)),
            ],
            "pixel_resolution": [
                float(source_info.get("pixel_size_x", 0.0)),
                float(source_info.get("pixel_size_y", 0.0)),
            ],
            "nodata_declared": bool(source_info.get("has_nodata")),
            "nodata_value": source_info.get("nodata"),
        },
        "crs": {
            "source": source_crs,
            "working": working_crs,
            "auto_reproject_enabled": bool(auto_reproject),
            "reprojected": source_crs != working_crs,
        },
        "preprocessing": {
            "reprojection_resampling": (
                "bilinear" if source_crs != working_crs else "not applied"
            ),
            "clip_extent_working_crs_xmin_ymin_xmax_ymax": (
                list(clip_extent) if clip_extent else None
            ),
            "raster_compression": compression,
            "vector_smoothing_iterations": int(smoothing_iterations),
            "vector_simplify_tolerance_map_units": float(simplify_tolerance),
            "raw_vectors_retained": True,
        },
    }
