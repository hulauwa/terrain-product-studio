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

from .presets import (
    ASPECT_CLASSES,
    CARTOGRAPHY_PRESETS,
    SLOPE_CLASSES,
    TERRAIN_PALETTES,
    resolve_palette_stops,
)
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
    # Qt6/QGIS4 scoped enum: QgsColorRampShader.Type.Discrete / .Interpolated
    try:
        ramp_discrete = QgsColorRampShader.Type.Discrete
        ramp_interp = QgsColorRampShader.Type.Interpolated
    except AttributeError:
        ramp_discrete = getattr(QgsColorRampShader, "Discrete")
        ramp_interp = getattr(QgsColorRampShader, "Interpolated")
    ramp.setColorRampType(ramp_discrete if discrete else ramp_interp)
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
    # Qt6/QGIS4 scoped enum: QgsContrastEnhancement.ContrastEnhancementAlgorithm.StretchToMinimumMaximum
    try:
        stretch_algo = QgsContrastEnhancement.ContrastEnhancementAlgorithm.StretchToMinimumMaximum
    except AttributeError:
        stretch_algo = getattr(QgsContrastEnhancement, "StretchToMinimumMaximum")
    enhancement.setContrastEnhancementAlgorithm(stretch_algo)
    renderer.setContrastEnhancement(enhancement)
    layer.setRenderer(renderer)
    layer.setOpacity(float(opacity))
    try:
        multiply_mode = QPainter.CompositionMode.CompositionMode_Multiply
    except AttributeError:  # Qt 5 unscoped enum
        multiply_mode = getattr(QPainter, "CompositionMode_Multiply")
    layer.setBlendMode(multiply_mode)
    layer.triggerRepaint()


