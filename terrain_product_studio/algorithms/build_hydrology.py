"""Standalone projected-DEM hydrology algorithm."""

from __future__ import annotations

import json
import math
import os
from datetime import datetime, timezone

from qgis.PyQt.QtCore import QCoreApplication
from qgis.core import (
    QgsProcessingAlgorithm,
    QgsProcessingException,
    QgsProcessingOutputFile,
    QgsProcessingOutputRasterLayer,
    QgsProcessingOutputVectorLayer,
    QgsProcessingParameterBand,
    QgsProcessingParameterBoolean,
    QgsProcessingParameterEnum,
    QgsProcessingParameterFolderDestination,
    QgsProcessingParameterNumber,
    QgsProcessingParameterRasterLayer,
    QgsProcessingParameterString,
    QgsUnitTypes,
)

from ..core import plugin_version
from ..core.math_utils import sanitize_prefix, unique_path
from ..core.native_hydrology import calculate_complete_hydrology
from ..core.smoothing import smooth_geometries


def _number_type_double():
    """Return QgsProcessingParameterNumber Double type enum (Qt5 & Qt6 safe)."""
    try:
        return QgsProcessingParameterNumber.Type.Double
    except AttributeError:
        return getattr(QgsProcessingParameterNumber, "Double")


class BuildHydrologyAlgorithm(QgsProcessingAlgorithm):
    INPUT = "INPUT"
    BAND = "BAND"
    OUTPUT_FOLDER = "OUTPUT_FOLDER"
    PREFIX = "PREFIX"
    Z_UNIT = "Z_UNIT"
    STREAM_THRESHOLD_HA = "STREAM_THRESHOLD_HA"
    RIVER_WIDTH_FACTOR = "RIVER_WIDTH_FACTOR"
    RIVER_DEPTH_FACTOR = "RIVER_DEPTH_FACTOR"
    CREATE_BASINS = "CREATE_BASINS"
    CREATE_TWI = "CREATE_TWI"
    SMOOTHING = "SMOOTHING"
    SIMPLIFY_TOLERANCE = "SIMPLIFY_TOLERANCE"

    FILLED_DEM = "FILLED_DEM"
    FLOW_DIRECTION = "FLOW_DIRECTION"
    FLOW_ACCUMULATION = "FLOW_ACCUMULATION"
    STREAM_RASTER = "STREAM_RASTER"
    STREAMS = "STREAMS"
    STREAMS_SMOOTH = "STREAMS_SMOOTH"
    BASINS = "BASINS"
    TWI = "TWI"
    HYDROLOGY_REPORT = "HYDROLOGY_REPORT"

    @staticmethod
    def tr(message):
        return QCoreApplication.translate("TerrainProductStudio", message)

    def name(self):
        return "buildhydrology"

    def displayName(self):
        return self.tr("Build DEM hydrology products")

    def group(self):
        return self.tr("Terrain Product Studio")

    def groupId(self):
        return "terrainstudio"

    def shortHelpString(self):
        return self.tr(
            "Conditions a projected DEM using priority-flood, calculates deterministic D8 flow, "
            "and creates filled DEM, direction, accumulation, basin, TWI, and continuous Strahler "
            "stream network polylines. It can run independently, while the master package invokes "
            "it after shared preprocessing and before flow-dependent products."
        )

    def createInstance(self):
        return BuildHydrologyAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterRasterLayer(self.INPUT, self.tr("Projected DEM")))
        self.addParameter(
            QgsProcessingParameterBand(
                self.BAND,
                self.tr("Elevation band"),
                defaultValue=1,
                parentLayerParameterName=self.INPUT,
            )
        )
        self.addParameter(
            QgsProcessingParameterFolderDestination(self.OUTPUT_FOLDER, self.tr("Output folder"))
        )
        self.addParameter(
            QgsProcessingParameterString(self.PREFIX, self.tr("Output filename prefix"), "terrain")
        )
        self.addParameter(
            QgsProcessingParameterEnum(
                self.Z_UNIT,
                self.tr("Elevation unit"),
                options=[self.tr("Meters"), self.tr("Feet")],
                defaultValue=0,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.STREAM_THRESHOLD_HA,
                self.tr("Minimum contributing area for streams (hectares)"),
                type=_number_type_double(),
                minValue=0.0001,
                maxValue=1000000000.0,
                defaultValue=25.0,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.RIVER_WIDTH_FACTOR,
                self.tr("River width factor (Horton W = 3·√A m)"),
                type=_number_type_double(),
                minValue=0.25,
                maxValue=10.0,
                defaultValue=1.0,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.RIVER_DEPTH_FACTOR,
                self.tr("River depth factor (power law D = 0.55·W^0.6 m)"),
                type=_number_type_double(),
                minValue=0.25,
                maxValue=5.0,
                defaultValue=1.0,
            )
        )
        self.addParameter(
            QgsProcessingParameterBoolean(
                self.CREATE_BASINS, self.tr("Create watershed basin raster"), defaultValue=True
            )
        )
        self.addParameter(
            QgsProcessingParameterBoolean(
                self.CREATE_TWI, self.tr("Create Topographic Wetness Index (TWI)"), defaultValue=True
            )
        )
        self.addParameter(
            QgsProcessingParameterEnum(
                self.SMOOTHING,
                self.tr("River smoothness (cartographic copy)"),
                options=[self.tr("Off"), self.tr("Light"), self.tr("Medium"), self.tr("Heavy")],
                defaultValue=0,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.SIMPLIFY_TOLERANCE,
                self.tr("Simplify rivers before smoothing (map units, 0 = off)"),
                type=_number_type_double(),
                minValue=0.0,
                defaultValue=0.0,
            )
        )

        self.addOutput(QgsProcessingOutputRasterLayer(self.FILLED_DEM, self.tr("Filled DEM")))
        self.addOutput(
            QgsProcessingOutputRasterLayer(self.FLOW_DIRECTION, self.tr("D8 flow direction"))
        )
        self.addOutput(
            QgsProcessingOutputRasterLayer(self.FLOW_ACCUMULATION, self.tr("Flow accumulation"))
        )
        self.addOutput(
            QgsProcessingOutputRasterLayer(self.STREAM_RASTER, self.tr("Potential stream raster"))
        )
        self.addOutput(
            QgsProcessingOutputVectorLayer(self.STREAMS, self.tr("Potential drainage network"))
        )
        self.addOutput(
            QgsProcessingOutputVectorLayer(
                self.STREAMS_SMOOTH, self.tr("Smoothed rivers (cartographic copy)")
            )
        )
        self.addOutput(QgsProcessingOutputRasterLayer(self.BASINS, self.tr("Watershed basins")))
        self.addOutput(
            QgsProcessingOutputRasterLayer(self.TWI, self.tr("Topographic Wetness Index (TWI)"))
        )
        self.addOutput(
            QgsProcessingOutputFile(self.HYDROLOGY_REPORT, self.tr("Hydrology report"))
        )

    @staticmethod
    def _horizontal_meters_per_unit(crs):
        try:
            # Qt6/QGIS4 scoped enum: QgsUnitTypes.DistanceUnit.DistanceMeters
            try:
                dist_meters = QgsUnitTypes.DistanceUnit.DistanceMeters
            except AttributeError:
                dist_meters = getattr(QgsUnitTypes, "DistanceMeters")
            factor = QgsUnitTypes.fromUnitToUnitFactor(crs.mapUnits(), dist_meters)
            if math.isfinite(factor) and factor > 0:
                return float(factor)
        except (AttributeError, TypeError, ValueError):
            pass
        return 1.0

    @staticmethod
    def _output_path(folder, prefix, suffix, extension):
        return unique_path(os.path.join(folder, f"{prefix}_{suffix}.{extension}"))

    def processAlgorithm(self, parameters, context, feedback):
        source = self.parameterAsRasterLayer(parameters, self.INPUT, context)
        band = self.parameterAsInt(parameters, self.BAND, context)
        folder = self.parameterAsString(parameters, self.OUTPUT_FOLDER, context)
        prefix = sanitize_prefix(self.parameterAsString(parameters, self.PREFIX, context))
        z_unit = self.parameterAsEnum(parameters, self.Z_UNIT, context)
        threshold_ha = self.parameterAsDouble(parameters, self.STREAM_THRESHOLD_HA, context)
        width_factor = self.parameterAsDouble(parameters, self.RIVER_WIDTH_FACTOR, context)
        depth_factor = self.parameterAsDouble(parameters, self.RIVER_DEPTH_FACTOR, context)
        create_basins = self.parameterAsBool(parameters, self.CREATE_BASINS, context)
        create_twi = self.parameterAsBool(parameters, self.CREATE_TWI, context)
        if source is None or not source.isValid():
            raise QgsProcessingException(self.tr("Input DEM is missing or invalid."))
        if not source.crs().isValid() or source.crs().isGeographic():
            raise QgsProcessingException(
                self.tr(
                    "Hydrology requires a projected DEM. Run Build terrain product package with "
                    "automatic reprojection first, or reproject the DEM manually."
                )
            )
        if band < 1 or band > source.bandCount():
            raise QgsProcessingException(self.tr("Elevation band is outside the raster range."))
        if not folder:
            raise QgsProcessingException(self.tr("Choose an output folder."))
        os.makedirs(folder, exist_ok=True)

        horizontal_m = self._horizontal_meters_per_unit(source.crs())
        vertical_m = 1.0 if z_unit == 0 else 0.3048
        pixel_width_m = abs(source.extent().width()) / max(1, source.width()) * horizontal_m
        pixel_height_m = abs(source.extent().height()) / max(1, source.height()) * horizontal_m
        pixel_area_m2 = pixel_width_m * pixel_height_m
        threshold_cells = max(1, int(round(threshold_ha * 10000.0 / pixel_area_m2)))

        outputs = {}
        paths = {
            self.FILLED_DEM: self._output_path(folder, prefix, "filled_dem", "tif"),
            self.FLOW_DIRECTION: self._output_path(folder, prefix, "flow_direction", "tif"),
            self.FLOW_ACCUMULATION: self._output_path(
                folder, prefix, "flow_accumulation", "tif"
            ),
            self.STREAM_RASTER: self._output_path(
                folder, prefix, "potential_streams", "tif"
            ),
            self.STREAMS: self._output_path(folder, prefix, "potential_streams", "gpkg"),
        }
        if create_basins:
            paths[self.BASINS] = self._output_path(folder, prefix, "watershed_basins", "tif")
        if create_twi:
            paths[self.TWI] = self._output_path(folder, prefix, "twi", "tif")

        feedback.pushInfo(
            self.tr(
                f"Priority-flood and Strahler D8 hydrology; {threshold_ha:g} ha = "
                f"{threshold_cells} contributing cells."
            )
        )
        try:
            hydrology_summary = calculate_complete_hydrology(
                input_dem_path=source.source().split("|")[0],
                band_number=band,
                filled_dem_path=paths[self.FILLED_DEM],
                direction_path=paths[self.FLOW_DIRECTION],
                accumulation_path=paths[self.FLOW_ACCUMULATION],
                stream_raster_path=paths[self.STREAM_RASTER],
                stream_vector_path=paths[self.STREAMS],
                threshold_cells=threshold_cells,
                pixel_area_m2=pixel_area_m2,
                horizontal_meters_per_unit=horizontal_m,
                vertical_meters_per_unit=vertical_m,
                twi_path=paths.get(self.TWI),
                basin_path=paths.get(self.BASINS),
                width_factor=width_factor,
                depth_factor=depth_factor,
            )
        except RuntimeError as error:
            raise QgsProcessingException(str(error)) from error
        for key, path in paths.items():
            if not os.path.exists(path):
                raise QgsProcessingException(self.tr(f"Hydrology output '{key}' was not created."))
            outputs[key] = path
        if hydrology_summary.get("stream_reaches", 0) == 0:
            feedback.pushWarning(
                self.tr(
                    "No stream reaches met the selected contributing-area threshold; "
                    "an empty stream layer was created and hydrology rasters remain valid."
                )
            )

        # Cartographic copy: Chaikin smoothing on the river polylines. The raw
        # D8 network stays untouched for hydrological calculations.
        smoothing_index = self.parameterAsEnum(parameters, self.SMOOTHING, context)
        simplify_tolerance = self.parameterAsDouble(
            parameters, self.SIMPLIFY_TOLERANCE, context
        )
        smoothing_summary = None
        if (smoothing_index > 0 or simplify_tolerance > 0) and os.path.exists(
            paths[self.STREAMS]
        ):
            smooth_path = self._output_path(
                folder, prefix, "potential_streams_smooth", "gpkg"
            )
            feedback.pushInfo(self.tr("Smoothing river polylines for cartographic display…"))
            try:
                smoothing_summary = smooth_geometries(
                    paths[self.STREAMS],
                    smooth_path,
                    iterations=smoothing_index,
                    simplify_tolerance=simplify_tolerance,
                )
                if os.path.exists(smooth_path) and smoothing_summary.get(
                    "smoothed_features", 0
                ) > 0:
                    outputs[self.STREAMS_SMOOTH] = smooth_path
            except RuntimeError as error:
                raise QgsProcessingException(str(error)) from error

        report_path = self._output_path(folder, prefix, "hydrology_report", "json")
        report = {
            "plugin": "Terrain Product Studio",
            "version": plugin_version(),
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "source": source.source(),
            "source_band": band,
            "crs": source.crs().authid() or source.crs().description(),
            "elevation_unit": "m" if z_unit == 0 else "ft",
            "minimum_contributing_area_ha": threshold_ha,
            "threshold_cells": threshold_cells,
            "pixel_area_m2": pixel_area_m2,
            "river_width_factor": width_factor,
            "river_depth_factor": depth_factor,
            "summary": hydrology_summary,
            "smoothing_summary": smoothing_summary,
            "note": (
                "Potential drainage inferred from DEM topography; it is not a surveyed "
                "hydrographic network."
            ),
            "outputs": outputs,
        }
        with open(report_path, "w", encoding="utf-8") as stream:
            json.dump(report, stream, ensure_ascii=False, indent=2)
        outputs[self.HYDROLOGY_REPORT] = report_path
        feedback.setProgress(100)
        return outputs
