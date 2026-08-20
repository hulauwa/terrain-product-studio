"""Pure data model for cohesive cartographic style packs.

A style pack is intentionally broader than a color palette: it chooses a
layout composition, a logical layer recipe, typography, QGIS symbology and a
web-terrain color treatment together.  Keeping the model free of QGIS imports
makes it safe to validate at plugin startup and in normal unit tests.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Tuple

from .presets import CARTOGRAPHY_PRESETS


@dataclass(frozen=True)
class LayoutTemplate:
    key: str
    label: str
    description: str
    frame_style: str
    legend_position: str
    title_position: str
    show_legend: bool = True
    show_metadata: bool = True
    show_grid: bool = True
    preferred_font: str = "Arial"


@dataclass(frozen=True)
class MapStylePack:
    key: str
    label: str
    description: str
    palette: str
    preferred_font: str
    layout_template: str
    layer_recipe: str
    web_palette: str


LAYOUT_TEMPLATES: Mapping[str, LayoutTemplate] = {
    "classic_topo": LayoutTemplate(
        "classic_topo",
        "Classic topographic sheet",
        "Double neatline, marginal grid and conventional map furniture.",
        "double",
        "side",
        "top",
        preferred_font="Arial",
    ),
    "survey_sheet": LayoutTemplate(
        "survey_sheet",
        "Historic survey sheet",
        "Warm double frame, explanation block and formal centered heading.",
        "survey",
        "side",
        "center",
        preferred_font="Baskerville",
    ),
    "modern_atlas": LayoutTemplate(
        "modern_atlas",
        "Modern atlas",
        "Clean asymmetric sidebar, thin frame and contemporary typography.",
        "thin",
        "side",
        "top",
        preferred_font="Noto Sans",
    ),
    "field_sheet": LayoutTemplate(
        "field_sheet",
        "Field sheet",
        "High-contrast map with a compact bottom information strip.",
        "heavy",
        "bottom",
        "top",
        preferred_font="Arial",
    ),
    "night_presentation": LayoutTemplate(
        "night_presentation",
        "Night presentation",
        "Full dark canvas, restrained frame and horizontal lower legend.",
        "glow",
        "bottom",
        "top",
        preferred_font="Arial",
    ),
    "engineering_titleblock": LayoutTemplate(
        "engineering_titleblock",
        "Engineering title block",
        "Drafting grid with a technical title block in the lower-right corner.",
        "technical",
        "titleblock",
        "top",
        preferred_font="DejaVu Sans Mono",
    ),
    "minimal_poster": LayoutTemplate(
        "minimal_poster",
        "Minimal poster",
        "Near full-bleed map with small editorial title and no legend by default.",
        "minimal",
        "none",
        "overlay",
        show_legend=False,
        show_metadata=False,
        show_grid=False,
        preferred_font="Noto Sans",
    ),
}


_TEMPLATE_BY_PRESET = {
    "usgs_classic": "classic_topo",
    "antique_survey": "survey_sheet",
    "modern_atlas": "modern_atlas",
    "natural_earth": "modern_atlas",
    "field_grayscale": "field_sheet",
    "night_dark": "night_presentation",
    "engineering_blueprint": "engineering_titleblock",
    "minimal_contours": "minimal_poster",
}


def _build_style_packs() -> Mapping[str, MapStylePack]:
    packs = {}
    for key, preset in CARTOGRAPHY_PRESETS.items():
        packs[key] = MapStylePack(
            key=key,
            label=preset["label"],
            description=preset["description"],
            palette=preset["palette"],
            preferred_font=preset["font"],
            layout_template=_TEMPLATE_BY_PRESET.get(key, "modern_atlas"),
            layer_recipe=key,
            web_palette=preset["palette"],
        )
    return packs


STYLE_PACKS = _build_style_packs()


def style_pack(key: str) -> MapStylePack:
    """Return a valid pack, falling back to the stable default."""

    return STYLE_PACKS.get(key, STYLE_PACKS["natural_earth"])


def validate_style_packs() -> Tuple[str, ...]:
    """Return human-readable catalog errors without importing QGIS."""

    errors = []
    for key, template in LAYOUT_TEMPLATES.items():
        if not template.preferred_font.strip():
            errors.append(f"{key}: preferred layout font is empty")
    for key, pack in STYLE_PACKS.items():
        if pack.layout_template not in LAYOUT_TEMPLATES:
            errors.append(f"{key}: unknown layout template {pack.layout_template}")
        if pack.key != key:
            errors.append(f"{key}: pack key mismatch")
        if not pack.preferred_font.strip():
            errors.append(f"{key}: preferred font is empty")
    return tuple(errors)
