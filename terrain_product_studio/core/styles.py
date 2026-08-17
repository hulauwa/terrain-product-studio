"""QGIS renderer and labeling helpers for generated products."""

from __future__ import annotations

from qgis.PyQt.QtGui import QColor, QFont, QPainter
from qgis.core import (
    QgsColorRampShader,
    QgsContrastEnhancement,
    QgsLineSymbol,
    QgsPalLayerSettings,
    QgsRasterShader,
    QgsRuleBasedRenderer,
    QgsSingleSymbolRenderer,
    QgsSingleBandGrayRenderer,
    QgsSingleBandPseudoColorRenderer,
    QgsTextBufferSettings,
    QgsTextFormat,
    QgsUnitTypes,
    QgsVectorLayerSimpleLabeling,
)

from .presets import ASPECT_CLASSES, CARTOGRAPHY_PRESETS, SLOPE_CLASSES
from .qgis_compat import all_raster_statistics_flag


def _stats(layer):
    statistics = layer.dataProvider().bandStatistics(
        1,
        all_raster_statistics_flag(),
        layer.extent(),
        250000,
    )
    return float(statistics.minimumValue), float(statistics.maximumValue)


def _pseudocolor(layer, items, discrete=False):
    ramp = QgsColorRampShader()
    ramp.setColorRampType(QgsColorRampShader.Discrete if discrete else QgsColorRampShader.Interpolated)
    ramp.setColorRampItemList(
        [
            QgsColorRampShader.ColorRampItem(float(value), QColor(color), str(label))
            for value, color, label in items
        ]
    )
    shader = QgsRasterShader()
    shader.setRasterShaderFunction(ramp)
    renderer = QgsSingleBandPseudoColorRenderer(layer.dataProvider(), 1, shader)
    layer.setRenderer(renderer)
    layer.triggerRepaint()


def apply_hillshade_style(layer, opacity=0.36):
    renderer = QgsSingleBandGrayRenderer(layer.dataProvider(), 1)
    enhancement = QgsContrastEnhancement(layer.dataProvider().dataType(1))
    enhancement.setMinimumValue(1.0)
    enhancement.setMaximumValue(254.0)
    enhancement.setContrastEnhancementAlgorithm(QgsContrastEnhancement.StretchToMinimumMaximum)
    renderer.setContrastEnhancement(enhancement)
    layer.setRenderer(renderer)
    layer.setOpacity(float(opacity))
    try:
        multiply_mode = QPainter.CompositionMode_Multiply
    except AttributeError:  # Qt 6 scoped enum used by QGIS 4
        multiply_mode = QPainter.CompositionMode.CompositionMode_Multiply
    layer.setBlendMode(multiply_mode)
    layer.triggerRepaint()


def apply_slope_style(layer):
    _pseudocolor(layer, SLOPE_CLASSES, discrete=True)


def apply_aspect_style(layer):
    _pseudocolor(layer, ASPECT_CLASSES, discrete=True)


def apply_tpi_style(layer):
    minimum, maximum = _stats(layer)
    extent = max(abs(minimum), abs(maximum), 1e-9)
    _pseudocolor(
        layer,
        (
            (-extent, "#285078", "Valley / negative"),
            (-extent * 0.35, "#8db6c7", "Lower position"),
            (0.0, "#f5f2df", "Near mean elevation"),
            (extent * 0.35, "#d7a46d", "Upper position"),
            (extent, "#7f3b32", "Ridge / positive"),
        ),
    )


def apply_ruggedness_style(layer):
    minimum, maximum = _stats(layer)
    span = max(maximum - minimum, 1e-9)
    _pseudocolor(
        layer,
        (
            (minimum, "#edf3e5", "Low"),
            (minimum + span * 0.25, "#c8d6a5", "Low–moderate"),
            (minimum + span * 0.50, "#d9b36c", "Moderate"),
            (minimum + span * 0.75, "#bf704e", "High"),
            (maximum, "#713c3f", "Very high"),
        ),
    )


