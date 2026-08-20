"""Small curated library of one-click terrain map designs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Tuple

from .presets import CARTOGRAPHY_PRESETS, TERRAIN_PALETTES
from .style_packs import LAYOUT_TEMPLATES


@dataclass(frozen=True)
class DesignPreset:
    key: str
    label: str
    description: str
    map_style: str
    layout_template: str
    palette: str
    grid_mode: str = "map_crs"
    preview: str = ""


DESIGN_PRESETS: Mapping[str, DesignPreset] = {
    "standard_topo": DesignPreset(
        "standard_topo",
        "Standard Topographic · Recommended",
        "Simple everyday terrain sheet with natural relief, clear contours and a conventional collar.",
        "natural_earth",
        "classic_topo",
        "natural",
        "map_crs",
        "standard_topo.jpg",
    ),
    "usgs_classic": DesignPreset(
        "usgs_classic",
        "USGS Classic",
        "Ivory sheet, brown hypsography, blue hydrography and compact American topographic typography.",
        "usgs_classic",
        "classic_topo",
        "usgs_topo",
        "dual",
        "usgs_classic.jpg",
    ),
    "arctic_survey": DesignPreset(
        "arctic_survey",
        "Arctic Survey",
        "Cool ice-blue elevation colors with a clean atlas collar and restrained gray-blue furniture.",
        "modern_atlas",
        "modern_atlas",
        "arctic",
        "wgs84",
        "arctic_survey.jpg",
    ),
    "desert_recon": DesignPreset(
        "desert_recon",
        "Desert Recon",
        "Sand and burnt-earth relief on a warm survey sheet with strong hydrographic contrast.",
        "antique_survey",
        "survey_sheet",
        "desert",
        "map_crs",
        "desert_recon.jpg",
    ),
    "night_operations": DesignPreset(
        "night_operations",
        "Night Operations",
        "Dark presentation sheet with luminous cyan-gray terrain lines for screen and briefing use.",
        "night_dark",
        "night_presentation",
        "terrain_dark",
        "map_crs",
        "night_operations.jpg",
    ),
    "engineering_blueprint": DesignPreset(
        "engineering_blueprint",
        "Engineering Blueprint",
        "Technical blue sheet, monospaced type and a disciplined title block for design review.",
        "engineering_blueprint",
        "engineering_titleblock",
        "grayscale",
        "map_crs",
        "engineering_blueprint.jpg",
    ),
}

DEFAULT_DESIGN_PRESET = "standard_topo"


def design_preset(key):
    return DESIGN_PRESETS.get(key, DESIGN_PRESETS[DEFAULT_DESIGN_PRESET])


def validate_design_presets() -> Tuple[str, ...]:
    errors = []
    for key, preset in DESIGN_PRESETS.items():
        if preset.key != key:
            errors.append(f"{key}: key mismatch")
        if preset.map_style not in CARTOGRAPHY_PRESETS:
            errors.append(f"{key}: unknown map style {preset.map_style}")
        if preset.layout_template not in LAYOUT_TEMPLATES:
            errors.append(f"{key}: unknown layout {preset.layout_template}")
        if preset.palette not in TERRAIN_PALETTES:
            errors.append(f"{key}: unknown palette {preset.palette}")
        if preset.grid_mode not in {"map_crs", "wgs84", "dual", "custom"}:
            errors.append(f"{key}: unknown grid mode {preset.grid_mode}")
    return tuple(errors)
