"""Restyle generated outputs without re-running the pipeline.

Reads the last run's report.json, re-applies the current cartography to the
layers already loaded in the project, and regenerates only the style-bearing
artifacts: canvas renderers, reusable QML style packs and layout map style
overrides. Analytical products are never recomputed — a restyle is purely
visual, keeps raw analytical values untouched and does not modify report.json.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

# Output extensions that can be restyled on the canvas as QGIS layers.
_RESTYLABLE_EXTENSIONS = (
    ".tif", ".tiff", ".gpkg", ".geojson", ".shp",
    ".csv", ".sqlite", ".vrt",
)


@dataclass
class RestylePlan:
    """Parsed state of one report.json run, tolerant of older manifests."""

    report_path: str
    outputs: Dict[str, str] = field(default_factory=dict)
    elevation_unit: str = "m"
    contour_interval: float = 10.0
    index_multiplier: int = 5
    scene3d: Dict = field(default_factory=dict)


def parse_run_manifest(report_path):
    """Load a report.json into a :class:`RestylePlan`.

    Returns ``None`` (never raises) when the file is missing, unreadable or
    not a JSON object, so the dock can show one gentle message for a stale
    or hand-edited manifest.
    """

    if not report_path or not os.path.isfile(report_path):
        return None
    try:
        with open(report_path, "r", encoding="utf-8") as stream:
            manifest = json.load(stream)
    except (OSError, ValueError):
        return None
    if not isinstance(manifest, dict):
        return None
    outputs = manifest.get("outputs", {}) or {}
    contour_interval = float(manifest.get("contour_interval") or 10.0)
    index_interval = float(manifest.get("index_contour_interval") or 0.0)
    index_multiplier = 5
    if contour_interval > 0 and index_interval > 0:
        index_multiplier = max(1, round(index_interval / contour_interval))
    return RestylePlan(
        report_path=report_path,
        outputs={
            str(key): str(value)
            for key, value in outputs.items()
            if value
        },
        elevation_unit=str(manifest.get("elevation_unit", "m")),
        contour_interval=contour_interval,
        index_multiplier=index_multiplier,
        scene3d=manifest.get("scene3d", {}) or {},
    )


def _normalized(path):
    return os.path.normpath(os.path.realpath(str(path or "")))


def match_project_layers(project, plan):
    """Map result key -> live project layer for every output in ``plan``.

    Matching is by normalized source path, so it also works after the plugin
    was reloaded or the project was re-opened since the run.
    """

    layers = {}
    plan_sources = {
        key: _normalized(path)
        for key, path in plan.outputs.items()
        if path and path.lower().endswith(_RESTYLABLE_EXTENSIONS)
    }
    if not plan_sources:
        return layers
    for layer in project.mapLayers().values():
        source = _normalized(layer.source())
        for key, path in plan_sources.items():
            if source == path:
                layers[key] = layer
                break
    return layers


def find_plugin_layouts(project, layout_names=None):
    """Return the layouts this plugin created for the run.

    ``layout_names`` cached at build time is authoritative.  When absent
    (plugin reloaded since the run), layouts are recognised by the
    ``terrain_product_studio/...`` custom properties written at creation —
    user's own layouts are never touched.
    """

    manager = project.layoutManager()
    if manager is None:
        return []
    layouts = list(manager.layouts())
    if layout_names:
        wanted = {name for name in layout_names if name}
        return [layout for layout in layouts if layout.name() in wanted]
    return [
        layout
        for layout in layouts
        if any(
            key.startswith("terrain_product_studio/")
            for key in layout.customProperties()
        )
    ]


def restyle_outputs(
    plan,
    *,
    project=None,
    config,
    output_folder=None,
    prefix=None,
    layout_names=None,
    restyle_canvas=True,
    restyle_qml=True,
    restyle_layouts=True,
):
    """Re-apply ``config``'s cartography to an existing run's outputs.

    Returns ``(count, warnings)`` where ``count`` is the number of canvas
    layers restyled and ``warnings`` a list of human-readable notes
    (including QML/layout results).  Missing or stale products degrade to
    notes instead of raising — a restyle never aborts the pipeline.
    """

    from qgis.core import QgsProject

    from .layout_styles import (
        apply_style_overrides_to_layout,
        create_layer_style_overrides,
        export_style_pack_qml,
    )
    from .cartography_qa import inspect_layer_recipe
    from .layers import apply_result_styles

    warnings: List[str] = []
    if plan is None:
        return 0, ["No valid report.json found — nothing was restyled."]
    if project is None:
        project = QgsProject.instance()
    preset_key = str(config.get("preset", "usgs_classic"))
    palette_key = config.get("palette_key")
    font_family = config.get("font_family")
    z_unit = str(config.get("z_unit", plan.elevation_unit))
    count = 0

    layers = match_project_layers(project, plan)
    if restyle_canvas:
        apply_result_styles(
            layers,
            contour_interval=float(config.get("contour_interval", plan.contour_interval)),
            index_multiplier=int(config.get("index_multiplier", plan.index_multiplier)),
            z_unit=z_unit,
            cartography_preset=preset_key,
            font_family=font_family,
            palette_key=palette_key,
        )
        count = len(layers)
        if not layers:
            warnings.append(
                "No layers from the last run are loaded in the project — "
                "the canvas was not restyled."
            )

    folder = output_folder or os.path.dirname(plan.report_path)
    if restyle_qml and folder:
        ordered_keys, _notes = inspect_layer_recipe(layers.keys(), preset_key)
        try:
            qml_paths, qml_warnings = export_style_pack_qml(
                layers, ordered_keys, config, folder, overwrite=True
            )
            if qml_paths:
                warnings.append(
                    f"Style Pack QML ({preset_key}): " + ", ".join(qml_paths.values())
                )
            warnings.extend(f"QML: {warning}" for warning in qml_warnings)
        except Exception as error:
            warnings.append(f"QML restyle failed: {error}")

    if restyle_layouts and layers:
        ordered_keys, _notes = inspect_layer_recipe(layers.keys(), preset_key)
        overrides, layout_warnings = create_layer_style_overrides(
            layers, ordered_keys, config
        )
        warnings.extend(f"Layout: {warning}" for warning in layout_warnings)
        if overrides:
            layouts = find_plugin_layouts(project, layout_names)
            maps_updated = 0
            for layout in layouts:
                maps_updated += apply_style_overrides_to_layout(
                    project, layout, overrides
                )
            if maps_updated:
                warnings.append(
                    f"Layouts: {maps_updated} map item(s) updated in "
                    + ", ".join(layout.name() for layout in layouts)
                )
            else:
                warnings.append(
                    "No plugin layout found — open the Layout Designer to "
                    "confirm, or rebuild the layout from the Layout tab."
                )

    return count, warnings
