"""Dockable user interface for Terrain Product Studio."""

from __future__ import annotations

import json
import math
import os
from datetime import datetime, timezone

from qgis.PyQt.QtCore import QDir, QCoreApplication, QTimer, QUrl, Qt
from qgis.PyQt.QtGui import (
    QBrush,
    QColor,
    QDesktopServices,
    QFont,
    QIcon,
    QLinearGradient,
    QPainter,
    QPen,
    QPixmap,
)
from qgis.PyQt.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDockWidget,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)
from qgis.core import (
    QgsApplication,
    QgsMapLayerProxyModel,
    QgsMapLayerStyle,
    QgsMapLayerType,
    QgsProject,
    QgsRasterLayer,
    QgsReferencedRectangle,
    QgsSettings,
)
from qgis.gui import QgsMapLayerComboBox

from .core.dem_info import format_dem_report, inspect_dem_layer
from .core.design_presets import (
    DEFAULT_DESIGN_PRESET,
    DESIGN_PRESETS,
    design_preset,
)
from .core.export_3d import export_obj, export_stl
from .core.history import append_history, load_history
from .core.intelligence_report import generate_intelligence_report
from .core.layers import add_terrain_results, apply_result_styles
from .core.layouts import create_terrain_layout, create_terrain_layouts
from .core.layout_styles import export_style_pack_qml
from .core.restyle import parse_run_manifest, restyle_outputs
from .core.smart_defaults import compute_smart_defaults
from .core.cartography_qa import inspect_layer_recipe, validate_layout_config
from .core.font_resolver import resolve_font_family
from .core.math_utils import sanitize_prefix, unique_path
from .core.presets import (
    CARTOGRAPHY_PRESETS,
    DEFAULT_CARTOGRAPHY,
    DEFAULT_PALETTE,
    INDUSTRY_PRESETS,
    PALETTE_GROUPS,
    PALETTE_ORDER,
    TERRAIN_PALETTES,
)
from .core.product_registry import DEFAULT_PRODUCT_REGISTRY
from .core.qgis_compat import font_families
from .core.share_package import write_share_manifest
from .core.style_packs import LAYOUT_TEMPLATES
from .core.web_3d_viewer import generate_3d_web_viewer
from .ui.smart_defaults import DebouncedDemInspector
from .ui.task_controller import ProcessingTaskController


