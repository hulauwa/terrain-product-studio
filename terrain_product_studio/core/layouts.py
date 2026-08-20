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
from .map_recipes import resolve_recipe_keys
from .presets import CARTOGRAPHY_PRESETS
from .qgis_compat import map_grid_line_border_style


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


def _map_layers(layers, preset_key):
    """Return the intentional cartographic stack, from top to bottom."""

    keys = resolve_recipe_keys(layers.keys(), preset_key, target="layout")
    return [layers[key] for key in keys if layers.get(key) is not None]


def _reference_layer(layers):
    for key in (
        "COLOR_RELIEF",
        "MULTI_HILLSHADE",
        "HILLSHADE",
        "CONTOURS_SMOOTH",
        "CONTOURS",
        "STREAMS_SMOOTH",
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

    reference = _reference_layer(layers)
    if reference is None:
        raise ValueError("No valid generated terrain layer is available for the layout.")

    extent = QgsRectangle(reference.extent())
    bbox_w = max(1e-3, extent.width())
    bbox_h = max(1e-3, extent.height())
    bbox_aspect = bbox_w / bbox_h

    # Dynamically select orientation and dimensions based on bounding box;
    # an explicit paper size / orientation in the config overrides the auto fit.
    landscape = bbox_aspect >= 0.95
    paper_sizes = {"a4": (210.0, 297.0), "a3": (297.0, 420.0), "a1": (594.0, 841.0)}
    paper_key = (config.get("paper_size") or "auto").lower()
    orientation_key = (config.get("orientation") or "auto").lower()
    if paper_key in paper_sizes:
        width_a, height_a = paper_sizes[paper_key]
        if orientation_key == "portrait":
            page_width, page_height = width_a, height_a
        elif orientation_key == "landscape":
            page_width, page_height = height_a, width_a
        else:  # auto orientation keeps the bounding-box choice
            page_width, page_height = (
                (height_a, width_a) if landscape else (width_a, height_a)
            )
    else:
        page_width, page_height = (297.0, 210.0) if landscape else (210.0, 297.0)
    # Every A-series sheet shares the √2:1 aspect ratio, so a single uniform
    # factor scales the whole A4-base layout to A3/A1 without distortion.
    page_is_landscape = page_width > page_height
    paper_scale = page_width / 297.0 if page_is_landscape else page_height / 297.0
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

    if page_is_landscape:
        avail_w, avail_h = 218.0, 160.0
        # Adapt map size to bbox aspect ratio without distortion
        if bbox_aspect >= (avail_w / avail_h):
            mw = avail_w
            mh = min(avail_h, mw / bbox_aspect)
        else:
            mh = avail_h
            mw = min(avail_w, mh * bbox_aspect)
        mx = 14.0 + (avail_w - mw) / 2.0
        my = 30.0 + (avail_h - mh) / 2.0
        map_box = (mx, my, mw, mh)
        legend_box = (239.0, 52.0, 46.0, 95.0)
        north_box = (252.0, 30.0, 18.0, 18.0)
        scale_box = (240.0, 152.0, 44.0, 12.0)
        meta_box = (239.0, 167.0, 46.0, 24.0)
        title_width = 269.0

    else:
        avail_w, avail_h = 184.0, 188.0
        if bbox_aspect >= (avail_w / avail_h):
            mw = avail_w
            mh = min(avail_h, mw / bbox_aspect)
        else:
            mh = avail_h
            mw = min(avail_w, mh * bbox_aspect)
        mx = 13.0 + (avail_w - mw) / 2.0
        my = 32.0 + (avail_h - mh) / 2.0
        map_box = (mx, my, mw, mh)
        legend_box = (13.0, 226.0, 88.0, 52.0)
        north_box = (174.0, 226.0, 18.0, 18.0)
        scale_box = (111.0, 248.0, 80.0, 12.0)
        meta_box = (111.0, 263.0, 80.0, 18.0)
        title_width = 184.0

    if paper_scale != 1.0:
        map_box = tuple(value * paper_scale for value in map_box)
        legend_box = tuple(value * paper_scale for value in legend_box)
        north_box = tuple(value * paper_scale for value in north_box)
        scale_box = tuple(value * paper_scale for value in scale_box)
        meta_box = tuple(value * paper_scale for value in meta_box)
        title_width *= paper_scale
        title_size, subtitle_size = 22.0 * paper_scale, 9.0 * paper_scale
    else:
        title_size, subtitle_size = (22.0, 9.0) if page_is_landscape else (19.0, 9.0)

    _add_label(
        layout,
        title.upper(),
        14.0 * paper_scale,
        8.0 * paper_scale,
        title_width,
        12.0 * paper_scale,
        font_family,
        title_size,
        preset["ink"],
        True,
    )
    _add_label(
        layout,
        subtitle,
        14.0 * paper_scale,
        20.0 * paper_scale,
        title_width,
        7.0 * paper_scale,
        font_family,
        subtitle_size,
        preset["muted_ink"],
    )

    map_item = QgsLayoutItemMap(layout)
    layout.addLayoutItem(map_item)
    map_item.attemptMove(
        QgsLayoutPoint(map_box[0], map_box[1], Qgis.LayoutUnit.Millimeters)
    )
    map_item.attemptResize(
        QgsLayoutSize(map_box[2], map_box[3], Qgis.LayoutUnit.Millimeters)
    )
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

    map_layers = _map_layers(layers, preset_key)
    if map_layers:
        map_item.setLayers(map_layers)
        map_item.setKeepLayerSet(True)
        map_item.setKeepLayerStyles(True)

    map_item.refresh()
    layout.setReferenceMap(map_item)

    if config.get("grid", True):
        interval = nice_interval(max(extent.width(), extent.height()), 6)
        grid = QgsLayoutItemMapGrid("Coordinate grid", map_item)
        grid.setIntervalX(interval)
        grid.setIntervalY(interval)
        grid.setGridLineColor(QColor(preset["grid"] + "55"))
        grid.setGridLineWidth(0.12)
        grid.setFrameStyle(map_grid_line_border_style())
        grid.setFramePenColor(QColor(preset["ink"]))
        grid.setFramePenSize(0.30)
        grid.setAnnotationEnabled(True)
        grid.setAnnotationPrecision(0 if not reference.crs().isGeographic() else 3)
        # USGS convention: labels sit outside the map frame, always horizontal
        # (never rotated with the frame edge). QGIS 4 moved these enums into
        # the Qgis namespace and made the position a per-side setting.
        try:
            for side in (
                Qgis.MapGridBorderSide.Left,
                Qgis.MapGridBorderSide.Right,
                Qgis.MapGridBorderSide.Bottom,
                Qgis.MapGridBorderSide.Top,
            ):
                grid.setAnnotationPosition(
                    Qgis.MapGridAnnotationPosition.OutsideMapFrame, side
                )
            grid.setAnnotationDirection(
                Qgis.MapGridAnnotationDirection.Horizontal
            )
        except AttributeError:  # QGIS 3 / Qt5 class enums
            try:
                grid.setAnnotationPosition(
                    QgsLayoutItemMapGrid.AnnotationPosition.OutsideMapFrame
                )
                grid.setAnnotationDirection(
                    QgsLayoutItemMapGrid.AnnotationDirection.Horizontal
                )
            except AttributeError:  # Qt5 unscoped enum fallback
                grid.setAnnotationPosition(
                    getattr(QgsLayoutItemMapGrid, "OutsideMapFrame")
                )
                grid.setAnnotationDirection(
                    getattr(QgsLayoutItemMapGrid, "Horizontal")
                )
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
