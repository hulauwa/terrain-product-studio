"""Opinionated print-layout composer for polished DEM map products."""

from __future__ import annotations

import os
from datetime import date

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QColor, QFont
from qgis.core import (
    Qgis,
    QgsFillSymbol,
    QgsLayoutExporter,
    QgsLayoutItemLabel,
    QgsLayoutItemLegend,
    QgsLayoutItemMap,
    QgsLayoutItemMapGrid,
    QgsLayoutItemPicture,
    QgsLayoutItemScaleBar,
    QgsLayoutMeasurement,
    QgsLayoutPoint,
    QgsLayoutSize,
    QgsPrintLayout,
    QgsProject,
    QgsRectangle,
    QgsTextFormat,
)

from .math_utils import nice_interval, sanitize_prefix, unique_path
from .presets import CARTOGRAPHY_PRESETS


def _qt_alignment(name):
    """Return an alignment flag on both Qt 5 and scoped-enum Qt 6."""

    if hasattr(Qt, name):
        return getattr(Qt, name)
    return getattr(Qt.AlignmentFlag, name)


def _preset(key):
    return CARTOGRAPHY_PRESETS.get(key, CARTOGRAPHY_PRESETS["usgs_classic"])


def _unique_layout_name(manager, requested):
    base = requested.strip() or "Terrain Map"
    name = base
    counter = 2
    while manager.layoutByName(name) is not None:
        name = f"{base} {counter}"
        counter += 1
    return name


def _add_label(layout, text, x, y, width, height, font, size, color, bold=False):
    label = QgsLayoutItemLabel(layout)
    label.setText(text)
    text_format = QgsTextFormat()
    selected_font = QFont(font)
    selected_font.setBold(bool(bold))
    text_format.setFont(selected_font)
    text_format.setSize(float(size))
    text_format.setColor(QColor(color))
    label.setTextFormat(text_format)
    label.setHAlign(_qt_alignment("AlignLeft"))
    label.setVAlign(_qt_alignment("AlignVCenter"))
    layout.addLayoutItem(label)
    label.attemptMove(QgsLayoutPoint(x, y, Qgis.LayoutUnit.Millimeters))
    label.attemptResize(QgsLayoutSize(width, height, Qgis.LayoutUnit.Millimeters))
    return label


def _map_layers(layers):
    """Return the intentional cartographic stack, from top to bottom."""

    return [
        layers[key]
        for key in (
            "SPOT_ELEVATIONS",
            "STREAMS",
            "RIDGES",
            "CONTOURS",
            "MULTI_HILLSHADE",
            "HILLSHADE",
            "COLOR_RELIEF",
        )
        if key in layers and layers[key] is not None
    ]


def _reference_layer(layers):
    for key in (
        "COLOR_RELIEF",
        "MULTI_HILLSHADE",
        "HILLSHADE",
        "CONTOURS",
        "STREAMS",
        "WORKING_DEM",
    ):
        if key in layers and layers[key] is not None and layers[key].isValid():
            return layers[key]
    return None


