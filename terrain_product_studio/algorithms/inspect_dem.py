"""Processing algorithm which reports DEM metadata and safe defaults."""

from __future__ import annotations

import json

from qgis.PyQt.QtCore import QCoreApplication
from qgis.core import (
    QgsProcessingAlgorithm,
    QgsProcessingException,
    QgsProcessingOutputNumber,
    QgsProcessingOutputString,
    QgsProcessingParameterBand,
    QgsProcessingParameterRasterLayer,
)

from ..core.dem_info import format_dem_report, inspect_dem_layer


class InspectDemAlgorithm(QgsProcessingAlgorithm):
    INPUT = "INPUT"
    BAND = "BAND"
    REPORT = "REPORT"
    REPORT_JSON = "REPORT_JSON"
    CONTOUR_INTERVAL = "CONTOUR_INTERVAL"
    WORKING_CRS = "WORKING_CRS"

    @staticmethod
    def tr(message):
        return QCoreApplication.translate("TerrainProductStudio", message)

    def name(self):
        return "inspectdem"

    def displayName(self):
        return self.tr("Inspect DEM")

    def group(self):
        return self.tr("Terrain Product Studio")

    def groupId(self):
        return "terrainstudio"

    def shortHelpString(self):
        return self.tr(
            "Checks a DEM band, reports dimensions, CRS, elevation range and NoData, "
            "then recommends a projected working CRS and contour interval."
        )

    def createInstance(self):
        return InspectDemAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterRasterLayer(self.INPUT, self.tr("Input DEM")))
        self.addParameter(
            QgsProcessingParameterBand(
                self.BAND,
                self.tr("Elevation band"),
                defaultValue=1,
                parentLayerParameterName=self.INPUT,
            )
        )
        self.addOutput(QgsProcessingOutputString(self.REPORT, self.tr("Inspection report")))
        self.addOutput(QgsProcessingOutputString(self.REPORT_JSON, self.tr("Inspection JSON")))
        self.addOutput(
            QgsProcessingOutputNumber(self.CONTOUR_INTERVAL, self.tr("Recommended contour interval"))
        )
        self.addOutput(QgsProcessingOutputString(self.WORKING_CRS, self.tr("Suggested working CRS")))

    def processAlgorithm(self, parameters, context, feedback):
        layer = self.parameterAsRasterLayer(parameters, self.INPUT, context)
        band = self.parameterAsInt(parameters, self.BAND, context)
        try:
            info = inspect_dem_layer(layer, band)
        except (ValueError, RuntimeError) as error:
            raise QgsProcessingException(str(error)) from error
        report = format_dem_report(info)
        feedback.pushInfo(report)
        return {
            self.REPORT: report,
            self.REPORT_JSON: json.dumps(info, ensure_ascii=False, indent=2),
            self.CONTOUR_INTERVAL: info["recommended_contour_interval"],
            self.WORKING_CRS: info["suggested_working_crs"],
        }