def _cartography_preset(preset_key):
    return CARTOGRAPHY_PRESETS.get(preset_key, CARTOGRAPHY_PRESETS["usgs_classic"])


def apply_contour_style(
    layer,
    minor_interval,
    index_multiplier=5,
    z_unit="m",
    preset_key="usgs_classic",
    font_family=None,
):
    """Apply 3-tier (minor, index, master) USGS-styled contour symbology and labels."""
    preset = _cartography_preset(preset_key)
    index = float(minor_interval) * max(1, int(index_multiplier))
    master = index * 2.0
    
    tol_index = max(abs(index) * 1e-7, 1e-9)
    tol_master = max(abs(master) * 1e-7, 1e-9)
    
    index_expr = f'abs("ELEV" - round("ELEV" / {index:.12g}) * {index:.12g}) <= {tol_index:.12g}'
    master_expr = f'abs("ELEV" - round("ELEV" / {master:.12g}) * {master:.12g}) <= {tol_master:.12g}'
    minor_expr = f"NOT ({index_expr})"
    
    master_color = preset.get("contour_master", preset["contour_index"])
    
    root = QgsRuleBasedRenderer.Rule(None)
    
    minor_symbol = QgsLineSymbol.createSimple(
        {"color": preset["contour_minor"], "width": "0.12", "capstyle": "round", "joinstyle": "round"}
    )
    index_symbol = QgsLineSymbol.createSimple(
        {"color": preset["contour_index"], "width": "0.30", "capstyle": "round", "joinstyle": "round"}
    )
    master_symbol = QgsLineSymbol.createSimple(
        {"color": master_color, "width": "0.48", "capstyle": "round", "joinstyle": "round"}
    )
    
    root.appendChild(
        QgsRuleBasedRenderer.Rule(
            minor_symbol,
            filterExp=minor_expr,
            label=f"Minor contours · {minor_interval:g} {z_unit}",
        )
    )
    root.appendChild(
        QgsRuleBasedRenderer.Rule(
            index_symbol,
            filterExp=f"({index_expr}) AND NOT ({master_expr})",
            label=f"Index contours · {index:g} {z_unit}",
        )
    )
    root.appendChild(
        QgsRuleBasedRenderer.Rule(
            master_symbol,
            filterExp=master_expr,
            label=f"Master contours · {master:g} {z_unit}",
        )
    )
    layer.setRenderer(QgsRuleBasedRenderer(root))

    # USGS Italic font styling for contour labels
    font = QFont(font_family or preset["font"])
    font.setItalic(True)
    
    text_format = QgsTextFormat()
    text_format.setFont(font)
    text_format.setSize(7.5)
    text_format.setColor(QColor(preset["contour_label"]))
    
    buffer = QgsTextBufferSettings()
    buffer.setEnabled(True)
    buffer.setSize(0.9)
    paper = QColor(preset["paper"])
    paper.setAlpha(225)
    buffer.setColor(paper)
    text_format.setBuffer(buffer)

    labels = QgsPalLayerSettings()
    labels.enabled = True
    labels.placement = QgsPalLayerSettings.Line
    labels.isExpression = True
    decimals = 0 if abs(index - round(index)) < 1e-9 else 2
    labels.fieldName = (
        f"CASE WHEN {index_expr} THEN "
        f"format_number(\"ELEV\", {decimals}) || ' {z_unit}' ELSE NULL END"
    )
    labels.repeatDistance = 110.0
    labels.repeatDistanceUnit = QgsUnitTypes.RenderMillimeters
    labels.setFormat(text_format)
    layer.setLabeling(QgsVectorLayerSimpleLabeling(labels))
    layer.setLabelsEnabled(True)
    layer.triggerRepaint()