class TerrainStudioDock(QDockWidget):
    SETTINGS_OUTPUT = "terrain_product_studio/output_folder"

    def __init__(self, iface, parent=None):
        super().__init__("Terrain Product Studio", parent)
        self.iface = iface
        self.task_controller = ProcessingTaskController()
        self._last_results = None
        self._run_config = None
        self._run_parameters = None
        self._fonts_populated = False
        self._contour_suggestion = None
        self._last_layout_layers = None
        self._font_sync_guard = False
        self._last_run_manifest = None
        self._last_result_layers = {}
        self._last_layout_names = []
        self._restyle_canvas_timer = None
        self._dem_info = None
        self._suggestions = []
        self._suggested_stream_threshold = None
        self._stream_threshold_touched = False
        self._suggestion_buttons = {}
        self._build_ui()
        self._connect_signals()
        self._on_layer_changed(self.dem_combo.currentLayer())

    @staticmethod
    def tr(message):
        return QCoreApplication.translate("TerrainStudioDock", message)

    def _build_ui(self):
        # Long setup controls scroll independently while the run/progress bar
        # remains pinned to the bottom of the dock on small screens.
        root = QWidget(self)
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(4)

        body = QWidget(root)
        outer = QVBoxLayout(body)
        outer.setContentsMargins(8, 8, 8, 8)

        title = QLabel(f"<b>{self.tr('DEM → Terrain Product Package')}</b>")
        subtitle = QLabel(
            self.tr(
                "Select a DEM, check products and run. Analytical rasters preserve original raw values; "
                "cartographic layers are automatically styled and grouped."
            )
        )
        subtitle.setWordWrap(True)
        outer.addWidget(title)
        outer.addWidget(subtitle)

        input_group = QGroupBox(self.tr("1 · Input Data"))
        input_layout = QGridLayout(input_group)
        self.dem_combo = QgsMapLayerComboBox()
        # Qt6/QGIS4 scoped enum: QgsMapLayerProxyModel.Filter.RasterLayer
        try:
            self.dem_combo.setFilters(QgsMapLayerProxyModel.Filter.RasterLayer)
        except AttributeError:
            self.dem_combo.setFilters(getattr(QgsMapLayerProxyModel, "RasterLayer"))
        self.browse_dem_button = QPushButton(self.tr("Open DEM…"))
        self.band_spin = QSpinBox()
        self.band_spin.setRange(1, 1)
        self.inspect_button = QPushButton(self.tr("Inspect DEM"))
        input_layout.addWidget(QLabel(self.tr("DEM layer")), 0, 0)
        input_layout.addWidget(self.dem_combo, 0, 1)
        input_layout.addWidget(self.browse_dem_button, 0, 2)
        input_layout.addWidget(QLabel(self.tr("Elevation band")), 1, 0)
        input_layout.addWidget(self.band_spin, 1, 1)
        input_layout.addWidget(self.inspect_button, 1, 2)
        outer.addWidget(input_group)

        # Extent / ROI Group
        extent_group = QGroupBox(self.tr("2 · Processing Extent"))
        extent_layout = QGridLayout(extent_group)
        self.extent_combo = QComboBox()
        self.extent_combo.addItem(self.tr("Full DEM Layer Extent"), "full")
        self.extent_combo.addItem(self.tr("Current Map Canvas Extent"), "canvas")
        self.extent_combo.addItem(self.tr("Calculate from Another Layer Extent"), "layer")
        self.extent_layer_combo = QgsMapLayerComboBox()
        self.extent_layer_combo.setEnabled(False)
        self.extent_label = QLabel(self.tr("Extent: Full DEM coverage"))
        self.extent_label.setStyleSheet("color: #8b949e; font-size: 11px;")
        extent_layout.addWidget(QLabel(self.tr("Mode")), 0, 0)
        extent_layout.addWidget(self.extent_combo, 0, 1, 1, 2)
        extent_layout.addWidget(QLabel(self.tr("Boundary Layer")), 1, 0)
        extent_layout.addWidget(self.extent_layer_combo, 1, 1, 1, 2)
        extent_layout.addWidget(self.extent_label, 2, 0, 1, 3)
        outer.addWidget(extent_group)

        output_group = QGroupBox(self.tr("3 · Output"))
        output_layout = QGridLayout(output_group)
        default_temp = os.path.join(os.path.dirname(__file__), "temp")
        os.makedirs(default_temp, exist_ok=True)
        default_output = QgsSettings().value(self.SETTINGS_OUTPUT, default_temp, type=str)
        if not default_output:
            default_output = default_temp
        self.output_edit = QLineEdit(default_output)
        self.output_button = QPushButton(self.tr("Browse…"))
        self.prefix_edit = QLineEdit("terrain")
        self.prefix_edit.setPlaceholderText("terrain")
        output_layout.addWidget(QLabel(self.tr("Folder")), 0, 0)
        output_layout.addWidget(self.output_edit, 0, 1)
        output_layout.addWidget(self.output_button, 0, 2)
        output_layout.addWidget(QLabel(self.tr("File prefix")), 1, 0)
        output_layout.addWidget(self.prefix_edit, 1, 1, 1, 2)
        self.create_project_check = QCheckBox(
            self.tr("Create QGIS project (.qgz) in output folder")
        )
        self.create_project_check.setChecked(True)
        self.create_project_check.setToolTip(
            self.tr(
                "Saves the current project with all generated layers, styling, "
                "groups and the print layout as a .qgz next to the outputs."
            )
        )
        output_layout.addWidget(self.create_project_check, 2, 0, 1, 3)
        self.share_manifest_check = QCheckBox(
            self.tr("Create transparent share manifest (data, styles and layouts)")
        )
        self.share_manifest_check.setChecked(True)
        output_layout.addWidget(self.share_manifest_check, 3, 0, 1, 3)
        self.portable_dem_check = QCheckBox(
            self.tr("Include a portable DEM copy for sharing (slower)")
        )
        self.portable_dem_check.setChecked(False)
        self.portable_dem_check.setToolTip(
            self.tr(
                "Keeps one numeric GeoTIFF DEM beside the package so another user can "
                "open the source elevation data. This is not an RGB image and does not "
                "change the DEM values. Leave off to save time and disk space."
            )
        )
        output_layout.addWidget(self.portable_dem_check, 4, 0, 1, 3)
        outer.addWidget(output_group)

        self.tabs = QTabWidget()
        self.tabs.setMinimumHeight(285)
        self.tabs.addTab(self._scrollable_options_page(self._create_products_tab()), self.tr("Products"))
        self.tabs.addTab(self._scrollable_options_page(self._create_contour_tab()), self.tr("Contours"))
        self.tabs.addTab(self._scrollable_options_page(self._create_hydrology_tab()), self.tr("Hydrology"))
        self.assistant_tab_index = self.tabs.addTab(
            self._scrollable_options_page(self._create_assistant_tab()), self.tr("Assistant")
        )
        self.cartography_tab_index = self.tabs.addTab(
            self._scrollable_options_page(self._create_cartography_tab()), self.tr("Layout")
        )
        self.tabs.addTab(self._scrollable_options_page(self._create_settings_tab()), self.tr("Settings"))
        self.report_tab_index = self.tabs.addTab(self._create_report_tab(), self.tr("Inspect"))
        self._update_index_preview()
        self._design_sync_guard = False
        self._apply_design_preset()
        outer.addWidget(self.tabs, 1)

        scroll = QScrollArea(root)
        scroll.setObjectName("terrainSetupScroll")
        scroll.setWidgetResizable(True)
        try:
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        except AttributeError:  # Qt 5 unscoped enum
            scroll.setHorizontalScrollBarPolicy(getattr(Qt, "ScrollBarAlwaysOff"))
            scroll.setVerticalScrollBarPolicy(getattr(Qt, "ScrollBarAsNeeded"))
        try:
            scroll.setFrameShape(QFrame.Shape.NoFrame)
        except AttributeError:  # Qt 5 fallback
            scroll.setFrameShape(getattr(QFrame, "NoFrame"))
        scroll.setWidget(body)
        self.setup_scroll = scroll
        root_layout.addWidget(scroll, 1)

        footer = QWidget(root)
        footer.setObjectName("terrainActionFooter")
        footer_layout = QVBoxLayout(footer)
        footer_layout.setContentsMargins(8, 4, 8, 8)
        footer_layout.setSpacing(4)

        presets = QHBoxLayout()
        self.quick_button = QPushButton(self.tr("Quick Basemap"))
        self.full_button = QPushButton(self.tr("Select All"))
        self.clear_button = QPushButton(self.tr("Clear All"))
        presets.addWidget(self.quick_button)
        presets.addWidget(self.full_button)
        presets.addWidget(self.clear_button)
        footer_layout.addLayout(presets)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        footer_layout.addWidget(self.progress)

        actions = QHBoxLayout()
        self.run_button = QPushButton(self.tr("Build Product Package"))
        self.run_button.setDefault(True)
        self.cancel_button = QPushButton(self.tr("Cancel"))
        self.cancel_button.setEnabled(False)
        actions.addWidget(self.run_button, 1)
        actions.addWidget(self.cancel_button)
        footer_layout.addLayout(actions)

        # Quick Results Action Bar
        results_bar = QHBoxLayout()
        self.open_3d_button = QPushButton(self.tr("🌐 View 3D Web Map"))
        self.open_3d_button.setEnabled(True)
        self.open_3d_button.setToolTip(self.tr("Open standalone interactive 3D Web terrain in default web browser"))
        self.open_report_button = QPushButton(self.tr("📊 View Report"))
        self.open_report_button.setEnabled(True)
        self.open_report_button.setToolTip(self.tr("Open Topographic Intelligence Report dashboard in default web browser"))
        self.docs_button = QPushButton(self.tr("📖 Documentation"))
        self.docs_button.setToolTip(self.tr("Open online user manual and scientific documentation on GitHub"))
        self.restyle_button = QPushButton(self.tr("🎨 Apply Style to Existing Outputs"))
        self.restyle_button.setEnabled(False)
        self.restyle_button.setToolTip(
            self.tr(
                "Restyle the last run's canvas layers, QML style packs, layouts "
                "and 3D viewer with the current cartography — no pipeline re-run."
            )
        )
        results_bar.addWidget(self.open_3d_button)
        results_bar.addWidget(self.open_report_button)
        results_bar.addWidget(self.restyle_button)
        results_bar.addWidget(self.docs_button)
        footer_layout.addLayout(results_bar)
        root_layout.addWidget(footer, 0)

        self.setWidget(root)
        self.setMinimumWidth(400)
        self.resize(460, 680)

    def _scrollable_options_page(self, content):
        """Wrap an option page so a large form cannot stretch the whole dock."""

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        try:
            scroll.setFrameShape(QFrame.Shape.NoFrame)
        except AttributeError:  # Qt 5 unscoped enum
            scroll.setFrameShape(getattr(QFrame, "NoFrame"))
        try:
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        except AttributeError:
            scroll.setHorizontalScrollBarPolicy(getattr(Qt, "ScrollBarAlwaysOff"))
            scroll.setVerticalScrollBarPolicy(getattr(Qt, "ScrollBarAsNeeded"))
        scroll.setWidget(content)
        return scroll

    def _create_products_tab(self):
        tab = QWidget()
        layout = QGridLayout(tab)
        self.products = {}
        self._product_labels = {}
        # The default setup is intentionally small: the canonical DEM supplies
        # color, with multidirectional hillshade, peaks and smoothed contours.
        # Everything analytical stays opt-in via presets or Select All.
        definitions = tuple(
            (
                product.parameter,
                self.tr(product.ui_label),
                product.default_enabled,
            )
            for product in DEFAULT_PRODUCT_REGISTRY.product_grid_specs()
        )
        # Industry preset combo: one click ticks a whole job-specific set,
        # leaving every checkbox editable afterwards.
        self.industry_combo = QComboBox()
        self.industry_combo.addItem(self.tr("Custom selection"), "")
        for key, (label, _) in INDUSTRY_PRESETS.items():
            self.industry_combo.addItem(self.tr(label), key)
        layout.addWidget(self.industry_combo, 0, 0, 1, 2)
        # Two-column compact grid: halves the Products tab height and keeps
        # the whole dock short enough that the Run button rarely needs scrolling.
        # QCheckBox cannot wrap text, so each item pairs a bare checkbox with a
        # word-wrapping QLabel — labels stay readable at any dock width.
        for index, (key, label, checked) in enumerate(definitions):
            item = QWidget()
            item_row = QHBoxLayout(item)
            item_row.setContentsMargins(0, 0, 0, 0)
            item_row.setSpacing(4)
            checkbox = QCheckBox()
            checkbox.setChecked(checked)
            item_label = QLabel(label)
            item_label.setWordWrap(True)
            item_row.addWidget(checkbox)
            item_row.addWidget(item_label, 1)
            self.products[key] = checkbox
            self._product_labels[key] = label
            layout.addWidget(item, 1 + index // 2, index % 2)
        layout.setColumnStretch(1, 1)
        note = QLabel(
            self.tr(
                "💡 Flow dependencies are automatic: SPI/STI, landslide hazard and "
                "multi-hazard trigger hydrology before analysis when no accumulation "
                "raster is supplied. Slope is never used as a drainage proxy."
            )
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: #8a8a8a; font-size: 11px; margin-top: 8px;")
        layout.addWidget(note, 2 + (len(definitions) - 1) // 2, 0, 1, 2)
        last_row = 2 + (len(definitions) - 1) // 2
        layout.setRowStretch(last_row, 1)
        return tab

    def _create_contour_tab(self):
        tab = QWidget()
        layout = QFormLayout(tab)
        self.contour_check = QCheckBox(self.tr("Generate elevation contours"))
        self.contour_check.setChecked(True)
        self.contour_interval = QDoubleSpinBox()
        self.contour_interval.setDecimals(3)
        self.contour_interval.setRange(0.001, 1000000.0)
        self.contour_interval.setValue(10.0)
        self.contour_interval.setSuffix(f" {self.tr('Z units')}")
        self.index_multiplier = QSpinBox()
        self.index_multiplier.setRange(1, 20)
        self.index_multiplier.setValue(5)
        self.index_preview = QLabel()
        layout.addRow(self.contour_check)
        suggestion_row = QHBoxLayout()
        self.contour_suggestion_label = QLabel(
            self.tr("Suggested interval: — (run Inspect DEM)")
        )
        self.contour_suggestion_label.setStyleSheet(
            "color: #8b949e; font-size: 11px;"
        )
        self.contour_suggestion_label.setWordWrap(True)
        self.apply_suggestion_button = QPushButton(self.tr("Apply"))
        self.apply_suggestion_button.setEnabled(False)
        suggestion_row.addWidget(self.contour_suggestion_label, 1)
        suggestion_row.addWidget(self.apply_suggestion_button)
        layout.addRow(suggestion_row)
        layout.addRow(self.tr("Contour interval"), self.contour_interval)
        layout.addRow(self.tr("Index multiplier (every Nth line)"), self.index_multiplier)
        layout.addRow(self.tr("Index contour interval"), self.index_preview)
        self.spot_pct_spin = QSpinBox()
        self.spot_pct_spin.setRange(0, 100)
        self.spot_pct_spin.setValue(80)
        self.spot_pct_spin.setSuffix(" %")
        self.spot_pct_spin.setSpecialValueText(self.tr("Off"))
        self.spot_pct_spin.setToolTip(
            self.tr(
                "Only keep peak points whose elevation is in the top this many "
                "percent of the terrain relief. 0 keeps every local peak."
            )
        )
        layout.addRow(
            self.tr("Peak point threshold (% of relief)"), self.spot_pct_spin
        )
        self.smoothing_combo = QComboBox()
        self.smoothing_combo.addItems(
            [self.tr("Off"), self.tr("Light"), self.tr("Medium"), self.tr("Heavy")]
        )
        self.smoothing_combo.setCurrentIndex(2)
        self.simplify_tolerance = QDoubleSpinBox()
        self.simplify_tolerance.setRange(0.0, 100000.0)
        self.simplify_tolerance.setDecimals(1)
        self.simplify_tolerance.setValue(0.0)
        self.simplify_tolerance.setSuffix(f" {self.tr('map units')}")
        self.simplify_tolerance.setSpecialValueText(self.tr("Off"))
        layout.addRow(self.tr("Smoothness level"), self.smoothing_combo)
        layout.addRow(self.tr("Simplify before smoothing"), self.simplify_tolerance)
        note = QLabel(
            self.tr(
                "Contours are saved in GeoPackage. Styled with 3-tier USGS cartography: "
                "thin minor lines, bold index lines, and master contours with curved labels."
            )
        )
        note.setWordWrap(True)
        layout.addRow(note)
        self._update_index_preview()
        return tab

    def _create_hydrology_tab(self):
        tab = QWidget()
        layout = QFormLayout(tab)
        self.hydrology_check = QCheckBox(self.tr("Extract continuous Strahler river network"))
        self.hydrology_check.setChecked(False)
        self.stream_threshold = QDoubleSpinBox()
        self.stream_threshold.setDecimals(2)
        self.stream_threshold.setRange(0.01, 1000000000.0)
        self.stream_threshold.setValue(25.0)
        self.stream_threshold.setSuffix(" ha")
        self.twi_check = QCheckBox(self.tr("Topographic Wetness Index (TWI)"))
        self.twi_check.setChecked(False)
        self.basins_check = QCheckBox(self.tr("Save watershed basin raster"))
        self.basins_check.setChecked(False)
        layout.addRow(self.hydrology_check)
        layout.addRow(self.tr("Minimum contributing area"), self.stream_threshold)
        self.stream_smoothing_combo = QComboBox()
        self.stream_smoothing_combo.addItems(
            [self.tr("Off"), self.tr("Light"), self.tr("Medium"), self.tr("Heavy")]
        )
        layout.addRow(self.tr("River smoothness level"), self.stream_smoothing_combo)
        self.river_width_factor_spin = QDoubleSpinBox()
        self.river_width_factor_spin.setRange(0.25, 10.0)
        self.river_width_factor_spin.setDecimals(2)
        self.river_width_factor_spin.setSingleStep(0.25)
        self.river_width_factor_spin.setValue(1.0)
        self.river_width_factor_spin.setToolTip(
            self.tr(
                "Multiplies the Horton river width estimate W = 3·√A (m). "
                "Factor 1.0 = real hydraulic geometry (see Assistant tab)."
            )
        )
        self.river_depth_factor_spin = QDoubleSpinBox()
        self.river_depth_factor_spin.setRange(0.25, 5.0)
        self.river_depth_factor_spin.setDecimals(2)
        self.river_depth_factor_spin.setSingleStep(0.25)
        self.river_depth_factor_spin.setValue(1.0)
        self.river_depth_factor_spin.setToolTip(
            self.tr(
                "Multiplies the power-law river depth estimate D = 0.55·W^0.6 (m). "
                "Factor 1.0 = real hydraulic geometry (see Assistant tab)."
            )
        )
        layout.addRow(self.tr("River width factor"), self.river_width_factor_spin)
        layout.addRow(self.tr("River depth factor"), self.river_depth_factor_spin)
        layout.addRow(self.twi_check)
        layout.addRow(self.basins_check)
        self.hydrology_note = QLabel(
            self.tr(
                "Uses priority-flood depression filling and deterministic D8 flow direction without GRASS. "
                "Continuous river polylines are graded into 4 Strahler stream orders with specialized symbology."
            )
        )
        self.hydrology_note.setWordWrap(True)
        layout.addRow(self.hydrology_note)
        return tab

    def _create_assistant_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        help_label = QLabel(
            self.tr(
                "Smart defaults are derived automatically from the selected "
                "DEM (contours, stream threshold, river dimensions, 3D "
                "exaggeration, working CRS). Apply one suggestion or all."
            )
        )
        help_label.setWordWrap(True)
        layout.addWidget(help_label)
        self.assistant_status = QLabel(
            self.tr("Select a DEM layer — suggestions appear automatically.")
        )
        self.assistant_status.setWordWrap(True)
        self.assistant_status.setStyleSheet("color: #777;")
        layout.addWidget(self.assistant_status)
        self.assistant_rows = QWidget()
        self.assistant_rows_layout = QVBoxLayout(self.assistant_rows)
        self.assistant_rows_layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.assistant_rows)
        self.apply_all_suggestions_button = QPushButton(
            self.tr("Apply all suggestions")
        )
        self.apply_all_suggestions_button.setEnabled(False)
        layout.addWidget(self.apply_all_suggestions_button)
        layout.addStretch(1)
        return page

    def _create_cartography_tab(self):
        tab = QWidget()
        layout = QFormLayout(tab)
        self.design_preset_combo = QComboBox()
        for key, design in DESIGN_PRESETS.items():
            self.design_preset_combo.addItem(design.label, key)
        self.design_preset_combo.addItem(self.tr("Custom design"), "")
        default_design_index = self.design_preset_combo.findData(
            DEFAULT_DESIGN_PRESET
        )
        if default_design_index >= 0:
            self.design_preset_combo.setCurrentIndex(default_design_index)
        self.design_description = QLabel()
        self.design_description.setWordWrap(True)
        self.design_description.setMinimumHeight(34)
        self.design_preview = QLabel()
        self.design_preview.setFixedSize(320, 226)
        self.design_preview.setStyleSheet(
            "border: 1px solid #747474; border-radius: 4px; "
            "background: #252525; color: #b8b8b8; padding: 2px;"
        )
        try:
            self.design_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        except AttributeError:
            self.design_preview.setAlignment(getattr(Qt, "AlignCenter"))
        self.cartography_combo = QComboBox()
        for key, preset in CARTOGRAPHY_PRESETS.items():
            self.cartography_combo.addItem(preset["label"], key)
        default_index = self.cartography_combo.findData(DEFAULT_CARTOGRAPHY)
        if default_index >= 0:
            self.cartography_combo.setCurrentIndex(default_index)
        self.cartography_description = QLabel()
        self.cartography_description.setWordWrap(True)
        self.theme_preview = QLabel()
        self.theme_preview.setFixedSize(164, 84)
        self.layout_template_combo = QComboBox()
        for key, template in LAYOUT_TEMPLATES.items():
            self.layout_template_combo.addItem(template.label, key)
        default_layout_index = self.layout_template_combo.findData("classic_topo")
        if default_layout_index >= 0:
            self.layout_template_combo.setCurrentIndex(default_layout_index)
        self.grid_mode_combo = QComboBox()
        self.grid_mode_combo.addItem(self.tr("Map / DEM CRS"), "map_crs")
        self.grid_mode_combo.addItem("WGS 84 · EPSG:4326", "wgs84")
        self.grid_mode_combo.addItem(
            self.tr("Dual · Map CRS + WGS 84"), "dual"
        )
        self.grid_mode_combo.addItem(self.tr("Custom EPSG…"), "custom")
        self.grid_custom_edit = QLineEdit("EPSG:32648")
        self.grid_custom_edit.setPlaceholderText("EPSG:32648")
        self.grid_custom_edit.setEnabled(False)
        try:
            self.theme_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        except AttributeError:
            self.theme_preview.setAlignment(getattr(Qt, "AlignCenter"))
        paper_row = QWidget()
        paper_layout = QHBoxLayout(paper_row)
        paper_layout.setContentsMargins(0, 0, 0, 0)
        self.paper_combo = QComboBox()
        for key, label in (
            ("auto", self.tr("Auto (fit extent)")),
            ("a4", "A4"),
            ("a3", "A3"),
            ("a1", "A1"),
        ):
            self.paper_combo.addItem(label, key)
        self.orientation_combo = QComboBox()
        for key, label in (
            ("auto", self.tr("Auto")),
            ("portrait", self.tr("Portrait")),
            ("landscape", self.tr("Landscape")),
        ):
            self.orientation_combo.addItem(label, key)
        paper_layout.addWidget(self.paper_combo)
        paper_layout.addWidget(self.orientation_combo)
        self.create_layout_button = QPushButton(self.tr("Create Layout Now"))
        self.create_layout_button.setEnabled(False)
        # Plain combo populated lazily on first Layout-tab visit: scanning the
        # system font database at dock startup was a noticeable UI freeze.
        self.font_combo = QComboBox()
        self.style_pack_font_check = QCheckBox(
            self.tr("Use layout-recommended font")
        )
        self.style_pack_font_check.setChecked(True)
        self.font_resolution_label = QLabel()
        self.font_resolution_label.setWordWrap(True)
        self.layout_name_edit = QLineEdit("Terrain Map")
        self.layout_extent_combo = QComboBox()
        self.layout_extent_combo.addItem(self.tr("Full generated extent"), "full")
        self.layout_extent_combo.addItem(self.tr("Current map canvas"), "canvas")
        self.map_title_edit = QLineEdit("TOPOGRAPHIC TERRAIN MAP")
        self.map_subtitle_edit = QLineEdit("DEM-derived relief, contours and drainage")
        self.map_author_edit = QLineEdit("Nguyễn Văn Tín")
        self.map_source_edit = QLineEdit("Digital Elevation Model")
        self.create_layout_check = QCheckBox(self.tr("Create Print Layout after processing"))
        self.create_layout_check.setChecked(True)
        self.grid_check = QCheckBox(self.tr("Coordinate border and grid"))
        self.grid_check.setChecked(True)
        self.legend_check = QCheckBox(self.tr("Show map legend"))
        self.legend_check.setChecked(True)
        self.open_layout_check = QCheckBox(self.tr("Open Layout Designer when finished"))
        self.open_layout_check.setChecked(False)
        export_row = QWidget()
        export_layout = QHBoxLayout(export_row)
        export_layout.setContentsMargins(0, 0, 0, 0)
        self.export_pdf_check = QCheckBox("PDF")
        self.export_png_check = QCheckBox("PNG")
        export_layout.addWidget(self.export_pdf_check)
        export_layout.addWidget(self.export_png_check)
        export_layout.addStretch(1)
        self.layout_dpi = QSpinBox()
        self.layout_dpi.setRange(72, 1200)
        self.layout_dpi.setValue(300)
        self.layout_dpi.setSuffix(" dpi")
        self.style_pack_summary = QLabel()
        self.style_pack_summary.setWordWrap(True)
        self.layout_queue = QListWidget()
        self.layout_queue.setMaximumHeight(112)
        self.layout_queue.setToolTip(
            self.tr(
                "Leave empty to generate the current design as one default layout. "
                "Add designs here to create a map book."
            )
        )
        queue_buttons = QWidget()
        queue_button_layout = QHBoxLayout(queue_buttons)
        queue_button_layout.setContentsMargins(0, 0, 0, 0)
        self.add_layout_button = QPushButton(self.tr("Add current"))
        self.duplicate_layout_button = QPushButton(self.tr("Duplicate"))
        self.remove_layout_button = QPushButton(self.tr("Remove"))
        self.move_layout_up_button = QPushButton("↑")
        self.move_layout_down_button = QPushButton("↓")
        self.create_all_layouts_button = QPushButton(self.tr("Generate all"))
        queue_button_layout.addWidget(self.add_layout_button)
        queue_button_layout.addWidget(self.duplicate_layout_button)
        queue_button_layout.addWidget(self.remove_layout_button)
        queue_button_layout.addWidget(self.move_layout_up_button)
        queue_button_layout.addWidget(self.move_layout_down_button)
        queue_button_layout.addWidget(self.create_all_layouts_button)
        self.recipe_inspector_label = QLabel()
        self.recipe_inspector_label.setWordWrap(True)
        self.qa_layout_button = QPushButton(self.tr("Check map readiness"))
        layout.addRow(self.tr("Design preset"), self.design_preset_combo)
        layout.addRow(self.design_description)
        layout.addRow(self.design_preview)

        self.advanced_design_group = QGroupBox(self.tr("Advanced overrides"))
        self.advanced_design_group.setCheckable(True)
        self.advanced_design_group.setChecked(False)
        advanced_outer = QVBoxLayout(self.advanced_design_group)
        advanced_outer.setContentsMargins(8, 4, 8, 8)
        self.advanced_design_body = QWidget()
        advanced_layout = QFormLayout(self.advanced_design_body)
        advanced_layout.addRow(self.tr("Map style"), self.cartography_combo)
        advanced_layout.addRow(self.theme_preview)
        advanced_layout.addRow(self.cartography_description)
        advanced_layout.addRow(
            self.tr("Layout template"), self.layout_template_combo
        )
        advanced_layout.addRow(self.style_pack_summary)
        advanced_layout.addRow(self.style_pack_font_check)
        advanced_layout.addRow(self.tr("Font family"), self.font_combo)
        advanced_layout.addRow(self.font_resolution_label)
        advanced_layout.addRow(self.grid_check)
        advanced_layout.addRow(self.legend_check)
        advanced_layout.addRow(self.tr("Coordinate grid"), self.grid_mode_combo)
        advanced_layout.addRow(self.tr("Custom grid CRS"), self.grid_custom_edit)
        advanced_outer.addWidget(self.advanced_design_body)
        self.advanced_design_body.setVisible(False)
        layout.addRow(self.advanced_design_group)
        layout.addRow(self.tr("Paper size"), paper_row)
        layout.addRow(self.create_layout_button)
        layout.addRow(self.tr("Map book queue"), self.layout_queue)
        queue_hint = QLabel(
            self.tr(
                "Empty queue = one current layout. Add several designs, then use ↑/↓ to order them."
            )
        )
        queue_hint.setWordWrap(True)
        layout.addRow(queue_hint)
        layout.addRow(queue_buttons)
        layout.addRow(self.recipe_inspector_label)
        layout.addRow(self.qa_layout_button)
        layout.addRow(self.tr("Layout name"), self.layout_name_edit)
        layout.addRow(self.tr("Map extent"), self.layout_extent_combo)
        layout.addRow(self.tr("Map title"), self.map_title_edit)
        layout.addRow(self.tr("Subtitle"), self.map_subtitle_edit)
        layout.addRow(self.tr("Author / Organization"), self.map_author_edit)
        layout.addRow(self.tr("Data source"), self.map_source_edit)
        layout.addRow(self.create_layout_check)
        layout.addRow(self.open_layout_check)
        layout.addRow(self.tr("Export layout"), export_row)
        layout.addRow(self.tr("Resolution"), self.layout_dpi)
        return tab

    def _create_settings_tab(self):
        tab = QWidget()
        layout = QFormLayout(tab)
        self.z_unit_combo = QComboBox()
        self.z_unit_combo.addItems([self.tr("Meters"), self.tr("Feet")])
        self.palette_combo = QComboBox()
        # Grouped by family with separators, in the same order as the
        # Processing PALETTE enum (PALETTE_ORDER). Separator entries carry no
        # user data and are skipped when resolving the algorithm index.
        for group_index, (group_key, group_label, keys) in enumerate(PALETTE_GROUPS):
            if group_index > 0:
                self.palette_combo.insertSeparator(self.palette_combo.count())
            for key in keys:
                preset = TERRAIN_PALETTES[key]
                stops = preset.get("elev_stops") or preset["stops"]
                self.palette_combo.addItem(
                    self._palette_preview(stops), preset["label"], key
                )
        default_index = self.palette_combo.findData(DEFAULT_PALETTE)
        if default_index >= 0:
            self.palette_combo.setCurrentIndex(default_index)
        self.palette_combo.setEnabled(True)
        self.compression_combo = QComboBox()
        self.compression_combo.addItems(["DEFLATE", "ZSTD", "LZW", "NONE"])
        self.web_3d_quality_combo = QComboBox()
        self.web_3d_quality_combo.addItems(
            [
                self.tr("Fast · 256 samples"),
                self.tr("Balanced · 384 samples"),
                self.tr("High · 512 samples"),
            ]
        )
        self.web_3d_quality_combo.setCurrentIndex(1)
        self.auto_reproject_check = QCheckBox(self.tr("Automatically reproject geographic DEM to UTM"))
        self.auto_reproject_check.setChecked(True)
        self.vertical_exaggeration = QDoubleSpinBox()
        self.vertical_exaggeration.setRange(0.01, 100.0)
        self.vertical_exaggeration.setDecimals(2)
        self.vertical_exaggeration.setValue(1.0)
        self.vertical_exaggeration.setToolTip(
            self.tr(
                "Hillshade keeps the true elevation scale at 1.0 — slopes and "
                "gradient directions are computed from real heights. A Z "
                "factor only distorts the shading; use the 3D viewer's own "
                "exaggeration for display."
            )
        )
        self.azimuth = QDoubleSpinBox()
        self.azimuth.setRange(0.0, 360.0)
        self.azimuth.setValue(315.0)
        self.azimuth.setSuffix("°")
        self.altitude = QDoubleSpinBox()
        self.altitude.setRange(0.0, 90.0)
        self.altitude.setValue(45.0)
        self.altitude.setSuffix("°")
        self.zevenbergen_check = QCheckBox(self.tr("Zevenbergen–Thorne (smoother slopes)"))
        self.zevenbergen_check.setChecked(False)

        self.bundle_check = QCheckBox(self.tr("Export all products to a single GeoPackage bundle"))
        self.bundle_check.setChecked(True)

        self.multi_hazard_weight_landslide = QDoubleSpinBox()
        self.multi_hazard_weight_landslide.setRange(0.0, 1.0)
        self.multi_hazard_weight_landslide.setDecimals(2)
        self.multi_hazard_weight_landslide.setSingleStep(0.05)
        self.multi_hazard_weight_landslide.setValue(0.5)
        self.multi_hazard_weight_twi = QDoubleSpinBox()
        self.multi_hazard_weight_twi.setRange(0.0, 1.0)
        self.multi_hazard_weight_twi.setDecimals(2)
        self.multi_hazard_weight_twi.setSingleStep(0.05)
        self.multi_hazard_weight_twi.setValue(0.3)
        self.multi_hazard_weight_slope = QDoubleSpinBox()
        self.multi_hazard_weight_slope.setRange(0.0, 1.0)
        self.multi_hazard_weight_slope.setDecimals(2)
        self.multi_hazard_weight_slope.setSingleStep(0.05)
        self.multi_hazard_weight_slope.setValue(0.2)

        layout.addRow(self.tr("Elevation unit"), self.z_unit_combo)
        layout.addRow(self.tr("Elevation color palette"), self.palette_combo)
        layout.addRow(self.tr("GeoTIFF compression"), self.compression_combo)
        layout.addRow(self.tr("Web 3D quality"), self.web_3d_quality_combo)
        performance_note = QLabel(
            self.tr(
                "Runs in a cancellable QGIS background task. GeoTIFF creation uses all CPU cores; "
                "independent Web 3D raster reads run concurrently."
            )
        )
        performance_note.setWordWrap(True)
        layout.addRow(performance_note)
        layout.addRow(self.auto_reproject_check)
        layout.addRow(self.tr("Hillshade vertical exaggeration"), self.vertical_exaggeration)
        layout.addRow(self.tr("Light azimuth"), self.azimuth)
        layout.addRow(self.tr("Light altitude"), self.altitude)
        layout.addRow(self.zevenbergen_check)
        note = QLabel(self.tr("Default Horn method is ideal for rugged terrain; Zevenbergen–Thorne fits smooth surfaces."))
        note.setWordWrap(True)
        layout.addRow(note)
        layout.addRow(self.bundle_check)
        weight_notes = QLabel(self.tr("Multi-hazard weights (landslide / TWI / slope, normalized)"))
        weight_notes.setWordWrap(True)
        layout.addRow(weight_notes)
        weight_row = QHBoxLayout()
        weight_row.addWidget(self.multi_hazard_weight_landslide, 1)
        weight_row.addWidget(self.multi_hazard_weight_twi, 1)
        weight_row.addWidget(self.multi_hazard_weight_slope, 1)
        layout.addRow(weight_row)

        self.z_scale_spin = QDoubleSpinBox()
        self.z_scale_spin.setRange(0.001, 100000.0)
        self.z_scale_spin.setDecimals(3)
        self.z_scale_spin.setValue(1.0)
        self.z_scale_spin.setToolTip(self.tr("Vertical exaggeration applied to the printed model"))
        self.base_thickness_spin = QDoubleSpinBox()
        self.base_thickness_spin.setRange(0.0, 100000.0)
        self.base_thickness_spin.setDecimals(3)
        self.base_thickness_spin.setValue(0.0)
        self.base_thickness_spin.setToolTip(self.tr("Solid base plate added below the lowest elevation (0 = surface only)"))
        self.stl_button = QPushButton(self.tr("Export 3D print model (STL)"))
        self.obj_button = QPushButton(self.tr("OBJ"))
        export_row = QHBoxLayout()
        export_row.addWidget(self.z_scale_spin, 1)
        export_row.addWidget(self.base_thickness_spin, 1)
        export_row.addWidget(self.stl_button, 2)
        export_row.addWidget(self.obj_button, 1)
        layout.addRow(export_row)
        return tab

    def _create_report_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        tab_actions = QHBoxLayout()
        self.tab_open_3d_button = QPushButton(self.tr("🌐 Open 3D Map in Browser"))
        self.tab_open_3d_button.setEnabled(False)
        self.tab_open_report_button = QPushButton(self.tr("📊 Open Intelligence Report"))
        self.tab_open_report_button.setEnabled(False)
        tab_actions.addWidget(self.tab_open_3d_button)
        tab_actions.addWidget(self.tab_open_report_button)
        layout.addLayout(tab_actions)

        history_label = QLabel(self.tr("Recent runs — click to open the output folder and report"))
        history_label.setStyleSheet("color: #8a8a8a; font-size: 11px; margin-top: 6px;")
        layout.addWidget(history_label)
        self.history_list = QListWidget()
        self.history_list.setWordWrap(True)
        self.history_list.setMaximumHeight(140)
        layout.addWidget(self.history_list)

        self.report_edit = QPlainTextEdit()
        self.report_edit.setReadOnly(True)
        self.report_edit.setPlaceholderText(self.tr("Click 'Inspect DEM' to view CRS, pixel size, NoData and contour suggestions."))
        layout.addWidget(self.report_edit)
        return tab

    def _connect_signals(self):
        self.dem_combo.layerChanged.connect(self._on_layer_changed)
        self.browse_dem_button.clicked.connect(self._browse_dem)
        self.inspect_button.clicked.connect(self.inspect_dem)
        self.output_button.clicked.connect(self._browse_output)
        self.contour_interval.valueChanged.connect(self._update_index_preview)
        self.index_multiplier.valueChanged.connect(self._update_index_preview)
        self.z_unit_combo.currentIndexChanged.connect(self._update_index_preview)
        self.hydrology_check.toggled.connect(self._update_hydrology_controls)
        # Assistant: debounced asynchronous DEM inspection (700 ms), sharing
        # the manual Inspect DEM sink with a generation counter.
        self.dem_inspector = DebouncedDemInspector(self)
        self.dem_inspector.inspected.connect(self._on_dem_inspected)
        self.dem_inspector.failed.connect(self._on_dem_inspect_failed)
        self.band_spin.valueChanged.connect(self._on_dem_input_changed)
        self.stream_threshold.valueChanged.connect(self._mark_stream_threshold_touched)
        self.apply_all_suggestions_button.clicked.connect(
            self._apply_all_suggestions
        )
        self.cartography_combo.currentIndexChanged.connect(
            self._on_cartography_preset_changed
        )
        self.cartography_combo.currentIndexChanged.connect(
            self._mark_design_custom
        )
        self.layout_template_combo.currentIndexChanged.connect(
            self._on_layout_template_changed
        )
        self.layout_template_combo.currentIndexChanged.connect(
            self._mark_design_custom
        )
        self.design_preset_combo.currentIndexChanged.connect(
            self._apply_design_preset
        )
        self.advanced_design_group.toggled.connect(
            self.advanced_design_body.setVisible
        )
        self.palette_combo.currentIndexChanged.connect(self._mark_design_custom)
        # Live restyle: cartography controls re-apply styles to the last run's
        # outputs (debounced — canvas at 600 ms, viewer at 1.5 s). Only visual
        # state is touched; the pipeline is never re-run.
        self.cartography_combo.currentIndexChanged.connect(
            self._schedule_live_restyle
        )
        self.palette_combo.currentIndexChanged.connect(
            self._schedule_live_restyle
        )
        self.design_preset_combo.currentIndexChanged.connect(
            self._schedule_live_restyle
        )
        self.font_combo.currentTextChanged.connect(self._schedule_live_restyle)
        self.grid_mode_combo.currentIndexChanged.connect(
            self._on_grid_mode_changed
        )
        self.grid_mode_combo.currentIndexChanged.connect(
            self._mark_design_custom
        )
        self.grid_custom_edit.textChanged.connect(self._mark_design_custom)
        self.create_layout_check.toggled.connect(self._update_layout_controls)
        self.apply_suggestion_button.clicked.connect(self._apply_contour_suggestion)
        self.create_layout_button.clicked.connect(self._create_layout_now)
        self.create_all_layouts_button.clicked.connect(self._create_all_layouts_now)
        self.add_layout_button.clicked.connect(self._add_current_layout_to_queue)
        self.duplicate_layout_button.clicked.connect(self._duplicate_queued_layout)
        self.remove_layout_button.clicked.connect(self._remove_queued_layout)
        self.move_layout_up_button.clicked.connect(
            lambda: self._move_queued_layout(-1)
        )
        self.move_layout_down_button.clicked.connect(
            lambda: self._move_queued_layout(1)
        )
        self.qa_layout_button.clicked.connect(self._show_layout_qa)
        self.style_pack_font_check.toggled.connect(self._on_style_pack_font_toggled)
        self.font_combo.currentTextChanged.connect(self._refresh_font_resolution)
        self.quick_button.clicked.connect(self._select_quick)
        self.full_button.clicked.connect(self._select_all)
        self.clear_button.clicked.connect(self._clear_selection)
        self.run_button.clicked.connect(self.run)
        self.cancel_button.clicked.connect(self.cancel_task)
        self.open_3d_button.clicked.connect(self._open_3d_map)
        self.open_report_button.clicked.connect(self._open_report)
        self.tab_open_3d_button.clicked.connect(self._open_3d_map)
        self.tab_open_report_button.clicked.connect(self._open_report)
        self.industry_combo.currentIndexChanged.connect(self._apply_industry_preset)
        self.stl_button.clicked.connect(lambda: self._export_3d_mesh("stl"))
        self.obj_button.clicked.connect(lambda: self._export_3d_mesh("obj"))
        self.history_list.itemClicked.connect(self._open_history_entry)
        self.docs_button.clicked.connect(self._open_online_docs)
        self.extent_combo.currentIndexChanged.connect(self._on_extent_mode_changed)
        self.extent_layer_combo.layerChanged.connect(self._on_extent_mode_changed)
        self.tabs.currentChanged.connect(self._on_tab_changed)
        self.restyle_button.clicked.connect(self._apply_style_to_outputs)
        self._update_hydrology_controls()
        self._update_layout_controls()
        self._on_extent_mode_changed()

    def _on_extent_mode_changed(self):
        mode = self.extent_combo.currentData()
        self.extent_layer_combo.setEnabled(mode == "layer")
        if mode == "full":
            self.extent_label.setText(self.tr("Extent: Full DEM coverage"))
        elif mode == "canvas":
            if self.iface and self.iface.mapCanvas():
                ext = self.iface.mapCanvas().extent()
                self.extent_label.setText(f"Map Canvas: ({ext.xMinimum():.1f}, {ext.yMinimum():.1f}) → ({ext.xMaximum():.1f}, {ext.yMaximum():.1f})")
            else:
                self.extent_label.setText(self.tr("Extent: Current map canvas view"))
        elif mode == "layer":
            layer = self.extent_layer_combo.currentLayer()
            if layer and layer.isValid():
                ext = layer.extent()
                self.extent_label.setText(f"{layer.name()}: ({ext.xMinimum():.1f}, {ext.yMinimum():.1f}) → ({ext.xMaximum():.1f}, {ext.yMaximum():.1f})")
            else:
                self.extent_label.setText(self.tr("No boundary layer selected"))

    def _open_online_docs(self):
        QDesktopServices.openUrl(QUrl("https://github.com/hulauwa/terrain-product-studio"))

    def _open_3d_map(self):
        path = getattr(self, "_last_3d_path", None)
        folder = self.output_edit.text().strip()
        prefix = sanitize_prefix(self.prefix_edit.text())

        if not path or not os.path.exists(path):
            candidate = os.path.join(folder, f"{prefix}_interactive_3d_terrain.html")
            if os.path.exists(candidate):
                path = candidate
                self._last_3d_path = candidate
            elif os.path.isdir(folder):
                for f in os.listdir(folder):
                    if f.endswith(".html") and "3d" in f.lower():
                        candidate = os.path.join(folder, f)
                        path = candidate
                        self._last_3d_path = candidate
                        break

        if path and os.path.exists(path):
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))
        else:
            layer = self.dem_combo.currentLayer()
            if layer and layer.isValid():
                os.makedirs(folder, exist_ok=True)
                v3d_target = os.path.join(folder, f"{prefix}_interactive_3d_terrain.html")
                try:
                    dem_path = layer.source().split("|")[0]
                    generate_3d_web_viewer(
                        dem_path=dem_path,
                        output_html_path=v3d_target,
                        title=f"{prefix.title()} 3D Interactive WebGIS Studio",
                    )
                    if os.path.exists(v3d_target):
                        self._last_3d_path = v3d_target
                        QDesktopServices.openUrl(QUrl.fromLocalFile(v3d_target))
                        return
                except Exception as err:
                    QMessageBox.warning(self, self.tr("3D Map Generation"), f"Could not generate 3D Map: {err}")
                    return

            QMessageBox.information(
                self,
                self.tr("3D Interactive Map"),
                self.tr("No 3D Map HTML file has been generated yet. Please select a DEM layer and run the package with 'Interactive 3D Web Terrain Viewer' checked."),
            )

    def _open_report(self):
        path = getattr(self, "_last_report_html_path", None)
        folder = self.output_edit.text().strip()
        prefix = sanitize_prefix(self.prefix_edit.text())

        if not path or not os.path.exists(path):
            candidate = os.path.join(folder, f"{prefix}_topographic_intelligence_report.html")
            if os.path.exists(candidate):
                path = candidate
                self._last_report_html_path = candidate
            elif os.path.isdir(folder):
                for f in os.listdir(folder):
                    if f.endswith(".html") and "report" in f.lower():
                        candidate = os.path.join(folder, f)
                        path = candidate
                        self._last_report_html_path = candidate
                        break

        if path and os.path.exists(path):
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))
        else:
            layer = self.dem_combo.currentLayer()
            if layer and layer.isValid():
                os.makedirs(folder, exist_ok=True)
                intel_target = os.path.join(folder, f"{prefix}_topographic_intelligence_report.html")
                try:
                    dem_path = layer.source().split("|")[0]
                    generate_intelligence_report(
                        dem_path=dem_path,
                        output_html_path=intel_target,
                        title=f"{prefix.title()} Topographic Intelligence Report",
                    )
                    if os.path.exists(intel_target):
                        self._last_report_html_path = intel_target
                        QDesktopServices.openUrl(QUrl.fromLocalFile(intel_target))
                        return
                except Exception as err:
                    QMessageBox.warning(self, self.tr("Intelligence Report"), f"Could not generate Report: {err}")
                    return

            QMessageBox.information(
                self,
                self.tr("Intelligence Report"),
                self.tr("No Topographic Intelligence Report has been generated yet. Please select a DEM layer and run the package with 'Topographic Intelligence Report' checked."),
            )

    def _on_layer_changed(self, layer):
        bands = layer.bandCount() if layer is not None and layer.isValid() else 1
        self.band_spin.setRange(1, max(1, bands))
        self.band_spin.setValue(1)
        self._contour_suggestion = None
        self.contour_suggestion_label.setText(
            self.tr("Suggested interval: — (run Inspect DEM)")
        )
        self.apply_suggestion_button.setEnabled(False)
        # A new DEM invalidates every smart default (the next inspection
        # recomputes them; the stream threshold is only auto-sent until the
        # user touches the spinbox again).
        self._dem_info = None
        self._suggestions = []
        self._suggested_stream_threshold = None
        self._stream_threshold_touched = False
        self._rebuild_assistant_rows()
        self.apply_all_suggestions_button.setEnabled(False)
        self.assistant_status.setText(
            self.tr("Select a DEM layer — suggestions appear automatically.")
        )
        self.dem_inspector.set_inputs(layer, self.band_spin.value())
        if layer is not None and layer.isValid():
            self.prefix_edit.setText(sanitize_prefix(layer.name()))
            if hasattr(self, "layout_name_edit"):
                self.layout_name_edit.setText(f"Terrain Map · {layer.name()}")
                self.map_title_edit.setText(layer.name().upper())
                source_name = os.path.basename(layer.source().split("|")[0])
                self.map_source_edit.setText(source_name or "Digital Elevation Model")

    def _update_hydrology_controls(self):
        enabled = self.hydrology_check.isChecked()
        for widget in (
            self.stream_threshold,
            self.river_width_factor_spin,
            self.river_depth_factor_spin,
            self.basins_check,
        ):
            widget.setEnabled(enabled)

    def _update_layout_controls(self):
        enabled = self.create_layout_check.isChecked()
        for widget in (
            self.grid_check,
            self.open_layout_check,
            self.export_pdf_check,
            self.export_png_check,
            self.layout_dpi,
            self.layout_name_edit,
            self.layout_extent_combo,
            self.map_title_edit,
            self.map_subtitle_edit,
            self.map_author_edit,
            self.map_source_edit,
            self.font_combo,
            self.style_pack_font_check,
            self.legend_check,
            self.layout_queue,
            self.add_layout_button,
            self.duplicate_layout_button,
            self.remove_layout_button,
            self.move_layout_up_button,
            self.move_layout_down_button,
            self.create_all_layouts_button,
            self.qa_layout_button,
            self.layout_template_combo,
        ):
            widget.setEnabled(enabled)
        self.font_combo.setEnabled(
            enabled and not self.style_pack_font_check.isChecked()
        )
        self.create_all_layouts_button.setEnabled(
            enabled and bool(self._last_layout_layers)
        )

    def _on_cartography_preset_changed(self):
        preset_key = self.cartography_combo.currentData() or DEFAULT_CARTOGRAPHY
        preset = CARTOGRAPHY_PRESETS[preset_key]
        self.cartography_description.setText(preset["description"])
        self.theme_preview.setPixmap(self._theme_preview_pixmap(preset))
        self._update_recipe_inspector()

    def _apply_design_preset(self, *_args):
        key = self.design_preset_combo.currentData()
        if not key:
            self.design_description.setText(
                self.tr("Custom combination of layout, map style, palette and grid.")
            )
            self.design_preview.setPixmap(QPixmap())
            self.design_preview.setText(
                self.tr("Custom design · generate a layout to preview")
            )
            return
        design = design_preset(key)
        self._design_sync_guard = True
        try:
            for combo, value in (
                (self.cartography_combo, design.map_style),
                (self.layout_template_combo, design.layout_template),
                (self.palette_combo, design.palette),
                (self.grid_mode_combo, design.grid_mode),
            ):
                index = combo.findData(value)
                if index >= 0:
                    combo.setCurrentIndex(index)
        finally:
            self._design_sync_guard = False
        self.design_description.setText(design.description)
        self._on_cartography_preset_changed()
        self._on_layout_template_changed()
        self._on_grid_mode_changed()
        self._update_design_preview(design)

    def _update_design_preview(self, design):
        path = os.path.join(
            os.path.dirname(__file__), "assets", "preset_previews", design.preview
        )
        pixmap = QPixmap(path)
        if pixmap.isNull():
            self.design_preview.setPixmap(QPixmap())
            self.design_preview.setText(self.tr("Preview will be generated from the sample DEM"))
            return
        try:
            aspect = Qt.AspectRatioMode.KeepAspectRatio
            transform = Qt.TransformationMode.SmoothTransformation
        except AttributeError:
            aspect = getattr(Qt, "KeepAspectRatio")
            transform = getattr(Qt, "SmoothTransformation")
        self.design_preview.setText("")
        self.design_preview.setPixmap(
            pixmap.scaled(self.design_preview.size(), aspect, transform)
        )

    def _mark_design_custom(self, *_args):
        if getattr(self, "_design_sync_guard", False):
            return
        custom_index = self.design_preset_combo.findData("")
        if custom_index >= 0 and self.design_preset_combo.currentIndex() != custom_index:
            self.design_preset_combo.setCurrentIndex(custom_index)

    def _on_grid_mode_changed(self, *_args):
        self.grid_custom_edit.setEnabled(
            self.grid_mode_combo.currentData() == "custom"
        )

    def _on_layout_template_changed(self, *_args):
        template_key = self.layout_template_combo.currentData() or "classic_topo"
        template = LAYOUT_TEMPLATES[template_key]
        self.style_pack_summary.setText(
            f"{template.label} · {template.description}"
        )
        self.grid_check.setChecked(template.show_grid)
        self.legend_check.setChecked(template.show_legend)
        if self.style_pack_font_check.isChecked() and self.font_combo.count():
            self._select_resolved_font(template.preferred_font)

    def _on_style_pack_font_toggled(self, checked):
        self.font_combo.setEnabled(not checked and self.create_layout_check.isChecked())
        if checked and self.font_combo.count():
            template_key = self.layout_template_combo.currentData() or "classic_topo"
            self._select_resolved_font(
                LAYOUT_TEMPLATES[template_key].preferred_font
            )
        else:
            self._refresh_font_resolution()

    def _select_resolved_font(self, requested):
        resolved = resolve_font_family(requested, font_families())
        self._font_sync_guard = True
        try:
            index = self.font_combo.findText(resolved.family)
            if index >= 0:
                self.font_combo.setCurrentIndex(index)
            else:
                self.font_combo.setCurrentText(resolved.family)
        finally:
            self._font_sync_guard = False
        self.font_resolution_label.setText(
            self.tr("Font fallback") + f": {requested} → {resolved.family}"
            if resolved.substituted
            else self.tr("Resolved font") + f": {resolved.family}"
        )

    def _refresh_font_resolution(self, *_args):
        if self._font_sync_guard or not self.font_combo.count():
            return
        requested = (
            LAYOUT_TEMPLATES[
                self.layout_template_combo.currentData() or "classic_topo"
            ].preferred_font
            if self.style_pack_font_check.isChecked()
            else self.font_combo.currentText()
        )
        resolved = resolve_font_family(requested, font_families())
        self.font_resolution_label.setText(
            self.tr("Font fallback") + f": {requested} → {resolved.family}"
            if resolved.substituted
            else self.tr("Resolved font") + f": {resolved.family}"
        )

    @staticmethod
    def _preset_color(value):
        """Parse a preset color like '166,116,66,170' or '#833e25' into QColor."""
        text = str(value).strip()
        if text.startswith("#"):
            return QColor(text)
        parts = [int(part) for part in text.split(",")]
        return QColor(*parts)

    def _palette_algorithm_index(self):
        """Combo index → PALETTE enum index, skipping separator items."""
        selected = self.palette_combo.itemData(self.palette_combo.currentIndex())
        try:
            return PALETTE_ORDER.index(selected)
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _palette_preview(stops, width=96, height=20):
        """Render a TERRAIN_PALETTES stop list as a gradient thumbnail icon.

        Elevation-anchored dark palettes are normalized to 0..1 (Qt gradients
        reject positions outside that range).
        """
        pixmap = QPixmap(width, height)
        pixmap.fill(QColor(255, 255, 255, 0))
        painter = QPainter(pixmap)
        gradient = QLinearGradient(0, 0, width, 0)
        if any(float(position) > 1.0 for position, *_ in stops):
            low = min(float(position) for position, *_ in stops)
            high = max(float(position) for position, *_ in stops)
            span = max(high - low, 1e-9)
            stops = tuple(
                ((float(position) - low) / span, red, green, blue)
                for position, red, green, blue in stops
            )
        for position, red, green, blue in stops:
            gradient.setColorAt(float(position), QColor(red, green, blue))
        painter.fillRect(0, 0, width, height, QBrush(gradient))
        painter.setPen(QPen(QColor(110, 110, 110), 1))
        painter.drawRect(0, 0, width - 1, height - 1)
        painter.end()
        return QIcon(pixmap)

    @classmethod
    def _theme_preview_pixmap(cls, preset, width=164, height=84):
        """Miniature map swatch: paper colour, contour lines, water and type."""
        pixmap = QPixmap(width, height)
        pixmap.fill(QColor(preset["paper"]))
        painter = QPainter(pixmap)
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        except AttributeError:
            painter.setRenderHint(getattr(QPainter, "Antialiasing"))
        contour_colors = (
            cls._preset_color(preset["contour_minor"]),
            cls._preset_color(preset["contour_index"]),
            cls._preset_color(preset["contour_master"]),
        )
        for line, color in enumerate(contour_colors):
            pen = QPen(color)
            pen.setWidth(line + 1)
            painter.setPen(pen)
            base_y = 22 + line * 17
            points = [
                (x, base_y + int(3.0 * math.sin(x / 12.0 + line)))
                for x in range(4, width - 4, 4)
            ]
            for index in range(len(points) - 1):
                painter.drawLine(points[index][0], points[index][1], points[index + 1][0], points[index + 1][1])
        painter.setPen(QPen(cls._preset_color(preset["water"]), 2))
        painter.drawLine(10, height - 14, width - 10, height - 14)
        painter.setPen(QColor(preset["ink"]))
        try:
            painter.setFont(QFont(preset.get("font", "Sans Serif"), 8, QFont.Weight.Bold))
        except AttributeError:
            painter.setFont(QFont(preset.get("font", "Sans Serif"), 8, getattr(QFont, "Bold")))
        painter.drawText(8, 14, preset["label"])
        painter.end()
        return pixmap

    def _apply_contour_suggestion(self):
        suggestion = getattr(self, "_contour_suggestion", None)
        if suggestion:
            self.contour_interval.setValue(float(suggestion))

    # --- Assistant (smart defaults) -------------------------------------------------

    @staticmethod
    def _format_suggestion_value(suggestion):
        if isinstance(suggestion.value, float):
            return f"{suggestion.value:g} {suggestion.unit}".strip()
        return f"{suggestion.value} {suggestion.unit}".strip()

    def _on_dem_input_changed(self, *_args):
        """Band changed — restart the debounced inspection."""
        layer = self.dem_combo.currentLayer()
        if layer is not None and layer.isValid() and not self.task_controller.active:
            self.dem_inspector.set_inputs(layer, self.band_spin.value())

    def _mark_stream_threshold_touched(self, *_args):
        self._stream_threshold_touched = True

    def _effective_stream_threshold(self):
        """Auto-send the suggested threshold until the user edits it."""
        if self._stream_threshold_touched or self._suggested_stream_threshold is None:
            return self.stream_threshold.value()
        return self._suggested_stream_threshold

    def _on_dem_inspected(self, info, generation):
        if generation != self.dem_inspector.generation:
            return  # stale async result — a newer inspection superseded it
        self._dem_info = info
        suggested = float(
            info.get("suggested_contour_interval")
            or info.get("recommended_contour_interval")
            or 10.0
        )
        self._contour_suggestion = suggested
        self._suggestions = compute_smart_defaults(info)
        self._suggested_stream_threshold = None
        for suggestion in self._suggestions:
            if suggestion.key == "stream_threshold":
                self._suggested_stream_threshold = float(suggestion.value)
        z_unit = self.z_unit_combo.currentIndex()
        unit = "m" if z_unit == 0 else "ft"
        estimated_scale = int(info.get("estimated_map_scale") or 0)
        if estimated_scale > 0:
            suggestion_text = (
                f"{self.tr('Suggested interval')} (≈1:{estimated_scale:,} "
                f"{self.tr('map scale')}): {suggested:g} {unit}"
            )
        else:
            suggestion_text = f"{self.tr('Suggested interval')}: {suggested:g} {unit}"
        self.contour_suggestion_label.setText(suggestion_text)
        self.apply_suggestion_button.setEnabled(True)
        self._rebuild_assistant_rows()
        self.apply_all_suggestions_button.setEnabled(bool(self._suggestions))
        self.assistant_status.setText(
            self.tr(
                f"{len(self._suggestions)} suggestion(s) for "
                f"{info.get('name', '')}."
            )
        )

    def _on_dem_inspect_failed(self, message, generation):
        if generation != self.dem_inspector.generation:
            return
        self.assistant_status.setText(
            self.tr(f"DEM inspection failed: {message}")
        )

    def _rebuild_assistant_rows(self):
        while self.assistant_rows_layout.count():
            item = self.assistant_rows_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._suggestion_buttons = {}
        for suggestion in self._suggestions:
            box = QGroupBox(
                f"{suggestion.label}: {self._format_suggestion_value(suggestion)}"
            )
            box_layout = QVBoxLayout(box)
            rationale = QLabel(suggestion.rationale)
            rationale.setWordWrap(True)
            box_layout.addWidget(rationale)
            apply_button = QPushButton(self.tr("Apply"))
            box_layout.addWidget(apply_button)
            self._suggestion_buttons[suggestion.key] = apply_button
            apply_button.clicked.connect(
                lambda _checked=False, key=suggestion.key: self._apply_suggestion(key)
            )
            self.assistant_rows_layout.addWidget(box)

    def _apply_suggestion(self, key):
        suggestion = next(
            (item for item in self._suggestions if item.key == key), None
        )
        if suggestion is None:
            return
        if key == "contour_interval":
            self.contour_interval.setValue(float(suggestion.value))
        elif key == "stream_threshold":
            self.stream_threshold.setValue(float(suggestion.value))
            self._stream_threshold_touched = True
        elif key == "river_dimensions":
            self.river_width_factor_spin.setValue(1.0)
            self.river_depth_factor_spin.setValue(1.0)
        elif key == "working_crs":
            self.auto_reproject_check.setChecked(True)
        self.report_edit.appendPlainText(
            f"{self.tr('Assistant')}: {suggestion.label} → "
            f"{self._format_suggestion_value(suggestion)}"
        )

    def _apply_all_suggestions(self):
        for suggestion in self._suggestions:
            self._apply_suggestion(suggestion.key)
        self.iface.messageBar().pushSuccess(
            "Terrain Product Studio",
            self.tr(f"Applied {len(self._suggestions)} smart default(s)."),
        )

    def _create_layout_now(self):
        if not self._last_layout_layers:
            QMessageBox.information(
                self,
                self.tr("No generated layers"),
                self.tr("Run the terrain package first, then create the layout."),
            )
            return
        config = self._cartography_config()
        config["create_layout"] = True
        config["open_layout"] = True
        north_arrow = os.path.join(
            os.path.dirname(__file__), "icons", "north_arrow_classic.svg"
        )
        try:
            layout, exported = create_terrain_layout(
                QgsProject.instance(),
                self._last_layout_layers,
                self.output_edit.text().strip(),
                config,
                north_arrow,
            )
            self.iface.openLayoutDesigner(layout)
            self.report_edit.appendPlainText(f"Layout: {layout.name()}")
            if exported:
                self.report_edit.appendPlainText(
                    f"{self.tr('Exported')}:\n" + "\n".join(exported)
                )
        except Exception as error:
            QMessageBox.warning(
                self, self.tr("Layout"), f"Could not create layout: {error}"
            )

    @staticmethod
    def _user_role():
        try:
            return Qt.ItemDataRole.UserRole
        except AttributeError:
            return getattr(Qt, "UserRole")

    def _queue_label(self, config):
        preset = CARTOGRAPHY_PRESETS.get(
            config.get("preset"), CARTOGRAPHY_PRESETS[DEFAULT_CARTOGRAPHY]
        )
        template = LAYOUT_TEMPLATES.get(
            config.get("layout_template"), LAYOUT_TEMPLATES["classic_topo"]
        )
        paper = str(config.get("paper_size", "auto")).upper()
        orientation = str(config.get("orientation", "auto")).title()
        return (
            f"{config.get('layout_name') or 'Terrain Map'} · {template.label} · "
            f"{preset['label']} · {paper}/{orientation}"
        )

    def _add_current_layout_to_queue(self):
        config = self._cartography_config()
        config["create_layout"] = True
        item = QListWidgetItem(self._queue_label(config))
        item.setData(self._user_role(), dict(config))
        self.layout_queue.addItem(item)
        self.layout_queue.setCurrentItem(item)

    def _duplicate_queued_layout(self):
        item = self.layout_queue.currentItem()
        if item is None:
            self._add_current_layout_to_queue()
            return
        config = dict(item.data(self._user_role()) or {})
        base = config.get("layout_name") or "Terrain Map"
        config["layout_name"] = f"{base} copy"
        config["title"] = config.get("title") or base
        copy_item = QListWidgetItem(self._queue_label(config))
        copy_item.setData(self._user_role(), dict(config))
        self.layout_queue.addItem(copy_item)
        self.layout_queue.setCurrentItem(copy_item)

    def _remove_queued_layout(self):
        row = self.layout_queue.currentRow()
        if row < 0:
            return
        self.layout_queue.takeItem(row)

    def _move_queued_layout(self, offset):
        row = self.layout_queue.currentRow()
        target = row + int(offset)
        if row < 0 or target < 0 or target >= self.layout_queue.count():
            return
        item = self.layout_queue.takeItem(row)
        self.layout_queue.insertItem(target, item)
        self.layout_queue.setCurrentItem(item)

    def _queued_or_current_layout_configs(self):
        configs = []
        for row in range(self.layout_queue.count()):
            item = self.layout_queue.item(row)
            value = item.data(self._user_role())
            if isinstance(value, dict):
                configs.append(dict(value))
        return configs or [self._cartography_config()]

    def _create_all_layouts_now(self):
        if not self._last_layout_layers:
            QMessageBox.information(
                self,
                self.tr("No generated layers"),
                self.tr("Run the terrain package first, then generate the map book."),
            )
            return
        configs = self._queued_or_current_layout_configs()
        north_arrow = os.path.join(
            os.path.dirname(__file__), "icons", "north_arrow_classic.svg"
        )
        try:
            layouts, exported = create_terrain_layouts(
                QgsProject.instance(),
                self._last_layout_layers,
                self.output_edit.text().strip(),
                configs,
                north_arrow,
            )
            self.report_edit.appendPlainText(
                self.tr("Map book layouts") + ": " + ", ".join(layout.name() for layout in layouts)
            )
            if exported:
                self.report_edit.appendPlainText(
                    f"{self.tr('Exported')}:\n" + "\n".join(exported)
                )
            if configs and configs[-1].get("open_layout"):
                self.iface.openLayoutDesigner(layouts[-1])
        except Exception as error:
            QMessageBox.warning(
                self, self.tr("Map book"), f"Could not generate layouts: {error}"
            )

    def _update_recipe_inspector(self):
        available = self._last_layout_layers.keys() if self._last_layout_layers else ()
        preset = self.cartography_combo.currentData() or DEFAULT_CARTOGRAPHY
        selected, notes = inspect_layer_recipe(available, preset)
        if not available:
            text = self.tr("Layer plan will appear after the terrain run.")
        else:
            text = self.tr("Layout layers") + ": " + ", ".join(selected)
            if notes:
                text += "\n" + "\n".join(f"• {note}" for note in notes)
        self.recipe_inspector_label.setText(text)

    def _show_layout_qa(self):
        config = self._cartography_config()
        available = self._last_layout_layers.keys() if self._last_layout_layers else ()
        findings = validate_layout_config(
            config,
            available,
            font_substituted=bool(config.get("font_substituted")),
        )
        QMessageBox.information(
            self,
            self.tr("Map readiness"),
            "\n\n".join(
                f"[{finding.level.upper()}] {finding.message}"
                + (f"\n{finding.fix}" if finding.fix else "")
                for finding in findings
            ),
        )

    def _on_tab_changed(self, index):
        if index == self.cartography_tab_index and not self._fonts_populated:
            self._populate_fonts()
        if index == self.report_tab_index:
            self._reload_history()

    def _apply_style_to_outputs(self):
        """Restyle canvas, QML style packs and layouts from the last run."""
        manifest_path = self._last_run_manifest
        if not manifest_path or not os.path.isfile(manifest_path):
            QMessageBox.information(
                self,
                self.tr("No recent run"),
                self.tr(
                    "Run the package build first — restyling needs the last "
                    "run's report.json."
                ),
            )
            return
        plan = parse_run_manifest(manifest_path)
        if plan is None:
            QMessageBox.warning(
                self,
                self.tr("Cannot read report"),
                self.tr(
                    "The report.json could not be read — it may be incomplete "
                    "or hand-edited."
                ),
            )
            return
        config = self._cartography_config()
        try:
            try:
                self.setCursor(Qt.CursorShape.WaitCursor)
            except AttributeError:
                self.setCursor(getattr(Qt, "WaitCursor"))
            count, notes = restyle_outputs(
                plan,
                project=QgsProject.instance(),
                config=config,
                layout_names=self._last_layout_names,
                restyle_canvas=True,
                restyle_qml=True,
                restyle_layouts=True,
            )
            if self.iface and self.iface.mapCanvas():
                self.iface.mapCanvas().refresh()
        except Exception as error:
            QMessageBox.warning(self, self.tr("Restyle failed"), str(error))
            return
        finally:
            self.unsetCursor()
        summary = f"{self.tr('Restyled')} {count} {self.tr('canvas layer(s)')}."
        self.report_edit.appendPlainText(f"\n{summary}")
        for note in notes:
            self.report_edit.appendPlainText(f" · {note}")
        self.iface.messageBar().pushSuccess("Terrain Product Studio", summary)

    def _schedule_live_restyle(self, *_args):
        """Debounce a canvas (600 ms) restyle on combo change."""
        if self.task_controller.active:
            return
        if self._restyle_canvas_timer is None:
            self._restyle_canvas_timer = QTimer(self)
            self._restyle_canvas_timer.setSingleShot(True)
            self._restyle_canvas_timer.setInterval(600)
            self._restyle_canvas_timer.timeout.connect(self._live_restyle_canvas)
        if self._last_run_manifest and self._last_result_layers:
            self._restyle_canvas_timer.start()

    def _live_restyle_canvas(self):
        """Best-effort canvas restyle — errors surface on the explicit button."""
        if self.task_controller.active or not self._last_result_layers:
            return
        config = self._cartography_config()
        unit = "m" if self.z_unit_combo.currentIndex() == 0 else "ft"
        try:
            apply_result_styles(
                self._last_result_layers,
                self.contour_interval.value(),
                self.index_multiplier.value(),
                unit,
                config["preset"],
                config["font_family"],
                config.get("palette_key"),
            )
            if self.iface and self.iface.mapCanvas():
                self.iface.mapCanvas().refresh()
        except Exception:  # nosec B110 — best-effort restyle; keep the dock usable
            pass

    def _apply_industry_preset(self, index):
        """Uncheck everything, then tick the selected industry's products."""
        key = self.industry_combo.currentData()
        if not key:
            return
        for checkbox in self.products.values():
            checkbox.setChecked(False)
        for product_key in INDUSTRY_PRESETS[key][1]:
            if product_key == "CREATE_HYDROLOGY":
                self.hydrology_check.setChecked(True)
                continue
            checkbox = self.products.get(product_key)
            if checkbox is not None:
                checkbox.setChecked(True)

    def _export_3d_mesh(self, fmt):
        """Export the current DEM as a binary STL or OBJ mesh."""
        layer = self.dem_combo.currentLayer()
        if layer is None or not layer.isValid():
            QMessageBox.warning(
                self, self.tr("3D Export"),
                self.tr("Select a valid DEM layer first."),
            )
            return
        dem_path = layer.source().split("|")[0]
        folder = self.output_edit.text().strip() or QDir.homePath()
        default_name = f"{sanitize_prefix(self.prefix_edit.text())}_3d_print.{fmt}"
        path, _ = QFileDialog.getSaveFileName(
            self, self.tr("Export 3D print model"), os.path.join(folder, default_name),
            self.tr(f"{fmt.upper()} model (*.{fmt})"),
        )
        if not path:
            return
        try:
            if fmt == "stl":
                triangles = export_stl(
                    dem_path, path,
                    z_scale=self.z_scale_spin.value(),
                    base_thickness_m=self.base_thickness_spin.value(),
                )
            else:
                triangles = export_obj(
                    dem_path, path,
                    z_scale=self.z_scale_spin.value(),
                    base_thickness_m=self.base_thickness_spin.value(),
                )
        except Exception as err:
            QMessageBox.warning(self, self.tr("3D Export"), f"{self.tr('Could not export 3D model')}: {err}")
            return
        self.iface.messageBar().pushSuccess(
            "Terrain Product Studio", f"{self.tr('Exported')} {triangles} {self.tr('triangles to')} {path}"
        )

    def _reload_history(self):
        try:
            user_role = Qt.ItemDataRole.UserRole
        except AttributeError:
            user_role = getattr(Qt, "UserRole")
        self.history_list.clear()
        for entry in load_history():
            when = str(entry.get("timestamp", ""))[:19].replace("T", " ")
            folder = entry.get("folder", "")
            prefix = entry.get("prefix", "")
            products = ", ".join(entry.get("products", []))
            item = QListWidgetItem(f"{when}  ·  {prefix or '—'}\n{folder}\n{products}")
            item.setData(user_role, entry)
            self.history_list.addItem(item)

    def _open_history_entry(self, item):
        """Open the run's output folder and its intelligence report."""
        try:
            user_role = Qt.ItemDataRole.UserRole
        except AttributeError:
            user_role = getattr(Qt, "UserRole")
        entry = item.data(user_role)
        if not isinstance(entry, dict):
            return
        folder = entry.get("folder", "")
        if os.path.isdir(folder):
            QDesktopServices.openUrl(QUrl.fromLocalFile(folder))
        report = entry.get("report", "")
        if report and os.path.exists(str(report)):
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(report)))

    def _populate_fonts(self):
        """Scan system fonts once, only when the Layout tab is first opened."""
        self._fonts_populated = True
        selected = self.font_combo.currentText()
        self.font_combo.clear()
        self.font_combo.addItems(font_families())
        if self.style_pack_font_check.isChecked():
            template_key = self.layout_template_combo.currentData() or "classic_topo"
            self._select_resolved_font(
                LAYOUT_TEMPLATES[template_key].preferred_font
            )
        elif selected:
            self._select_resolved_font(selected)
        self._on_style_pack_font_toggled(self.style_pack_font_check.isChecked())

    def _browse_dem(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            self.tr("Select DEM"),
            QDir.homePath(),
            self.tr("Raster (*.tif *.tiff *.vrt *.img *.asc *.dem);;All Files (*)"),
        )
        if not path:
            return
        layer = QgsRasterLayer(path, os.path.splitext(os.path.basename(path))[0])
        if not layer.isValid():
            QMessageBox.warning(self, self.tr("Invalid DEM"), self.tr("QGIS could not open the selected raster."))
            return
        QgsProject.instance().addMapLayer(layer)
        self.dem_combo.setLayer(layer)

    def _browse_output(self):
        initial = self.output_edit.text().strip() or QDir.homePath()
        folder = QFileDialog.getExistingDirectory(self, self.tr("Select Output Folder"), initial)
        if folder:
            self.output_edit.setText(folder)
            QgsSettings().setValue(self.SETTINGS_OUTPUT, folder)

    def _selected_raster_count(self):
        count = sum(checkbox.isChecked() for checkbox in self.products.values())
        if self.hydrology_check.isChecked():
            count += 3 + self.basins_check.isChecked()
        return count

    def inspect_dem(self):
        layer = self.dem_combo.currentLayer()
        if layer is None or not layer.isValid():
            QMessageBox.information(self, self.tr("No DEM selected"), self.tr("Please select a DEM layer first."))
            return
        try:
            info = inspect_dem_layer(
                layer,
                self.band_spin.value(),
                self._selected_raster_count(),
            )
        except (ValueError, RuntimeError) as error:
            QMessageBox.critical(self, self.tr("Could not inspect DEM"), str(error))
            return
        self.report_edit.setPlainText(format_dem_report(info))
        # Same sink as the async inspector (mark_fresh bumps the generation,
        # so a pending async result cannot overwrite this manual one).
        self.dem_inspector.mark_fresh(info)
        self.tabs.setCurrentIndex(self.report_tab_index)

    def _update_index_preview(self):
        interval = self.contour_interval.value() * self.index_multiplier.value()
        z_unit_combo = getattr(self, "z_unit_combo", None)
        unit = "m" if z_unit_combo is None or z_unit_combo.currentIndex() == 0 else "ft"
        self.index_preview.setText(f"{interval:g} {unit}")

    def _select_quick(self):
        for key, checkbox in self.products.items():
            checkbox.setChecked(key in {"CREATE_MULTI_HILLSHADE", "CREATE_SPOT_ELEVATIONS"})
        self.contour_check.setChecked(True)
        self.smoothing_combo.setCurrentIndex(2)
        self.hydrology_check.setChecked(False)

    def _select_all(self):
        for checkbox in self.products.values():
            checkbox.setChecked(True)
        self.contour_check.setChecked(True)
        self.hydrology_check.setChecked(True)

    def _clear_selection(self):
        for checkbox in self.products.values():
            checkbox.setChecked(False)
        self.contour_check.setChecked(False)
        self.hydrology_check.setChecked(False)

    def _parameters(self):
        parameters = {
            "INPUT": self.dem_combo.currentLayer(),
            "BAND": self.band_spin.value(),
            "OUTPUT_FOLDER": self.output_edit.text().strip(),
            "PREFIX": sanitize_prefix(self.prefix_edit.text()),
            "Z_UNIT": self.z_unit_combo.currentIndex(),
            "AUTO_REPROJECT": self.auto_reproject_check.isChecked(),
            "PALETTE": self._palette_algorithm_index(),
            "COMPRESSION": self.compression_combo.currentIndex(),
            "WEB_3D_QUALITY": self.web_3d_quality_combo.currentIndex(),
            "PORTABLE_DEM_COPY": self.portable_dem_check.isChecked(),
            "VERTICAL_EXAGGERATION": self.vertical_exaggeration.value(),
            "AZIMUTH": self.azimuth.value(),
            "ALTITUDE": self.altitude.value(),
            "ZEVENBERGEN": self.zevenbergen_check.isChecked(),
            "CREATE_CONTOURS": self.contour_check.isChecked(),
            "CONTOUR_INTERVAL": self.contour_interval.value(),
            "INDEX_MULTIPLIER": self.index_multiplier.value(),
            "SPOT_PCT": self.spot_pct_spin.value(),
            "SMOOTHING": self.smoothing_combo.currentIndex(),
            "SIMPLIFY_TOLERANCE": self.simplify_tolerance.value(),
            "ACCUMULATION": None,
            "CREATE_HYDROLOGY": self.hydrology_check.isChecked(),
            "STREAM_THRESHOLD_HA": self._effective_stream_threshold(),
            "RIVER_WIDTH_FACTOR": self.river_width_factor_spin.value(),
            "RIVER_DEPTH_FACTOR": self.river_depth_factor_spin.value(),
            "CREATE_BASINS": self.basins_check.isChecked(),
            "CREATE_TWI": (
                self.hydrology_check.isChecked() and self.twi_check.isChecked()
            ),
            "STREAM_SMOOTHING": self.stream_smoothing_combo.currentIndex(),
            "STREAM_SIMPLIFY_TOLERANCE": self.simplify_tolerance.value(),
            "CREATE_BUNDLE": self.bundle_check.isChecked(),
            "MULTIHAZARD_WEIGHT_LANDSLIDE": self.multi_hazard_weight_landslide.value(),
            "MULTIHAZARD_WEIGHT_TWI": self.multi_hazard_weight_twi.value(),
            "MULTIHAZARD_WEIGHT_SLOPE": self.multi_hazard_weight_slope.value(),
        }
        mode = self.extent_combo.currentData()
        if mode == "canvas" and self.iface and self.iface.mapCanvas():
            canvas = self.iface.mapCanvas()
            ext = canvas.extent()
            canvas_crs = canvas.mapSettings().destinationCrs()
            parameters["EXTENT"] = QgsReferencedRectangle(ext, canvas_crs)
        elif mode == "layer":
            layer = self.extent_layer_combo.currentLayer()
            if layer and layer.isValid():
                parameters["EXTENT"] = QgsReferencedRectangle(layer.extent(), layer.crs())
        parameters.update({key: checkbox.isChecked() for key, checkbox in self.products.items()})
        return parameters

    def _cartography_config(self):
        preset_key = self.cartography_combo.currentData() or DEFAULT_CARTOGRAPHY
        requested_font = (
            LAYOUT_TEMPLATES[
                self.layout_template_combo.currentData() or "classic_topo"
            ].preferred_font
            if self.style_pack_font_check.isChecked()
            else (self.font_combo.currentText() or "Sans Serif")
        )
        resolved_font = resolve_font_family(requested_font, font_families())
        config = {
            "preset": preset_key,
            "design_preset": self.design_preset_combo.currentData() or "custom",
            "layout_template": self.layout_template_combo.currentData()
            or "classic_topo",
            "palette_key": self.palette_combo.currentData()
            or CARTOGRAPHY_PRESETS[preset_key]["palette"],
            "font_family": resolved_font.family,
            "requested_font": resolved_font.requested,
            "font_substituted": resolved_font.substituted,
            "create_layout": self.create_layout_check.isChecked(),
            "layout_name": self.layout_name_edit.text().strip(),
            "title": self.map_title_edit.text().strip(),
            "subtitle": self.map_subtitle_edit.text().strip(),
            "author": self.map_author_edit.text().strip(),
            "source": self.map_source_edit.text().strip(),
            "grid": self.grid_check.isChecked(),
            "grid_mode": self.grid_mode_combo.currentData() or "map_crs",
            "grid_custom_crs": self.grid_custom_edit.text().strip(),
            "show_legend": self.legend_check.isChecked(),
            "open_layout": self.open_layout_check.isChecked(),
            "export_pdf": self.export_pdf_check.isChecked(),
            "export_png": self.export_png_check.isChecked(),
            "dpi": self.layout_dpi.value(),
            "paper_size": self.paper_combo.currentData() or "auto",
            "orientation": self.orientation_combo.currentData() or "auto",
            "export_prefix": sanitize_prefix(self.prefix_edit.text()),
            "create_project": self.create_project_check.isChecked(),
            "create_share_manifest": self.share_manifest_check.isChecked(),
            "create_hydrology": self.hydrology_check.isChecked(),
            "stream_threshold_ha": self._effective_stream_threshold(),
            "create_basins": self.basins_check.isChecked(),
            "contour_interval": self.contour_interval.value(),
            "index_multiplier": self.index_multiplier.value(),
            "z_unit": "m" if self.z_unit_combo.currentIndex() == 0 else "ft",
        }
        if (
            self.layout_extent_combo.currentData() == "canvas"
            and self.iface
            and self.iface.mapCanvas()
        ):
            canvas = self.iface.mapCanvas()
            extent = canvas.extent()
            config["layout_extent"] = [
                extent.xMinimum(),
                extent.yMinimum(),
                extent.xMaximum(),
                extent.yMaximum(),
            ]
            config["layout_extent_crs"] = (
                canvas.mapSettings().destinationCrs().authid()
            )
        return config

    def run(self):
        if self.task_controller.active:
            return
        layer = self.dem_combo.currentLayer()
        if layer is None or not layer.isValid():
            QMessageBox.information(self, self.tr("No DEM selected"), self.tr("Please select a DEM layer first."))
            return
        output = self.output_edit.text().strip()
        if not output:
            QMessageBox.information(self, self.tr("No output folder"), self.tr("Please choose an output folder."))
            return
        if (
            not self.contour_check.isChecked()
            and not any(checkbox.isChecked() for checkbox in self.products.values())
            and not self.hydrology_check.isChecked()
        ):
            QMessageBox.information(
                self,
                self.tr("No terrain product selected"),
                self.tr("Check at least one basemap or contour product."),
            )
            return

        algorithm = QgsApplication.processingRegistry().algorithmById(
            "terrainstudio:buildterrainpackage"
        )
        if algorithm is None:
            QMessageBox.critical(
                self,
                self.tr("Missing Processing Provider"),
                self.tr("Terrain Product Studio processing algorithm was not found. Please reload the plugin."),
            )
            return

        os.makedirs(output, exist_ok=True)
        QgsSettings().setValue(self.SETTINGS_OUTPUT, output)
        run_parameters = self._parameters()
        self._run_config = self._cartography_config()
        self._run_parameters = run_parameters
        self.run_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.progress.setValue(0)
        self.report_edit.appendPlainText(f"\n{self.tr('Generating terrain package…')}")
        try:
            self.task_controller.start(
                algorithm,
                run_parameters,
                progress_callback=lambda value: self.progress.setValue(int(value)),
                finished_callback=self._task_finished,
            )
        except Exception as error:
            self.run_button.setEnabled(True)
            self.cancel_button.setEnabled(False)
            self.progress.setValue(0)
            self.report_edit.appendPlainText(
                f"\n{self.tr('Could not start Processing task')}: {error}"
            )
            QMessageBox.critical(
                self,
                self.tr("Could not start task"),
                str(error),
            )

    def cancel_task(self):
        self.task_controller.cancel()

    def _task_finished(self, successful, results):
        if not successful:
            self.run_button.setEnabled(True)
            self.cancel_button.setEnabled(False)
            self.progress.setValue(0)
            self.report_edit.appendPlainText(
                f"\n{self.tr('Task failed. Check View → Panels → Log Messages → Processing for details.')}"
            )
            self.iface.messageBar().pushWarning(
                "Terrain Product Studio", self.tr("Could not complete product package; check Processing log.")
            )
            return

        config = self._run_config or self._cartography_config()
        final_results = dict(results)
        prefix = sanitize_prefix(self.prefix_edit.text())

        self.run_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        self.progress.setValue(100)
        self._last_results = final_results

        unit = "m" if self.z_unit_combo.currentIndex() == 0 else "ft"
        loaded, failed, layers = add_terrain_results(
            final_results,
            self.contour_interval.value(),
            self.index_multiplier.value(),
            unit,
            config["preset"],
            config["font_family"],
            return_layers=True,
            palette_key=config.get("palette_key"),
        )
        self._last_layout_layers = layers
        self._last_result_layers = layers
        self.create_layout_button.setEnabled(bool(layers))
        self.create_all_layouts_button.setEnabled(
            bool(layers) and self.create_layout_check.isChecked()
        )
        self._update_recipe_inspector()
        report_path = str(final_results.get("REPORT", ""))
        if report_path and os.path.isfile(report_path):
            self._last_run_manifest = report_path
            self.restyle_button.setEnabled(True)
        self.report_edit.appendPlainText(
            f"\n{self.tr('Finished. Loaded')} {loaded} {self.tr('layers into project.')}\n{self.tr('Report')}: {report_path}"
        )
        if failed:
            self.report_edit.appendPlainText(f"{self.tr('Failed to load')}:\n" + "\n".join(failed))

        # Export one reusable QML set per selected Style Pack.  This preserves
        # the numeric DEM while still making its cartography portable outside
        # the generated QGZ project.
        style_configs = self._queued_or_current_layout_configs()
        if not self.layout_queue.count():
            style_configs = [dict(config)]
        exported_style_presets = set()
        for style_config in style_configs:
            preset_key = style_config.get("preset", DEFAULT_CARTOGRAPHY)
            if preset_key in exported_style_presets:
                continue
            exported_style_presets.add(preset_key)
            ordered_keys, _notes = inspect_layer_recipe(layers.keys(), preset_key)
            try:
                qml_paths, qml_warnings = export_style_pack_qml(
                    layers,
                    ordered_keys,
                    style_config,
                    self.output_edit.text().strip(),
                )
                for layer_key, qml_path in qml_paths.items():
                    final_results[f"STYLE_{preset_key}_{layer_key}"] = qml_path
                if qml_paths:
                    self.report_edit.appendPlainText(
                        f"Style Pack QML ({preset_key}): "
                        + ", ".join(qml_paths.values())
                    )
                if qml_warnings:
                    self.report_edit.appendPlainText(
                        "Style warnings: " + " | ".join(qml_warnings)
                    )
            except Exception as error:
                self.report_edit.appendPlainText(
                    f"Style Pack export error ({preset_key}): {error}"
                )

        layout_message = ""
        created_layout_names = []
        if config.get("create_layout"):
            north_arrow = os.path.join(
                os.path.dirname(__file__), "icons", "north_arrow_classic.svg"
            )
            try:
                layout_configs = self._queued_or_current_layout_configs()
                if not self.layout_queue.count():
                    layout_configs = [dict(config)]
                layouts, exported = create_terrain_layouts(
                    QgsProject.instance(),
                    layers,
                    self.output_edit.text().strip(),
                    layout_configs,
                    north_arrow,
                )
                layout_message = (
                    f" {self.tr('Created layout')} "
                    + ", ".join(f"'{layout.name()}'" for layout in layouts)
                    + "."
                )
                self.report_edit.appendPlainText(
                    "Layouts: " + ", ".join(layout.name() for layout in layouts)
                )
                created_layout_names = [layout.name() for layout in layouts]
                if exported:
                    self.report_edit.appendPlainText(f"{self.tr('Exported')}:\n" + "\n".join(exported))
                    for export_index, export_path in enumerate(exported, 1):
                        final_results[f"LAYOUT_EXPORT_{export_index}"] = export_path
                if config.get("open_layout") and layouts:
                    self.iface.openLayoutDesigner(layouts[-1])
            except Exception as error:  # keep generated terrain products available
                self.report_edit.appendPlainText(f"{self.tr('Layout error')}: {error}")
        self._last_layout_names = created_layout_names

        if config.get("create_project"):
            try:
                project_path = unique_path(
                    os.path.join(self.output_edit.text().strip(), f"{prefix}.qgz")
                )
                if QgsProject.instance().write(project_path):
                    final_results["QGIS_PROJECT"] = project_path
                    self.report_edit.appendPlainText(
                        f"{self.tr('QGIS project')}: {project_path}"
                    )
                else:
                    self.report_edit.appendPlainText(
                        f"{self.tr('QGIS project save failed')}: {project_path}"
                    )
            except Exception as error:
                self.report_edit.appendPlainText(
                    f"{self.tr('QGIS project save error')}: {error}"
                )

        if config.get("create_share_manifest", True):
            try:
                share_path = write_share_manifest(
                    self.output_edit.text().strip(),
                    prefix,
                    final_results,
                    config,
                    created_layout_names,
                )
                self.report_edit.appendPlainText(
                    f"{self.tr('Share manifest')}: {share_path}"
                )
            except Exception as error:
                self.report_edit.appendPlainText(
                    f"{self.tr('Share manifest error')}: {error}"
                )

        # Activate 3D Web Viewer & Intelligence Report buttons if generated
        v3d = final_results.get("VIEWER_3D")
        if v3d and os.path.exists(str(v3d)):
            self._last_3d_path = str(v3d)
            self.open_3d_button.setEnabled(True)
            self.tab_open_3d_button.setEnabled(True)
            self.report_edit.appendPlainText(f"\n🌐 3D Interactive Web Map: {v3d}")

        intel = final_results.get("INTELLIGENCE_REPORT")
        if intel and os.path.exists(str(intel)):
            self._last_report_html_path = str(intel)
            self.open_report_button.setEnabled(True)
            self.tab_open_report_button.setEnabled(True)
            self.report_edit.appendPlainText(f"📊 Topographic Intelligence Report: {intel}")

        bundle_path = str(final_results.get("BUNDLE", ""))
        append_history(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "folder": self.output_edit.text().strip(),
                "prefix": sanitize_prefix(self.prefix_edit.text()),
                "products": [
                    self._product_labels.get(key, key)
                    for key, checkbox in self.products.items()
                    if checkbox.isChecked()
                ],
                "report": str(intel) if intel and os.path.exists(str(intel)) else "",
                "bundle": bundle_path if bundle_path and os.path.exists(bundle_path) else "",
            }
        )

        self.iface.messageBar().pushSuccess(
            "Terrain Product Studio", f"{self.tr('Successfully built and loaded')} {loaded} {self.tr('terrain layers.')}{layout_message}"
        )
