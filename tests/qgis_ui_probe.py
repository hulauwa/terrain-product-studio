"""Manual qgis_process probe which constructs the dock without showing it."""

from __future__ import annotations

import os
import sys
import traceback

from qgis.core import QgsProcessingAlgorithm, QgsProcessingException


class TerrainStudioUiProbe(QgsProcessingAlgorithm):
    def name(self):
        return "terrainstudiouiprobe"

    def displayName(self):
        return "Terrain Studio UI probe"

    def group(self):
        return "Tests"

    def groupId(self):
        return "tests"

    def createInstance(self):
        return TerrainStudioUiProbe()

    def initAlgorithm(self, config=None):
        pass

    def processAlgorithm(self, parameters, context, feedback):
        workspace = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        sys.path.insert(0, workspace)
        try:
            from qgis.PyQt.QtWidgets import QGridLayout, QScrollArea

            from terrain_product_studio.core.qgis_compat import font_families
            from terrain_product_studio.dock import TerrainStudioDock

            dock = TerrainStudioDock(None)
            if len(dock.products) != 19:
                raise RuntimeError(f"Unexpected product checkbox count: {len(dock.products)}")
            scroll = dock.setup_scroll
            if not isinstance(scroll, QScrollArea):
                raise RuntimeError("Dock setup controls are not wrapped in a QScrollArea")
            if not scroll.widgetResizable():
                raise RuntimeError("Scroll area must be widget-resizable")
            if dock.run_button is None or not dock.run_button.isEnabled():
                raise RuntimeError("Run button missing or disabled")
            products_tab = dock.tabs.widget(0)
            if not isinstance(products_tab, QScrollArea):
                raise RuntimeError("Products options page should be scrollable")
            if not isinstance(products_tab.widget().layout(), QGridLayout):
                raise RuntimeError("Products tab should use the compact 2-column grid")
            if dock.smoothing_combo.currentIndex() != 2:
                raise RuntimeError("Contours should default to Medium smoothing")
            if not font_families():
                raise RuntimeError("QGIS returned no installed font families")
            dock._populate_fonts()
            dock._cartography_config()
            dock.close()
            dock.deleteLater()
            feedback.pushInfo("Dock constructed successfully")
            return {}
        except Exception as error:
            raise QgsProcessingException(traceback.format_exc()) from error