def apply_spot_elevation_style(layer, preset_key="usgs_classic", font_family=None):
    """Apply USGS peak marker symbol (small triangle) and elevation label."""
    from qgis.core import QgsMarkerSymbol
    
    preset = _cartography_preset(preset_key)
    spot_color = preset.get("spot_elevation", preset["ink"])
    
    symbol = QgsMarkerSymbol.createSimple(
        {
            "name": "triangle",
            "color": spot_color,
            "outline_color": preset["paper"],
            "outline_width": "0.2",
            "size": "2.8",
        }
    )
    layer.setRenderer(QgsSingleSymbolRenderer(symbol))
    
    font = QFont(font_family or preset["font"])
    font.setBold(True)
    
    text_format = QgsTextFormat()
    text_format.setFont(font)
    text_format.setSize(7.0)
    text_format.setColor(QColor(spot_color))
    
    buffer = QgsTextBufferSettings()
    buffer.setEnabled(True)
    buffer.setSize(0.7)
    buffer.setColor(QColor(preset["paper"]))
    text_format.setBuffer(buffer)
    
    labels = QgsPalLayerSettings()
    labels.enabled = True
    labels.placement = QgsPalLayerSettings.OrderedPositionsAroundPoint
    labels.fieldName = "LABEL"
    labels.setFormat(text_format)
    layer.setLabeling(QgsVectorLayerSimpleLabeling(labels))
    layer.setLabelsEnabled(True)
    layer.triggerRepaint()


def apply_curvature_style(layer):
    """Apply diverging color scale for profile / planform curvature."""
    minimum, maximum = _stats(layer)
    extent = max(abs(minimum), abs(maximum), 1e-6)
    _pseudocolor(
        layer,
        (
            (-extent, "#0055ff", "Concave / high flow convergence"),
            (-extent * 0.25, "#88bbff", "Slightly concave"),
            (0.0, "#f7f7f7", "Flat / planar"),
            (extent * 0.25, "#ffbb88", "Slightly convex"),
            (extent, "#ff3300", "Convex / ridge crest"),
        ),
    )


def apply_ridge_style(layer, preset_key="usgs_classic"):
    """Apply dashed ridgeline vector style."""
    preset = _cartography_preset(preset_key)
    ridge_color = preset.get("ridge", "130,85,50,200")
    symbol = QgsLineSymbol.createSimple(
        {
            "color": ridge_color,
            "width": "0.38",
            "customdash": "3;2",
            "use_custom_dash": "1",
            "capstyle": "flat",
            "joinstyle": "round",
        }
    )
    layer.setRenderer(QgsSingleSymbolRenderer(symbol))
    layer.triggerRepaint()


def apply_stream_style(layer, preset_key="usgs_classic"):
    """Apply a restrained hydrography line style to extracted drainage."""

    preset = _cartography_preset(preset_key)
    symbol = QgsLineSymbol.createSimple(
        {
            "color": preset["water"],
            "width": "0.46",
            "capstyle": "round",
            "joinstyle": "round",
        }
    )
    layer.setRenderer(QgsSingleSymbolRenderer(symbol))
    layer.triggerRepaint()


def apply_flow_accumulation_style(layer, preset_key="usgs_classic"):
    minimum, maximum = _stats(layer)
    maximum = max(maximum, minimum + 1e-9)
    span = maximum - minimum
    preset = _cartography_preset(preset_key)
    _pseudocolor(
        layer,
        (
            (minimum, "#f6f3ea", "Low accumulation"),
            (minimum + span * 0.001, preset["water_light"], "Local flow"),
            (minimum + span * 0.02, "#63a9ca", "Concentrated flow"),
            (minimum + span * 0.15, preset["water"], "Channel"),
            (maximum, "#174f73", "Main drainage"),
        ),
    )


def apply_basin_style(layer, preset_key="usgs_classic"):
    minimum, maximum = _stats(layer)
    span = max(maximum - minimum, 1e-9)
    preset = _cartography_preset(preset_key)
    _pseudocolor(
        layer,
        (
            (minimum, preset["water_light"], "Basin identifiers"),
            (minimum + span * 0.33, "#e0c789", "Basins"),
            (minimum + span * 0.66, "#a5bb8b", "Basins"),
            (maximum, "#c9a0a0", "Basins"),
        ),
    )
    layer.setOpacity(0.55)

