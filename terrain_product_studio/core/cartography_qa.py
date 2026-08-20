"""Small, explainable preflight checks for print and web terrain outputs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping, Tuple

from .map_recipes import resolve_recipe_keys
from .presets import CARTOGRAPHY_PRESETS, TERRAIN_PALETTES
from .style_packs import LAYOUT_TEMPLATES


@dataclass(frozen=True)
class QaFinding:
    level: str
    message: str
    fix: str = ""


def inspect_layer_recipe(available: Iterable[str], preset_key: str):
    """Explain chosen layer variants and hidden raw/smooth alternatives."""

    available = set(available)
    selected = resolve_recipe_keys(available, preset_key, target="layout")
    notes = []
    for raw, smooth, label in (
        ("CONTOURS", "CONTOURS_SMOOTH", "Contours"),
        ("STREAMS", "STREAMS_SMOOTH", "Streams"),
    ):
        if smooth in available:
            notes.append(f"{label}: using smoothed layer; raw layer stays available but hidden")
        elif raw in available:
            notes.append(f"{label}: using raw layer because no smoothed output is available")
    return selected, tuple(notes)


def validate_layout_config(
    config: Mapping,
    available_layers: Iterable[str],
    *,
    font_substituted: bool = False,
) -> Tuple[QaFinding, ...]:
    findings = []
    available = set(available_layers)
    dpi = int(config.get("dpi", 300))
    if dpi < 200:
        findings.append(QaFinding("warning", "Export resolution is below 200 dpi.", "Use 300 dpi for print."))
    if dpi > 600:
        findings.append(QaFinding("info", "Very high DPI can make layout export slow and memory-heavy.", "Use 300–600 dpi unless a printer requires more."))
    if font_substituted:
        findings.append(QaFinding("warning", "The requested font is not installed.", "Review the resolved fallback font before export."))
    if not ({"WORKING_DEM", "COLOR_RELIEF"} & available):
        findings.append(QaFinding("warning", "No DEM basemap is available.", "Load the working DEM or enable the optional RGB compatibility raster."))
    if "CONTOURS_SMOOTH" in available and "CONTOURS" not in available:
        findings.append(QaFinding("info", "Only the smoothed contour copy is available; analytical raw contours are missing."))
    if not str(config.get("title", "")).strip():
        findings.append(QaFinding("warning", "Map title is empty.", "Enter a concise title."))
    elif len(str(config.get("title", "")).strip()) > 70:
        findings.append(
            QaFinding(
                "warning",
                "Map title is too long for the reserved title zone.",
                "Keep the title under 70 characters and move detail to the subtitle.",
            )
        )
    template_key = str(config.get("layout_template", "classic_topo"))
    if template_key not in LAYOUT_TEMPLATES:
        findings.append(
            QaFinding(
                "warning",
                "The selected layout template is unavailable.",
                "Choose one of the installed layout templates.",
            )
        )
    palette = TERRAIN_PALETTES.get(str(config.get("palette_key", "")), {})
    preset = CARTOGRAPHY_PRESETS.get(str(config.get("preset", "")), {})
    if palette.get("dark") and not preset.get("dark"):
        findings.append(
            QaFinding(
                "info",
                "A dark elevation palette is paired with a light map style.",
                "This is allowed; review contour and label contrast before export.",
            )
        )
    if not findings:
        findings.append(QaFinding("ready", "Layout is ready to generate."))
    return tuple(findings)