def create_terrain_layout(
    project: QgsProject,
    layers,
    output_folder,
    config,
    north_arrow_path,
):
    """Create, register and optionally export a complete print layout.

    Returns ``(layout, exported_paths)``.  The map is deliberately limited to
    the generated cartographic layers so hidden analytical rasters never leak
    into the print product.
    """

    preset_key = config.get("preset", "usgs_classic")
    preset = _preset(preset_key)
    font_family = config.get("font_family") or preset["font"]
    title = config.get("title", "TERRAIN MAP").strip() or "TERRAIN MAP"
    subtitle = config.get("subtitle", "DEM-derived topographic products").strip()
    author = config.get("author", "Terrain Product Studio").strip()
    source = config.get("source", "Digital Elevation Model").strip()
    layout_name = config.get("layout_name", title.title()).strip() or "Terrain Map"

    manager = project.layoutManager()
    layout = QgsPrintLayout(project)
    layout.initializeDefaults()
    layout.setName(_unique_layout_name(manager, layout_name))

    landscape = preset["orientation"] == "landscape"
    page_width, page_height = (297.0, 210.0) if landscape else (210.0, 297.0)
    page = layout.pageCollection().page(0)
    page.setPageSize(
        QgsLayoutSize(page_width, page_height, Qgis.LayoutUnit.Millimeters)
    )
    page.setPageStyleSymbol(
        QgsFillSymbol.createSimple(
            {
                "color": preset["paper"],
                "outline_color": preset["ink"],
                "outline_width": "0.45",
            }
        )
    )

    if landscape:
        map_box = (14.0, 31.0, 218.0, 153.0)
        legend_box = (239.0, 52.0, 44.0, 97.0)
        north_box = (252.0, 31.0, 18.0, 18.0)
        scale_box = (240.0, 154.0, 42.0, 12.0)
        meta_box = (239.0, 169.0, 44.0, 15.0)
        title_width = 269.0
    else:
        map_box = (13.0, 33.0, 184.0, 188.0)
        legend_box = (13.0, 230.0, 88.0, 45.0)
        north_box = (171.0, 229.0, 18.0, 18.0)
        scale_box = (111.0, 252.0, 78.0, 12.0)
        meta_box = (111.0, 267.0, 78.0, 10.0)
        title_width = 184.0

    _add_label(
        layout,
        title.upper(),
        14.0 if landscape else 13.0,
        8.0,
        title_width,
        12.0,
        font_family,
        22.0 if landscape else 19.0,
        preset["ink"],
        True,
    )
    _add_label(
        layout,
        subtitle,
        14.0 if landscape else 13.0,
        20.0,
        title_width,
        7.0,
        font_family,
        9.0,
        preset["muted_ink"],
    )

    reference = _reference_layer(layers)
    if reference is None:
        raise ValueError("No valid generated terrain layer is available for the layout.")

    map_item = QgsLayoutItemMap(layout)
    map_item.setFrameEnabled(True)
    map_item.setFrameStrokeColor(QColor(preset["ink"]))
    map_item.setFrameStrokeWidth(
        QgsLayoutMeasurement(0.55, Qgis.LayoutUnit.Millimeters)
    )
    map_item.setBackgroundColor(QColor(preset["paper"]))
    map_item.setCrs(reference.crs())
    extent = QgsRectangle(reference.extent())
    extent.scale(1.035)
    map_item.setExtent(extent)
    map_layers = _map_layers(layers)
    if map_layers:
        map_item.setLayers(map_layers)
        map_item.setKeepLayerSet(True)
        map_item.setKeepLayerStyles(True)
    layout.addLayoutItem(map_item)
    map_item.attemptMove(
        QgsLayoutPoint(map_box[0], map_box[1], Qgis.LayoutUnit.Millimeters)
    )
    map_item.attemptResize(
        QgsLayoutSize(map_box[2], map_box[3], Qgis.LayoutUnit.Millimeters)
    )
    layout.setReferenceMap(map_item)

    if config.get("grid", True):
        interval = nice_interval(max(extent.width(), extent.height()), 6)
        grid = QgsLayoutItemMapGrid("Coordinate grid", map_item)
        grid.setIntervalX(interval)
        grid.setIntervalY(interval)
        grid.setGridLineColor(QColor(preset["grid"] + "55"))
        grid.setGridLineWidth(0.12)
        grid.setFrameStyle(Qgis.MapGridFrameStyle.LineBorder)
        grid.setFramePenColor(QColor(preset["ink"]))
        grid.setFramePenSize(0.30)
        grid.setAnnotationEnabled(True)
        grid.setAnnotationPrecision(0 if not reference.crs().isGeographic() else 3)
        annotation_format = QgsTextFormat()
        annotation_format.setFont(QFont(font_family))
        annotation_format.setSize(6.5)
        annotation_format.setColor(QColor(preset["muted_ink"]))
        grid.setAnnotationTextFormat(annotation_format)
        grid.setAnnotationFrameDistance(1.0)
        map_item.grids().addGrid(grid)

    legend = QgsLayoutItemLegend(layout)
    legend.setTitle(preset["legend_title"])
    legend.setLinkedMap(map_item)
    legend.setLegendFilterByMapEnabled(True)
    legend.setResizeToContents(False)
    legend.setColumnCount(1)
    legend.setSymbolWidth(5.0)
    legend.setSymbolHeight(3.0)
    legend.setBoxSpace(1.5)
    try:
        legend_title_font = QFont(font_family, 9)
        legend_title_font.setBold(True)
        legend.setStyleFont(Qgis.LegendComponent.Title, legend_title_font)
        legend.setStyleFont(Qgis.LegendComponent.Group, QFont(font_family, 7))
        legend.setStyleFont(Qgis.LegendComponent.SymbolLabel, QFont(font_family, 7))
    except (AttributeError, TypeError):
        pass
    layout.addLayoutItem(legend)
    legend.attemptMove(
        QgsLayoutPoint(legend_box[0], legend_box[1], Qgis.LayoutUnit.Millimeters)
    )
    legend.attemptResize(
        QgsLayoutSize(legend_box[2], legend_box[3], Qgis.LayoutUnit.Millimeters)
    )

    north = QgsLayoutItemPicture(layout)
    north.setPicturePath(north_arrow_path)
    north.setLinkedMap(map_item)
    layout.addLayoutItem(north)
    north.attemptMove(
        QgsLayoutPoint(north_box[0], north_box[1], Qgis.LayoutUnit.Millimeters)
    )
    north.attemptResize(
        QgsLayoutSize(north_box[2], north_box[3], Qgis.LayoutUnit.Millimeters)
    )

    scale = QgsLayoutItemScaleBar(layout)
    scale.setLinkedMap(map_item)
    scale.setStyle("Single Box")
    scale.setNumberOfSegments(4)
    scale.setNumberOfSegmentsLeft(0)
    scale.applyDefaultSize()
    scale_text = QgsTextFormat()
    scale_text.setFont(QFont(font_family))
    scale_text.setSize(7.0)
    scale_text.setColor(QColor(preset["ink"]))
    scale.setTextFormat(scale_text)
    layout.addLayoutItem(scale)
    scale.attemptMove(
        QgsLayoutPoint(scale_box[0], scale_box[1], Qgis.LayoutUnit.Millimeters)
    )
    scale.attemptResize(
        QgsLayoutSize(scale_box[2], scale_box[3], Qgis.LayoutUnit.Millimeters)
    )

    crs_text = reference.crs().authid() or reference.crs().description()
    _add_label(
        layout,
        f"CRS  {crs_text}\n{date.today().isoformat()}",
        meta_box[0],
        meta_box[1],
        meta_box[2],
        meta_box[3],
        font_family,
        6.5,
        preset["muted_ink"],
    )

    footer = f"Source: {source}   •   Cartography: {author}   •   Generated with Terrain Product Studio"
    _add_label(
        layout,
        footer,
        14.0 if landscape else 13.0,
        190.0 if landscape else 281.0,
        269.0 if landscape else 184.0,
        8.0,
        font_family,
        6.5,
        preset["muted_ink"],
    )

    if not manager.addLayout(layout):
        raise RuntimeError("QGIS could not register the generated print layout.")

    exported = []
    exporter = QgsLayoutExporter(layout)
    export_prefix = sanitize_prefix(config.get("export_prefix", title))
    dpi = max(72, min(1200, int(config.get("dpi", 300))))
    if config.get("export_pdf", False):
        pdf_path = unique_path(os.path.join(output_folder, f"{export_prefix}_map.pdf"))
        pdf_settings = QgsLayoutExporter.PdfExportSettings()
        pdf_settings.dpi = dpi
        result = exporter.exportToPdf(pdf_path, pdf_settings)
        if int(result) != int(QgsLayoutExporter.ExportResult.Success):
            raise RuntimeError(f"QGIS could not export PDF (code {int(result)}).")
        exported.append(pdf_path)
    if config.get("export_png", False):
        png_path = unique_path(os.path.join(output_folder, f"{export_prefix}_map.png"))
        image_settings = QgsLayoutExporter.ImageExportSettings()
        image_settings.dpi = dpi
        result = exporter.exportToImage(png_path, image_settings)
        if int(result) != int(QgsLayoutExporter.ExportResult.Success):
            raise RuntimeError(f"QGIS could not export PNG (code {int(result)}).")
        exported.append(png_path)

    return layout, exported
