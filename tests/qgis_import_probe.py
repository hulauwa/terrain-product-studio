"""Standalone Processing script used to expose plugin import tracebacks in qgis_process."""

from __future__ import annotations

import os
import sys
import traceback

from qgis.core import QgsProcessingAlgorithm, QgsProcessingException


class TerrainStudioImportProbe(QgsProcessingAlgorithm):
    def name(self):
        return "terrainstudioimportprobe"

    def displayName(self):
        return "Terrain Studio import probe"

    def group(self):
        return "Tests"

    def groupId(self):
        return "tests"

    def createInstance(self):
        return TerrainStudioImportProbe()

    def initAlgorithm(self, config=None):
        pass

    def processAlgorithm(self, parameters, context, feedback):
        workspace = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        sys.path.insert(0, workspace)
        try:
            from terrain_product_studio.provider import TerrainStudioProvider

            provider = TerrainStudioProvider()
            provider.loadAlgorithms()
            algorithm_names = sorted(algorithm.name() for algorithm in provider.algorithms())
            feedback.pushInfo("Imported algorithms: " + ",".join(algorithm_names))
            return {}
        except Exception as error:
            raise QgsProcessingException(traceback.format_exc()) from error
