"""Create immutable, per-layout QGIS layer-style snapshots."""

from __future__ import annotations

import os

from qgis.core import QgsMapLayerStyle

from .math_utils import sanitize_prefix, unique_path
from .presets import CARTOGRAPHY_PRESETS
from .styles import (
    apply_contour_style,
    apply_dem_style,
    apply_hillshade_style,
    apply_ridge_style,
    apply_spot_elevation_style,
    apply_stream_style,
)


def _apply_pack_style(layer, key, config):
    preset = config.get("preset", "natural_earth")
    font = config.get("font_family")
    if key == "WORKING_DEM":
        apply_dem_style(layer, preset, config.get("palette_key"))
    elif key in {"HILLSHADE", "MULTI_HILLSHADE"}:
        dark = bool(CARTOGRAPHY_PRESETS.get(preset, {}).get("dark"))
        opacity = 0.45 if dark else (0.32 if key == "MULTI_HILLSHADE" else 0.38)
        apply_hillshade_style(layer, opacity)
    elif key in {"CONTOURS", "CONTOURS_SMOOTH"}:
        apply_contour_style(
            layer,
            float(config.get("contour_interval", 10.0)),
            int(config.get("index_multiplier", 5)),
            config.get("z_unit", "m"),
            preset,
            font,
        )
    elif key == "SPOT_ELEVATIONS":
        apply_spot_elevation_style(layer, preset, font)
    elif key in {"STREAMS", "STREAMS_SMOOTH"}:
        apply_stream_style(layer, preset)
    elif key == "RIDGES":
        apply_ridge_style(layer, preset)


def create_layer_style_overrides(layers, ordered_keys, config):
    """Return ``(layer-id -> style XML, warnings)`` for one layout.

    Styles are applied to temporary layer clones, so creating a layout never
    mutates the live canvas or another layout.  Unsupported provider clones
    fall back to the layer's current style rather than aborting the layout.
    """

    overrides = {}
    warnings = []
    for key in ordered_keys:
        layer = layers.get(key)
        if layer is None:
            continue
        candidate = None
        try:
            candidate = layer.clone()
            if candidate is None or not candidate.isValid():
                raise RuntimeError("layer provider could not create a valid clone")
            _apply_pack_style(candidate, key, config)
            style = QgsMapLayerStyle()
            style.readFromLayer(candidate)
            xml = style.xmlData()
            if xml:
                overrides[layer.id()] = xml
        except Exception as error:
            warnings.append(f"{key}: could not create style snapshot ({error})")
            try:
                style = QgsMapLayerStyle()
                style.readFromLayer(layer)
                xml = style.xmlData()
                if xml:
                    overrides[layer.id()] = xml
            except Exception as fallback_error:
                warnings.append(f"{key}: current style fallback failed ({fallback_error})")
        finally:
            if candidate is not None and candidate is not layer:
                candidate = None
    return overrides, tuple(warnings)


def export_style_pack_qml(layers, ordered_keys, config, output_folder):
    """Write reusable QML files for the same styles captured by a layout."""

    overrides, warnings = create_layer_style_overrides(
        layers, ordered_keys, config
    )
    id_to_key = {
        layer.id(): key for key, layer in layers.items() if layer is not None
    }
    preset = sanitize_prefix(config.get("preset", "style_pack"))
    style_folder = os.path.join(output_folder, "styles", preset)
    os.makedirs(style_folder, exist_ok=True)
    exported = {}
    for layer_id, xml in overrides.items():
        key = id_to_key.get(layer_id)
        if not key:
            continue
        path = unique_path(
            os.path.join(style_folder, f"{sanitize_prefix(key.lower())}.qml")
        )
        with open(path, "w", encoding="utf-8") as stream:
            stream.write(xml)
        exported[key] = path
    return exported, warnings
