"""Dockable user interface for Terrain Product Studio."""

from __future__ import annotations

import os

from qgis.PyQt.QtCore import QDir, QCoreApplication, QUrl
from qgis.PyQt.QtGui import QFont, QDesktopServices
from qgis.PyQt.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDockWidget,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFontComboBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)
from qgis.core import (
    QgsApplication,
    QgsMapLayerProxyModel,
    QgsProcessingAlgRunnerTask,
    QgsProcessingContext,
    QgsProcessingFeedback,
    QgsProject,
    QgsRasterLayer,
    QgsRectangle,
    QgsReferencedRectangle,
    QgsSettings,
)
from qgis.gui import QgsMapLayerComboBox

from .core.dem_info import format_dem_report, inspect_dem_layer
from .core.intelligence_report import generate_intelligence_report
from .core.layers import add_terrain_results
from .core.layouts import create_terrain_layout
from .core.math_utils import sanitize_prefix
from .core.presets import CARTOGRAPHY_PRESETS, TERRAIN_PALETTES
from .core.web_3d_viewer import generate_3d_web_viewer


class TerrainStudioDock(QDockWidget):
    SETTINGS_OUTPUT = "terrain_product_studio/output_folder"

    def __init__(self, iface, parent=None):
        super().__init__("Terrain Product Studio", parent)
        self.iface = iface
        self.task = None
        self.context = None
        self.feedback = None
        self._last_results = None
        self._run_config = None
        self._run_parameters = None
        self._terrain_results = None
        self._phase = None
        self._build_ui()
        self._connect_signals()
        self._on_layer_changed(self.dem_combo.currentLayer())

    @staticmethod
    def tr(message):
        return QCoreApplication.translate("TerrainStudioDock", message)

    def _build_ui(self):
        body = QWidget(self)
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
            self.dem_combo.setFilters(QgsMapLayerProxyModel.RasterLayer)
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
        outer.addWidget(output_group)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._create_products_tab(), self.tr("Products"))
        self.tabs.addTab(self._create_contour_tab(), self.tr("Contours"))
        self.tabs.addTab(self._create_hydrology_tab(), self.tr("Hydrology"))
        self.tabs.addTab(self._create_cartography_tab(), self.tr("Layout"))
        self.tabs.addTab(self._create_settings_tab(), self.tr("Settings"))
        self.report_tab_index = self.tabs.addTab(self._create_report_tab(), self.tr("Inspect"))
        self._update_index_preview()
        self._on_cartography_preset_changed()
        outer.addWidget(self.tabs, 1)

        presets = QHBoxLayout()
        self.quick_button = QPushButton(self.tr("Quick Basemap"))
        self.full_button = QPushButton(self.tr("Select All"))
        self.clear_button = QPushButton(self.tr("Clear All"))
        presets.addWidget(self.quick_button)
        presets.addWidget(self.full_button)
        presets.addWidget(self.clear_button)
        outer.addLayout(presets)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        outer.addWidget(self.progress)

        actions = QHBoxLayout()
        self.run_button = QPushButton(self.tr("Build Product Package"))
        self.run_button.setDefault(True)
        self.cancel_button = QPushButton(self.tr("Cancel"))
        self.cancel_button.setEnabled(False)
        actions.addWidget(self.run_button, 1)
        actions.addWidget(self.cancel_button)
        outer.addLayout(actions)

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
        results_bar.addWidget(self.open_3d_button)
        results_bar.addWidget(self.open_report_button)
        results_bar.addWidget(self.docs_button)
        outer.addLayout(results_bar)

        self.setWidget(body)
        self.resize(480, 810)

    def _create_products_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        self.products = {}
        definitions = (
            ("CREATE_COLOR_RELIEF", self.tr("Elevation color relief"), True),
            ("CREATE_HILLSHADE", self.tr("Standard single-light hillshade"), False),
            ("CREATE_MULTI_HILLSHADE", self.tr("Multidirectional hillshade"), True),
            ("CREATE_SLOPE", self.tr("Slope (degrees)"), True),
            ("CREATE_ASPECT", self.tr("Aspect (orientation)"), True),
            ("CREATE_TRI", self.tr("Terrain Ruggedness Index (TRI)"), True),
            ("CREATE_TPI", self.tr("Topographic Position Index (TPI)"), True),
            ("CREATE_ROUGHNESS", self.tr("Roughness"), True),
            ("CREATE_SPOT_ELEVATIONS", self.tr("Spot elevation peaks (markers)"), True),
            ("CREATE_SUITABILITY", self.tr("Slope construction suitability (TCVN)"), True),
            ("CREATE_LANDSLIDE", self.tr("Landslide hazard & RUSLE LS-factor"), True),
            ("CREATE_3D_VIEWER", self.tr("Interactive 3D Web Terrain Viewer (HTML)"), True),
            ("CREATE_INTELLIGENCE_REPORT", self.tr("Topographic Intelligence Report (HTML)"), True),
            ("CREATE_PROFILE_CURVATURE", self.tr("Profile curvature (flow acceleration)"), False),
            ("CREATE_PLANFORM_CURVATURE", self.tr("Planform curvature (flow convergence)"), False),
        )
        for key, label, checked in definitions:
            checkbox = QCheckBox(label)
            checkbox.setChecked(checked)
            self.products[key] = checkbox
            layout.addWidget(checkbox)
        layout.addStretch(1)
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
        layout.addRow(self.tr("Contour interval"), self.contour_interval)
        layout.addRow(self.tr("Index multiplier (every Nth line)"), self.index_multiplier)
        layout.addRow(self.tr("Index contour interval"), self.index_preview)
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
        self.hydrology_check.setChecked(True)
        self.stream_threshold = QDoubleSpinBox()
        self.stream_threshold.setDecimals(2)
        self.stream_threshold.setRange(0.01, 1000000000.0)
        self.stream_threshold.setValue(25.0)
        self.stream_threshold.setSuffix(" ha")
        self.twi_check = QCheckBox(self.tr("Topographic Wetness Index (TWI)"))
        self.twi_check.setChecked(True)
        self.basins_check = QCheckBox(self.tr("Save watershed basin raster"))
        self.basins_check.setChecked(True)
        layout.addRow(self.hydrology_check)
        layout.addRow(self.tr("Minimum contributing area"), self.stream_threshold)
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

    def _create_cartography_tab(self):
        tab = QWidget()
        layout = QFormLayout(tab)
        self.cartography_combo = QComboBox()
        for key, preset in CARTOGRAPHY_PRESETS.items():
            self.cartography_combo.addItem(preset["label"], key)
        self.cartography_description = QLabel()
        self.cartography_description.setWordWrap(True)
        self.font_combo = QFontComboBox()
        self.layout_name_edit = QLineEdit("Terrain Map")
        self.map_title_edit = QLineEdit("TOPOGRAPHIC TERRAIN MAP")
        self.map_subtitle_edit = QLineEdit("DEM-derived relief, contours and drainage")
        self.map_author_edit = QLineEdit("Nguyễn Văn Tín")
        self.map_source_edit = QLineEdit("Digital Elevation Model")
        self.create_layout_check = QCheckBox(self.tr("Create Print Layout after processing"))
        self.create_layout_check.setChecked(True)
        self.grid_check = QCheckBox(self.tr("Coordinate border and grid"))
        self.grid_check.setChecked(True)
        self.open_layout_check = QCheckBox(self.tr("Open Layout Designer when finished"))
        self.open_layout_check.setChecked(True)
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
        layout.addRow(self.tr("Map template"), self.cartography_combo)
        layout.addRow(self.cartography_description)
        layout.addRow(self.tr("Font family"), self.font_combo)
        layout.addRow(self.tr("Layout name"), self.layout_name_edit)
        layout.addRow(self.tr("Map title"), self.map_title_edit)
        layout.addRow(self.tr("Subtitle"), self.map_subtitle_edit)
        layout.addRow(self.tr("Author / Organization"), self.map_author_edit)
        layout.addRow(self.tr("Data source"), self.map_source_edit)
        layout.addRow(self.create_layout_check)
        layout.addRow(self.grid_check)
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
        for key, preset in TERRAIN_PALETTES.items():
            self.palette_combo.addItem(preset["label"], key)
        self.compression_combo = QComboBox()
        self.compression_combo.addItems(["DEFLATE", "ZSTD", "LZW", "NONE"])
        self.auto_reproject_check = QCheckBox(self.tr("Automatically reproject geographic DEM to UTM"))
        self.auto_reproject_check.setChecked(True)
        self.vertical_exaggeration = QDoubleSpinBox()
        self.vertical_exaggeration.setRange(0.01, 100.0)
        self.vertical_exaggeration.setDecimals(2)
        self.vertical_exaggeration.setValue(1.0)
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
        layout.addRow(self.tr("Elevation unit"), self.z_unit_combo)
        layout.addRow(self.tr("Color palette"), self.palette_combo)
        layout.addRow(self.tr("GeoTIFF compression"), self.compression_combo)
        layout.addRow(self.auto_reproject_check)
        layout.addRow(self.tr("Hillshade vertical exaggeration"), self.vertical_exaggeration)
        layout.addRow(self.tr("Light azimuth"), self.azimuth)
        layout.addRow(self.tr("Light altitude"), self.altitude)
        layout.addRow(self.zevenbergen_check)
        note = QLabel(self.tr("Default Horn method is ideal for rugged terrain; Zevenbergen–Thorne fits smooth surfaces."))
        note.setWordWrap(True)
        layout.addRow(note)
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
        self.cartography_combo.currentIndexChanged.connect(
            self._on_cartography_preset_changed
        )
        self.create_layout_check.toggled.connect(self._update_layout_controls)
        self.quick_button.clicked.connect(self._select_quick)
        self.full_button.clicked.connect(self._select_all)
        self.clear_button.clicked.connect(self._clear_selection)
        self.run_button.clicked.connect(self.run)
        self.cancel_button.clicked.connect(self.cancel_task)
        self.open_3d_button.clicked.connect(self._open_3d_map)
        self.open_report_button.clicked.connect(self._open_report)
        self.tab_open_3d_button.clicked.connect(self._open_3d_map)
        self.tab_open_report_button.clicked.connect(self._open_report)
        self.docs_button.clicked.connect(self._open_online_docs)
        self.extent_combo.currentIndexChanged.connect(self._on_extent_mode_changed)
        self.extent_layer_combo.layerChanged.connect(self._on_extent_mode_changed)
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
        if not path or not os.path.exists(path):
            folder = self.output_edit.text().strip()
            prefix = sanitize_prefix(self.prefix_edit.text())
            candidate = os.path.join(folder, f"{prefix}_interactive_3d_terrain.html")
            if os.path.exists(candidate):
                path = candidate
                self._last_3d_path = candidate
        if path and os.path.exists(path):
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))
        else:
            QMessageBox.information(
                self,
                self.tr("3D Interactive Map"),
                self.tr("No 3D Map HTML file has been generated yet. Please run the product package with 'Interactive 3D Web Terrain Viewer' checked."),
            )

    def _open_report(self):
        path = getattr(self, "_last_report_html_path", None)
        if not path or not os.path.exists(path):
            folder = self.output_edit.text().strip()
            prefix = sanitize_prefix(self.prefix_edit.text())
            candidate = os.path.join(folder, f"{prefix}_topographic_intelligence_report.html")
            if os.path.exists(candidate):
                path = candidate
                self._last_report_html_path = candidate
        if path and os.path.exists(path):
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))
        else:
            QMessageBox.information(
                self,
                self.tr("Intelligence Report"),
                self.tr("No Topographic Intelligence Report has been generated yet. Please run the product package with 'Topographic Intelligence Report' checked."),
            )

    def _on_layer_changed(self, layer):
        bands = layer.bandCount() if layer is not None and layer.isValid() else 1
        self.band_spin.setRange(1, max(1, bands))
        self.band_spin.setValue(1)
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
            self.map_title_edit,
            self.map_subtitle_edit,
            self.map_author_edit,
            self.map_source_edit,
            self.font_combo,
        ):
            widget.setEnabled(enabled)

    def _on_cartography_preset_changed(self):
        preset_key = self.cartography_combo.currentData() or "usgs_classic"
        preset = CARTOGRAPHY_PRESETS[preset_key]
        self.cartography_description.setText(preset["description"])
        self.font_combo.setCurrentFont(QFont(preset["font"]))
        palette_index = self.palette_combo.findData(preset["palette"])
        if palette_index >= 0:
            self.palette_combo.setCurrentIndex(palette_index)

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
        self.contour_interval.setValue(info["recommended_contour_interval"])
        self.tabs.setCurrentIndex(self.report_tab_index)

    def _update_index_preview(self):
        interval = self.contour_interval.value() * self.index_multiplier.value()
        z_unit_combo = getattr(self, "z_unit_combo", None)
        unit = "m" if z_unit_combo is None or z_unit_combo.currentIndex() == 0 else "ft"
        self.index_preview.setText(f"{interval:g} {unit}")

    def _select_quick(self):
        for key, checkbox in self.products.items():
            checkbox.setChecked(key in {"CREATE_COLOR_RELIEF", "CREATE_MULTI_HILLSHADE", "CREATE_3D_VIEWER", "CREATE_INTELLIGENCE_REPORT"})
        self.contour_check.setChecked(True)
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
            "PALETTE": self.palette_combo.currentIndex(),
            "COMPRESSION": self.compression_combo.currentIndex(),
            "VERTICAL_EXAGGERATION": self.vertical_exaggeration.value(),
            "AZIMUTH": self.azimuth.value(),
            "ALTITUDE": self.altitude.value(),
            "ZEVENBERGEN": self.zevenbergen_check.isChecked(),
            "CREATE_CONTOURS": self.contour_check.isChecked(),
            "CONTOUR_INTERVAL": self.contour_interval.value(),
            "INDEX_MULTIPLIER": self.index_multiplier.value(),
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
        return {
            "preset": self.cartography_combo.currentData() or "usgs_classic",
            "font_family": self.font_combo.currentFont().family(),
            "create_layout": self.create_layout_check.isChecked(),
            "layout_name": self.layout_name_edit.text().strip(),
            "title": self.map_title_edit.text().strip(),
            "subtitle": self.map_subtitle_edit.text().strip(),
            "author": self.map_author_edit.text().strip(),
            "source": self.map_source_edit.text().strip(),
            "grid": self.grid_check.isChecked(),
            "open_layout": self.open_layout_check.isChecked(),
            "export_pdf": self.export_pdf_check.isChecked(),
            "export_png": self.export_png_check.isChecked(),
            "dpi": self.layout_dpi.value(),
            "export_prefix": sanitize_prefix(self.prefix_edit.text()),
            "create_hydrology": self.hydrology_check.isChecked(),
            "stream_threshold_ha": self.stream_threshold.value(),
            "create_basins": self.basins_check.isChecked(),
        }

    def run(self):
        if self.task is not None:
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
        self.context = QgsProcessingContext()
        self.context.setProject(QgsProject.instance())
        self.feedback = QgsProcessingFeedback()
        self.feedback.progressChanged.connect(lambda value: self.progress.setValue(int(value)))
        run_parameters = self._parameters()
        self.task = QgsProcessingAlgRunnerTask(
            algorithm,
            run_parameters,
            self.context,
            self.feedback,
        )
        self._run_config = self._cartography_config()
        self._run_parameters = run_parameters
        self._terrain_results = None
        self._phase = "terrain"
        self.task.executed.connect(self._task_finished)
        self.run_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.progress.setValue(0)
        self.report_edit.appendPlainText(f"\n{self.tr('Generating terrain package…')}")
        QgsApplication.taskManager().addTask(self.task)

    def cancel_task(self):
        if self.task is not None:
            self.task.cancel()
        if self.feedback is not None:
            self.feedback.cancel()

    def _task_finished(self, successful, results):
        self.task = None

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

        # Phase 1 finished: if hydrology is requested, launch phase 2 algorithm
        if self._phase == "terrain" and config.get("create_hydrology"):
            self._terrain_results = dict(results)
            hydrology_alg = QgsApplication.processingRegistry().algorithmById("terrainstudio:buildhydrology")
            if hydrology_alg is not None:
                self._phase = "hydrology"
                working_input = results.get("WORKING_DEM") or self.dem_combo.currentLayer()
                hydro_params = {
                    "INPUT": working_input,
                    "BAND": self.band_spin.value(),
                    "OUTPUT_FOLDER": self.output_edit.text().strip(),
                    "PREFIX": sanitize_prefix(self.prefix_edit.text()),
                    "Z_UNIT": self.z_unit_combo.currentIndex(),
                    "STREAM_THRESHOLD_HA": self.stream_threshold.value(),
                    "CREATE_BASINS": self.basins_check.isChecked(),
                    "CREATE_TWI": self.twi_check.isChecked(),
                }
                self.feedback = QgsProcessingFeedback()
                self.feedback.progressChanged.connect(lambda val: self.progress.setValue(int(val)))
                self.task = QgsProcessingAlgRunnerTask(hydrology_alg, hydro_params, self.context, self.feedback)
                self.task.executed.connect(self._task_finished)
                self.run_button.setEnabled(False)
                self.cancel_button.setEnabled(True)
                self.report_edit.appendPlainText(f"\n{self.tr('Extracting hydrology & river network…')}")
                QgsApplication.taskManager().addTask(self.task)
                return

        # Merge results if hydrology ran after terrain
        final_results = dict(results)
        if self._terrain_results:
            final_results.update(self._terrain_results)
            self._terrain_results = None

        # Refresh 3D Web Viewer & Intelligence Report with newly generated Hydrology rivers & TWI
        working_dem_path = str(final_results.get("WORKING_DEM", ""))
        if not working_dem_path and self.dem_combo.currentLayer():
            working_dem_path = self.dem_combo.currentLayer().source().split("|")[0]
        prefix = sanitize_prefix(self.prefix_edit.text())

        if final_results.get("STREAMS") and os.path.exists(str(final_results.get("STREAMS"))):
            v3d_target = final_results.get("VIEWER_3D")
            if v3d_target and os.path.exists(str(v3d_target)):
                try:
                    generate_3d_web_viewer(
                        dem_path=working_dem_path,
                        output_html_path=str(v3d_target),
                        title=f"{prefix.title()} 3D Interactive WebGIS Studio",
                        stream_vector_path=str(final_results.get("STREAMS")),
                        contour_vector_path=final_results.get("CONTOURS"),
                        spot_peaks_path=final_results.get("SPOT_ELEVATIONS"),
                        slope_path=final_results.get("SLOPE"),
                        twi_path=final_results.get("TWI"),
                        suitability_path=final_results.get("SUITABILITY"),
                        hazard_path=final_results.get("LANDSLIDE_HAZARD"),
                    )
                except Exception:
                    pass

            intel_target = final_results.get("INTELLIGENCE_REPORT")
            if intel_target and os.path.exists(str(intel_target)):
                try:
                    generate_intelligence_report(
                        dem_path=working_dem_path,
                        output_html_path=str(intel_target),
                        title=f"{prefix.title()} Topographic Intelligence Report",
                        slope_path=final_results.get("SLOPE"),
                        aspect_path=final_results.get("ASPECT"),
                        stream_vector_path=str(final_results.get("STREAMS")),
                        suitability_path=final_results.get("SUITABILITY"),
                        hazard_path=final_results.get("LANDSLIDE_HAZARD"),
                        twi_path=final_results.get("TWI"),
                    )
                except Exception:
                    pass

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
        )
        report_path = str(final_results.get("REPORT", ""))
        self.report_edit.appendPlainText(
            f"\n{self.tr('Finished. Loaded')} {loaded} {self.tr('layers into project.')}\n{self.tr('Report')}: {report_path}"
        )
        if failed:
            self.report_edit.appendPlainText(f"{self.tr('Failed to load')}:\n" + "\n".join(failed))

        layout_message = ""
        if config.get("create_layout"):
            north_arrow = os.path.join(
                os.path.dirname(__file__), "icons", "north_arrow_classic.svg"
            )
            try:
                layout, exported = create_terrain_layout(
                    QgsProject.instance(),
                    layers,
                    self.output_edit.text().strip(),
                    config,
                    north_arrow,
                )
                layout_message = f" {self.tr('Created layout')} '{layout.name()}'."
                self.report_edit.appendPlainText(f"Layout: {layout.name()}")
                if exported:
                    self.report_edit.appendPlainText(f"{self.tr('Exported')}:\n" + "\n".join(exported))
                if config.get("open_layout"):
                    self.iface.openLayoutDesigner(layout)
            except Exception as error:  # keep generated terrain products available
                self.report_edit.appendPlainText(f"{self.tr('Layout error')}: {error}")
        
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

        self.iface.messageBar().pushSuccess(
            "Terrain Product Studio", f"{self.tr('Successfully built and loaded')} {loaded} {self.tr('terrain layers.')}{layout_message}"
        )