def apply_dem_style(layer, preset_key="natural_earth", palette_key=None):
    """Render the canonical single-band DEM without creating an RGB copy."""

    preset = _cartography_preset(preset_key)
    palette = TERRAIN_PALETTES.get(
        palette_key, TERRAIN_PALETTES[preset["palette"]]
    )
    minimum, maximum = _stats(layer)
    if minimum >= maximum:
        maximum = minimum + 1.0
    items = [
        (value, QColor(red, green, blue), f"{value:g}")
        for value, red, green, blue in resolve_palette_stops(
            palette, minimum, maximum
        )
    ]
    _pseudocolor(layer, items)


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
        {"color": preset["contour_minor"], "width": "0.15", "capstyle": "round", "joinstyle": "round"}
    )
    index_symbol = QgsLineSymbol.createSimple(
        {"color": preset["contour_index"], "width": "0.35", "capstyle": "round", "joinstyle": "round"}
    )
    master_symbol = QgsLineSymbol.createSimple(
        {"color": master_color, "width": "0.55", "capstyle": "round", "joinstyle": "round"}
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
    # Qt6/QGIS4 scoped enum: QgsPalLayerSettings.Placement.Line
    try:
        labels.placement = QgsPalLayerSettings.Placement.Line
    except AttributeError:
        labels.placement = getattr(QgsPalLayerSettings, "Line")
    labels.isExpression = True
    decimals = 0 if abs(index - round(index)) < 1e-9 else 2
    labels.fieldName = (
        f"CASE WHEN {index_expr} THEN "
        f"format_number(\"ELEV\", {decimals}) || ' {z_unit}' ELSE NULL END"
    )
    labels.repeatDistance = 110.0
    # Qt6/QGIS4 scoped enum: QgsUnitTypes.RenderUnit.RenderMillimeters
    try:
        labels.repeatDistanceUnit = QgsUnitTypes.RenderUnit.RenderMillimeters
    except AttributeError:
        labels.repeatDistanceUnit = getattr(QgsUnitTypes, "RenderMillimeters")
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
    # Qt6/QGIS4 scoped enum: QgsPalLayerSettings.Placement.OrderedPositionsAroundPoint
    try:
        labels.placement = QgsPalLayerSettings.Placement.OrderedPositionsAroundPoint
    except AttributeError:
        labels.placement = getattr(QgsPalLayerSettings, "OrderedPositionsAroundPoint")
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
    """Apply tiered Strahler hydrography line style with graduated width and colors.

    Light maps use a distinct hydro blue clearly separated from the terrain
    ramps; Dark Terrain maps use a luminous cyan that stays readable on the
    deep ink background.
    """
    from qgis.core import (
        QgsRuleBasedRenderer,
        QgsLineSymbol,
    )

    preset = _cartography_preset(preset_key)
    base_water = preset.get("water", "#0070c0")

    symbol = QgsLineSymbol.createSimple({"color": base_water, "width": "0.35"})
    root_rule = QgsRuleBasedRenderer.Rule(symbol)
    root_rule.children().clear()

    if preset.get("dark"):
        stream_colors = ("#9be1ff", "#5fc9f7", "#2ba4e8", "#0f7fc9")
    else:
        stream_colors = ("#74c0e6", "#3f9fd6", "#1a6fb5", "#0b4489")

    # Rule 1: Order 1 (Headwater streams)
    s1 = QgsLineSymbol.createSimple({"color": stream_colors[0], "width": "0.28", "capstyle": "round", "joinstyle": "round"})
    r1 = QgsRuleBasedRenderer.Rule(s1, 0, 0, '"ORDER" <= 1', "Order 1 - Headwater Stream")
    root_rule.appendChild(r1)

    # Rule 2: Order 2 (Secondary Tributaries)
    s2 = QgsLineSymbol.createSimple({"color": stream_colors[1], "width": "0.52", "capstyle": "round", "joinstyle": "round"})
    r2 = QgsRuleBasedRenderer.Rule(s2, 0, 0, '"ORDER" = 2', "Order 2 - Secondary Tributary")
    root_rule.appendChild(r2)

    # Rule 3: Order 3 (Sub-Rivers)
    s3 = QgsLineSymbol.createSimple({"color": stream_colors[2], "width": "0.85", "capstyle": "round", "joinstyle": "round"})
    r3 = QgsRuleBasedRenderer.Rule(s3, 0, 0, '"ORDER" = 3', "Order 3 - Sub-River Channel")
    root_rule.appendChild(r3)

    # Rule 4: Order 4+ (Main Channels)
    s4 = QgsLineSymbol.createSimple({"color": stream_colors[3], "width": "1.30", "capstyle": "round", "joinstyle": "round"})
    r4 = QgsRuleBasedRenderer.Rule(s4, 0, 0, '"ORDER" >= 4', "Order 4+ - Major River Channel")
    root_rule.appendChild(r4)

    # Fallback rule
    s_fallback = QgsLineSymbol.createSimple({"color": stream_colors[1], "width": "0.45"})
    r_fallback = QgsRuleBasedRenderer.Rule(s_fallback, 0, 0, "ELSE", "Other Stream Channels")
    root_rule.appendChild(r_fallback)

    renderer = QgsRuleBasedRenderer(root_rule)
    layer.setRenderer(renderer)
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


def apply_twi_style(layer):
    """Apply Topographic Wetness Index (TWI) moisture saturation colormap."""
    minimum, maximum = _stats(layer)
    min_val = max(0.0, minimum)
    max_val = min(30.0, max(min_val + 2.0, maximum))
    span = max_val - min_val
    _pseudocolor(
        layer,
        (
            (min_val, "#d73027", "Very Dry Ridge (< 4)"),
            (min_val + span * 0.25, "#fee08b", "Dry Slope (4 - 7)"),
            (min_val + span * 0.50, "#d9ef8b", "Moderate Moisture (7 - 10)"),
            (min_val + span * 0.75, "#66bd63", "Moist / Convergent (10 - 14)"),
            (max_val, "#006837", "Saturated / Valley Floor (> 14)"),
        ),
    )


def apply_suitability_style(layer):
    """Apply Urban Construction Suitability 5-tier categorized colormap."""
    _pseudocolor(
        layer,
        (
            (1.0, "#2ca25f", "Class 1: < 3° (Highly Suitable / Very High)"),
            (2.0, "#99d8c9", "Class 2: 3°–8° (Suitable / High)"),
            (3.0, "#fed976", "Class 3: 8°–15° (Moderate / Grading Required)"),
            (4.0, "#fd8d3c", "Class 4: 15°–25° (Restricted / Steep Slope)"),
            (5.0, "#e31a1c", "Class 5: > 25° (Unsuitable / Conservation Zone)"),
        ),
    )


def apply_landslide_style(layer):
    """Apply Landslide Hazard 4-tier risk colormap."""
    _pseudocolor(
        layer,
        (
            (1.0, "#2b83ba", "Class 1: Low Hazard / Stable Terrain"),
            (2.0, "#ffffbf", "Class 2: Moderate Hazard"),
            (3.0, "#fdae61", "Class 3: High Hazard (Steep Slope)"),
            (4.0, "#d7191c", "Class 4: Very High Hazard (Critical Risk)"),
        ),
    )


def apply_geomorphon_style(layer):
    """Apply the 10-class geomorphon landform categorical colormap."""
    from .geomorphon import GEOMORPHON_COLORS, GEOMORPHON_FORMS

    _pseudocolor(
        layer,
        tuple(
            (float(code), color, f"{code} · {name}")
            for code, (name, color) in enumerate(
                zip(GEOMORPHON_FORMS, GEOMORPHON_COLORS), start=1
            )
        ),
    )


def apply_spi_style(layer):
    """Apply the Stream Power Index blue→yellow→red ramp."""
    _pseudocolor(
        layer,
        (
            (1.0, "#2c7bb6", "Low"),
            (6.0, "#ffffbf", "Moderate"),
            (12.0, "#d7191c", "High"),
        ),
    )


def apply_sti_style(layer):
    """Apply the Sediment Transport Index blue→yellow→red ramp."""
    _pseudocolor(
        layer,
        (
            (0.0, "#2c7bb6", "Low"),
            (6.0, "#ffffbf", "Moderate"),
            (20.0, "#d7191c", "High"),
        ),
    )


def apply_multihazard_style(layer):
    """Apply the 3-class multi-hazard palette: green / amber / red."""
    _pseudocolor(
        layer,
        (
            (1.0, "#2e8b57", "Low"),
            (2.0, "#f0a30a", "Moderate"),
            (3.0, "#d7191c", "High"),
        ),
    )
