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
            from terrain_product_studio.dock import TerrainStudioDock

            dock = TerrainStudioDock(None)
            if len(dock.products) != 8:
                raise RuntimeError("Unexpected product checkbox count")
            dock.close()
            dock.deleteLater()
            feedback.pushInfo("Dock constructed successfully")
            return {}
        except Exception as error:
            raise QgsProcessingException(traceback.format_exc()) from error
