"""Opinionated print-layout composer for polished DEM map products."""

from __future__ import annotations

import os
from datetime import date

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QColor, QFont
from qgis.core import (
    Qgis,
    QgsFillSymbol,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
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
from .qgis_compat import (
    layout_unit_mm,
    legend_component,
    map_grid_line_border_style,
    set_label_text_format,
)
from .layout_styles import create_layer_style_overrides
from .layout_geometry import plan_layout_geometry, validate_layout_geometry
from .style_packs import LAYOUT_TEMPLATES, style_pack


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


def _add_label(
    layout,
    text,
    x,
    y,
    width,
    height,
    font,
    size,
    color,
    bold=False,
    alignment="AlignLeft",
):
    label = QgsLayoutItemLabel(layout)
    label.setText(text)
    text_format = QgsTextFormat()
    selected_font = QFont(font)
    selected_font.setBold(bool(bold))
    text_format.setFont(selected_font)
    text_format.setSize(float(size))
    text_format.setColor(QColor(color))
    set_label_text_format(label, text_format)
    label.setHAlign(_qt_alignment(alignment))
    label.setVAlign(_qt_alignment("AlignVCenter"))
    layout.addLayoutItem(label)
    label.attemptMove(QgsLayoutPoint(x, y, layout_unit_mm()))
    label.attemptResize(QgsLayoutSize(width, height, layout_unit_mm()))
    return label


def _map_layer_keys(layers, preset_key):
    return resolve_recipe_keys(layers.keys(), preset_key, target="layout")


def _reference_layer(layers):
    for key in (
        "WORKING_DEM",
        "COLOR_RELIEF",
        "MULTI_HILLSHADE",
        "HILLSHADE",
        "CONTOURS_SMOOTH",
        "CONTOURS",
        "STREAMS_SMOOTH",
        "STREAMS",
    ):
        if key in layers and layers[key] is not None and layers[key].isValid():
            return layers[key]
    return None


def _grid_enum(container_name, value):
    """Resolve QGIS 3 class enums and QGIS 4 scoped grid enums."""

    qgis_container = getattr(Qgis, container_name, None)
    if qgis_container is not None and hasattr(qgis_container, value):
        return getattr(qgis_container, value)
    legacy_container = getattr(QgsLayoutItemMapGrid, container_name, None)
    if legacy_container is not None and hasattr(legacy_container, value):
        return getattr(legacy_container, value)
    return getattr(QgsLayoutItemMapGrid, value)


def _set_grid_annotation_sides(grid, visible_names):
    sides = {
        name: _grid_enum("MapGridBorderSide", name)
        for name in ("Left", "Right", "Bottom", "Top")
    }
    outside = _grid_enum("MapGridAnnotationPosition", "OutsideMapFrame")
    horizontal = _grid_enum("MapGridAnnotationDirection", "Horizontal")
    show = _grid_enum("MapGridComponentVisibility", "ShowAll")
    hide = _grid_enum("MapGridComponentVisibility", "HideAll")
    for name, side in sides.items():
        try:
            grid.setAnnotationPosition(outside, side)
        except TypeError:  # Older QGIS supports the all-sides overload.
            grid.setAnnotationPosition(outside)
        try:
            grid.setAnnotationDirection(horizontal, side)
        except TypeError:
            grid.setAnnotationDirection(horizontal)
        try:
            grid.setAnnotationDisplay(show if name in visible_names else hide, side)
        except (AttributeError, TypeError):
            # Very old builds cannot selectively hide sides; supported QGIS
            # 3.34+ and QGIS 4 both take the per-side overload above.
            pass


def _add_coordinate_grid(
    map_item,
    project,
    map_crs,
    map_extent,
    grid_crs,
    *,
    name,
    color,
    ink,
    font_family,
    visible_sides,
    annotation_size,
    frame_distance,
):
    grid = QgsLayoutItemMapGrid(name, map_item)
    if grid_crs is not None and grid_crs.isValid():
        grid.setCrs(grid_crs)
    interval_extent = QgsRectangle(map_extent)
    if grid_crs is not None and grid_crs.isValid() and grid_crs != map_crs:
        try:
            interval_extent = QgsCoordinateTransform(
                map_crs, grid_crs, project
            ).transformBoundingBox(map_extent)
        except Exception:
            interval_extent = QgsRectangle(map_extent)
    interval = nice_interval(
        max(interval_extent.width(), interval_extent.height()), 6
    )
    grid.setIntervalX(interval)
    grid.setIntervalY(interval)
    grid.setGridLineColor(QColor(color))
    grid.setGridLineWidth(0.10)
    grid.setFrameStyle(map_grid_line_border_style())
    grid.setFramePenColor(QColor(ink))
    grid.setFramePenSize(0.25)
    grid.setAnnotationEnabled(True)
    grid.setAnnotationPrecision(
        3 if grid_crs is not None and grid_crs.isGeographic() else 0
    )
    _set_grid_annotation_sides(grid, set(visible_sides))
    annotation_format = QgsTextFormat()
    annotation_format.setFont(QFont(font_family))
    annotation_format.setSize(float(annotation_size))
    annotation_format.setColor(QColor(ink))
    grid.setAnnotationTextFormat(annotation_format)
    grid.setAnnotationFrameDistance(float(frame_distance))
    map_item.grids().addGrid(grid)
    return grid


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
    pack = style_pack(preset_key)
    template_key = config.get("layout_template") or pack.layout_template
    template = LAYOUT_TEMPLATES.get(
        template_key, LAYOUT_TEMPLATES[pack.layout_template]
    )
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
    requested_extent = config.get("layout_extent")
    if isinstance(requested_extent, (list, tuple)) and len(requested_extent) == 4:
        candidate = QgsRectangle(*[float(value) for value in requested_extent])
        source_authid = str(config.get("layout_extent_crs") or "")
        if source_authid and source_authid != reference.crs().authid():
            source_crs = QgsCoordinateReferenceSystem(source_authid)
            if source_crs.isValid():
                transform = QgsCoordinateTransform(
                    source_crs, reference.crs(), project
                )
                candidate = transform.transformBoundingBox(candidate)
        clipped = candidate.intersect(reference.extent())
        if not clipped.isNull() and not clipped.isEmpty():
            extent = clipped
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
    page_is_landscape = page_width > page_height
    page = layout.pageCollection().page(0)
    page.setPageSize(
        QgsLayoutSize(page_width, page_height, layout_unit_mm())
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

    show_legend = bool(template.show_legend and config.get("show_legend", True))
    show_metadata = bool(template.show_metadata)
    geometry = plan_layout_geometry(
        template.key,
        template.legend_position,
        page_width,
        page_height,
        show_legend=show_legend,
        show_metadata=show_metadata,
    )
    geometry_errors = validate_layout_geometry(geometry)
    if geometry_errors:
        raise ValueError("Invalid layout geometry: " + "; ".join(geometry_errors))
    boxes = geometry.boxes
    map_box = boxes["map"].as_tuple()
    north_box = boxes["north"].as_tuple()
    scale_box = boxes["scale"].as_tuple()
    legend_box = boxes.get("legend")
    meta_box = boxes.get("metadata")
    title_box = boxes["title"].as_tuple()
    subtitle_box = boxes["subtitle"].as_tuple()
    footer_box = boxes["footer"].as_tuple()

    # USGS marginal style sheets use a compact 5–12 pt hierarchy. Keep type
    # sizes stable across paper sizes so text remains professional, not poster-like.
    title_size = 12.0 if template.key in {"classic_topo", "survey_sheet"} else 13.0
    subtitle_size = 7.5

    title_alignment = "AlignHCenter" if template.title_position == "center" else "AlignLeft"
    _add_label(
        layout,
        title.upper(),
        title_box[0],
        title_box[1],
        title_box[2],
        title_box[3],
        font_family,
        title_size,
        preset["ink"],
        True,
        title_alignment,
    )
    _add_label(
        layout,
        subtitle,
        subtitle_box[0],
        subtitle_box[1],
        subtitle_box[2],
        subtitle_box[3],
        font_family,
        subtitle_size,
        preset["muted_ink"],
    )

    map_item = QgsLayoutItemMap(layout)
    layout.addLayoutItem(map_item)
    map_item.attemptMove(
        QgsLayoutPoint(map_box[0], map_box[1], layout_unit_mm())
    )
    map_item.attemptResize(
        QgsLayoutSize(map_box[2], map_box[3], layout_unit_mm())
    )
    map_item.setFrameEnabled(True)
    map_item.setFrameStrokeColor(QColor(preset["ink"]))
    frame_width = {
        "minimal": 0.0,
        "thin": 0.30,
        "survey": 0.75,
        "heavy": 0.80,
        "glow": 0.35,
        "technical": 0.65,
        "double": 0.55,
    }.get(template.frame_style, 0.55)
    map_item.setFrameEnabled(frame_width > 0)
    map_item.setFrameStrokeWidth(
        QgsLayoutMeasurement(frame_width, layout_unit_mm())
    )
    map_item.setBackgroundColor(QColor(preset["paper"]))
    map_item.setCrs(reference.crs())

    extent.scale(1.035)
    try:
        map_item.zoomToExtent(extent)
    except AttributeError:
        map_item.setExtent(extent)
    # QGIS may resize a layout map while fitting a new extent. Re-assert the
    # reserved safe zone afterwards so the map can never grow into legend or
    # marginalia space.
    map_item.attemptMove(
        QgsLayoutPoint(map_box[0], map_box[1], layout_unit_mm())
    )
    map_item.attemptResize(
        QgsLayoutSize(map_box[2], map_box[3], layout_unit_mm())
    )

    ordered_keys = _map_layer_keys(layers, preset_key)
    map_layers = [
        layers[key] for key in ordered_keys if layers.get(key) is not None
    ]
    if map_layers:
        map_item.setLayers(map_layers)
        map_item.setKeepLayerSet(True)
        style_config = dict(config)
        style_config["dark"] = bool(preset.get("dark"))
        overrides, style_warnings = create_layer_style_overrides(
            layers, ordered_keys, style_config
        )
        if overrides:
            map_item.setLayerStyleOverrides(overrides)
        else:
            # Preserve the current appearance even if a provider cannot be
            # cloned for a style-pack variant.
            map_item.storeCurrentLayerStyles()
        map_item.setKeepLayerStyles(True)
        if style_warnings:
            layout.setCustomProperty(
                "terrain_product_studio/style_warnings",
                "\n".join(style_warnings),
            )

    map_item.refresh()
    layout.setReferenceMap(map_item)

    if config.get("grid", template.show_grid):
        grid_mode = str(config.get("grid_mode") or "map_crs")
        map_crs = reference.crs()
        wgs84 = QgsCoordinateReferenceSystem("EPSG:4326")
        if grid_mode == "custom":
            custom_crs = QgsCoordinateReferenceSystem(
                str(config.get("grid_custom_crs") or "")
            )
            if custom_crs.isValid():
                _add_coordinate_grid(
                    map_item,
                    project,
                    map_crs,
                    extent,
                    custom_crs,
                    name="Custom coordinate grid",
                    color=preset["grid"] + "55",
                    ink=preset["muted_ink"],
                    font_family=font_family,
                    visible_sides=("Left", "Right", "Bottom", "Top"),
                    annotation_size=6.0,
                    frame_distance=1.0,
                )
            else:
                layout.setCustomProperty(
                    "terrain_product_studio/grid_warning",
                    "Invalid custom grid CRS; map CRS grid used instead.",
                )
                grid_mode = "map_crs"
        if grid_mode == "wgs84":
            _add_coordinate_grid(
                map_item,
                project,
                map_crs,
                extent,
                wgs84,
                name="WGS 84 graticule",
                color=preset["grid"] + "55",
                ink=preset["muted_ink"],
                font_family=font_family,
                visible_sides=("Left", "Right", "Bottom", "Top"),
                annotation_size=6.0,
                frame_distance=1.0,
            )
        elif grid_mode == "dual":
            _add_coordinate_grid(
                map_item,
                project,
                map_crs,
                extent,
                map_crs,
                name="Projected coordinate grid",
                color=preset["grid"] + "55",
                ink=preset["muted_ink"],
                font_family=font_family,
                visible_sides=("Left", "Bottom"),
                annotation_size=5.8,
                frame_distance=1.0,
            )
            _add_coordinate_grid(
                map_item,
                project,
                map_crs,
                extent,
                wgs84,
                name="WGS 84 graticule",
                color=preset["accent"] + "45",
                ink=preset["accent"],
                font_family=font_family,
                visible_sides=("Right", "Top"),
                annotation_size=5.5,
                frame_distance=1.0,
            )
        elif grid_mode == "map_crs":
            _add_coordinate_grid(
                map_item,
                project,
                map_crs,
                extent,
                map_crs,
                name="Map CRS grid",
                color=preset["grid"] + "55",
                ink=preset["muted_ink"],
                font_family=font_family,
                visible_sides=("Left", "Right", "Bottom", "Top"),
                annotation_size=6.0,
                frame_distance=1.0,
            )

    if show_legend and legend_box is not None:
        legend_rect = legend_box.as_tuple()
        legend = QgsLayoutItemLegend(layout)
        legend.setTitle(preset["legend_title"])
        legend.setLinkedMap(map_item)
        legend.setLegendFilterByMapEnabled(True)
        legend.setResizeToContents(False)
        legend.setColumnCount(2 if template.legend_position == "bottom" else 1)
        legend.setSymbolWidth(5.0)
        legend.setSymbolHeight(3.0)
        legend.setBoxSpace(1.5)
        try:
            legend_title_font = QFont(font_family, 8)
            legend_title_font.setBold(True)
            legend.setStyleFont(legend_component("Title"), legend_title_font)
            legend.setStyleFont(legend_component("Group"), QFont(font_family, 6))
            legend.setStyleFont(
                legend_component("SymbolLabel"), QFont(font_family, 6)
            )
        except (AttributeError, TypeError):
            layout.setCustomProperty(
                "terrain_product_studio/legend_font_fallback", True
            )
        layout.addLayoutItem(legend)
        legend.attemptMove(
            QgsLayoutPoint(legend_rect[0], legend_rect[1], layout_unit_mm())
        )
        legend.attemptResize(
            QgsLayoutSize(legend_rect[2], legend_rect[3], layout_unit_mm())
        )

    north = QgsLayoutItemPicture(layout)
    north.setPicturePath(north_arrow_path)
    north.setLinkedMap(map_item)
    layout.addLayoutItem(north)
    north.attemptMove(
        QgsLayoutPoint(north_box[0], north_box[1], layout_unit_mm())
    )
    north.attemptResize(
        QgsLayoutSize(north_box[2], north_box[3], layout_unit_mm())
    )

    scale = QgsLayoutItemScaleBar(layout)
    scale.setLinkedMap(map_item)
    scale.setStyle("Single Box")
    scale.setNumberOfSegments(4)
    scale.setNumberOfSegmentsLeft(0)
    scale.applyDefaultSize()
    scale_text = QgsTextFormat()
    scale_text.setFont(QFont(font_family))
    scale_text.setSize(6.5)
    scale_text.setColor(QColor(preset["ink"]))
    set_label_text_format(scale, scale_text)
    layout.addLayoutItem(scale)
    scale.attemptMove(
        QgsLayoutPoint(scale_box[0], scale_box[1], layout_unit_mm())
    )
    scale.attemptResize(
        QgsLayoutSize(scale_box[2], scale_box[3], layout_unit_mm())
    )

    crs_text = reference.crs().authid() or reference.crs().description()
    if show_metadata and meta_box is not None:
        meta_rect = meta_box.as_tuple()
        _add_label(
            layout,
            f"CRS  {crs_text}\n{date.today().isoformat()}",
            meta_rect[0],
            meta_rect[1],
            meta_rect[2],
            meta_rect[3],
            font_family,
            6.0,
            preset["muted_ink"],
        )

    footer = f"Source: {source}   •   Cartography: {author}   •   Generated with Terrain Product Studio"
    _add_label(
        layout,
        footer,
        footer_box[0],
        footer_box[1],
        footer_box[2],
        footer_box[3],
        font_family,
        5.5,
        preset["muted_ink"],
    )

    if not manager.addLayout(layout):
        raise RuntimeError("QGIS could not register the generated print layout.")

    exported = []
    exporter = QgsLayoutExporter(layout)
    export_prefix = sanitize_prefix(config.get("export_prefix", title))
    layout_slug = sanitize_prefix(layout.name())
    dpi = max(72, min(1200, int(config.get("dpi", 300))))
    if config.get("export_pdf", False):
        pdf_path = unique_path(
            os.path.join(output_folder, f"{export_prefix}_{layout_slug}.pdf")
        )
        pdf_settings = QgsLayoutExporter.PdfExportSettings()
        pdf_settings.dpi = dpi
        result = exporter.exportToPdf(pdf_path, pdf_settings)
        if int(result) != int(QgsLayoutExporter.ExportResult.Success):
            raise RuntimeError(f"QGIS could not export PDF (code {int(result)}).")
        exported.append(pdf_path)
    if config.get("export_png", False):
        png_path = unique_path(
            os.path.join(output_folder, f"{export_prefix}_{layout_slug}.png")
        )
        image_settings = QgsLayoutExporter.ImageExportSettings()
        image_settings.dpi = dpi
        result = exporter.exportToImage(png_path, image_settings)
        if int(result) != int(QgsLayoutExporter.ExportResult.Success):
            raise RuntimeError(f"QGIS could not export PNG (code {int(result)}).")
        exported.append(png_path)

    return layout, exported


def create_terrain_layouts(project, layers, output_folder, configs, north_arrow_path):
    """Create an ordered map book while keeping each layout style independent."""

    created = []
    exported = []
    for config in configs:
        layout, paths = create_terrain_layout(
            project, layers, output_folder, config, north_arrow_path
        )
        created.append(layout)
        exported.extend(paths)
    return created, exported
