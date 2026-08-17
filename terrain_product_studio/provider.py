"""Processing provider registration."""

from __future__ import annotations

import os

from qgis.PyQt.QtCore import QCoreApplication
from qgis.PyQt.QtGui import QIcon
from qgis.core import QgsProcessingProvider

from .algorithms.build_package import BuildTerrainPackageAlgorithm
from .algorithms.build_hydrology import BuildHydrologyAlgorithm
from .algorithms.inspect_dem import InspectDemAlgorithm


class TerrainStudioProvider(QgsProcessingProvider):
    @staticmethod
    def tr(message):
        return QCoreApplication.translate("TerrainProductStudio", message)

    def loadAlgorithms(self):
        self.addAlgorithm(InspectDemAlgorithm())
        self.addAlgorithm(BuildTerrainPackageAlgorithm())
        self.addAlgorithm(BuildHydrologyAlgorithm())

    def id(self):
        return "terrainstudio"

    def name(self):
        return self.tr("Terrain Product Studio")

    def longName(self):
        return self.name()

    def icon(self):
        return QIcon(os.path.join(os.path.dirname(__file__), "icons", "terrain_studio.png"))
