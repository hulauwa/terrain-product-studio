"""Master Processing algorithm for producing a styled-ready terrain package."""

from __future__ import annotations

import json
import math
import os
from datetime import datetime, timezone

from qgis import processing
from qgis.PyQt.QtCore import QCoreApplication
from qgis.core import (
    QgsApplication,
    QgsProcessingAlgorithm,
    QgsProcessingException,
    QgsProcessingMultiStepFeedback,
    QgsProcessingOutputFile,
    QgsProcessingOutputRasterLayer,
    QgsProcessingOutputVectorLayer,
    QgsProcessingParameterBand,
    QgsProcessingParameterBoolean,
    QgsProcessingParameterEnum,
    QgsProcessingParameterExtent,
    QgsProcessingParameterFolderDestination,
    QgsProcessingParameterNumber,
    QgsProcessingParameterRasterLayer,
    QgsProcessingParameterString,
    QgsRasterLayer,
    QgsUnitTypes,
)

from ..core.dem_info import inspect_dem_layer
from ..core.intelligence_report import generate_intelligence_report
from ..core.math_utils import sanitize_prefix, unique_path
from ..core.flow_products import FlowProductBuilder, FlowProductError
from ..core.pipeline import plan_pipeline
from ..core.preprocessing import DemPreprocessor
from ..core.product_registry import DEFAULT_PRODUCT_REGISTRY
from ..core.presets import (
    DEFAULT_PALETTE,
    PALETTE_ORDER,
    TERRAIN_PALETTES,
    resolve_palette_stops,
)
from ..core import plugin_version
from ..core.qgis_compat import all_raster_statistics_flag
from ..core.provenance import analytical_assumptions, build_run_provenance
from ..core.smoothing import smooth_geometries
from ..core.spot_elevations import extract_spot_elevations
from ..core.geomorphon import classify_geomorphon
from ..core.thematic_terrain import (
    calculate_slope_suitability,
)
from ..core.bundle import create_bundle
from ..core.web_3d_viewer import generate_3d_web_viewer



def _number_type_double():
    """Return QgsProcessingParameterNumber Double type enum (Qt5 & Qt6 safe)."""
    try:
        return QgsProcessingParameterNumber.Type.Double
    except AttributeError:
        return getattr(QgsProcessingParameterNumber, "Double")


def _number_type_integer():
    """Return QgsProcessingParameterNumber Integer type enum (Qt5 & Qt6 safe)."""
    try:
        return QgsProcessingParameterNumber.Type.Integer
    except AttributeError:
        return getattr(QgsProcessingParameterNumber, "Integer")


class BuildTerrainPackageAlgorithm(QgsProcessingAlgorithm):
    INPUT = "INPUT"
    BAND = "BAND"
    OUTPUT_FOLDER = "OUTPUT_FOLDER"
    PREFIX = "PREFIX"
    EXTENT = "EXTENT"
    Z_UNIT = "Z_UNIT"
    AUTO_REPROJECT = "AUTO_REPROJECT"
    PALETTE = "PALETTE"
    COMPRESSION = "COMPRESSION"
    WEB_3D_QUALITY = "WEB_3D_QUALITY"
    PORTABLE_DEM_COPY = "PORTABLE_DEM_COPY"
    VERTICAL_EXAGGERATION = "VERTICAL_EXAGGERATION"
    AZIMUTH = "AZIMUTH"
    ALTITUDE = "ALTITUDE"
    ZEVENBERGEN = "ZEVENBERGEN"
    CREATE_COLOR_RELIEF = "CREATE_COLOR_RELIEF"
    CREATE_HILLSHADE = "CREATE_HILLSHADE"
    CREATE_MULTI_HILLSHADE = "CREATE_MULTI_HILLSHADE"
    CREATE_SLOPE = "CREATE_SLOPE"
    CREATE_ASPECT = "CREATE_ASPECT"
    CREATE_TRI = "CREATE_TRI"
    CREATE_TPI = "CREATE_TPI"
    CREATE_ROUGHNESS = "CREATE_ROUGHNESS"
    CREATE_PROFILE_CURVATURE = "CREATE_PROFILE_CURVATURE"
    CREATE_PLANFORM_CURVATURE = "CREATE_PLANFORM_CURVATURE"
    CREATE_CONTOURS = "CREATE_CONTOURS"
    CREATE_SPOT_ELEVATIONS = "CREATE_SPOT_ELEVATIONS"
    CREATE_SUITABILITY = "CREATE_SUITABILITY"
    CREATE_LANDSLIDE = "CREATE_LANDSLIDE"
    CREATE_GEOMORPHON = "CREATE_GEOMORPHON"
    CREATE_SPI = "CREATE_SPI"
    CREATE_STI = "CREATE_STI"
    CREATE_MULTIHAZARD = "CREATE_MULTIHAZARD"
    CREATE_BUNDLE = "CREATE_BUNDLE"
    CREATE_3D_VIEWER = "CREATE_3D_VIEWER"
    CREATE_INTELLIGENCE_REPORT = "CREATE_INTELLIGENCE_REPORT"
    CREATE_HYDROLOGY = "CREATE_HYDROLOGY"
    STREAM_THRESHOLD_HA = "STREAM_THRESHOLD_HA"
    CREATE_BASINS = "CREATE_BASINS"
    CREATE_TWI = "CREATE_TWI"
    STREAM_SMOOTHING = "STREAM_SMOOTHING"
    STREAM_SIMPLIFY_TOLERANCE = "STREAM_SIMPLIFY_TOLERANCE"
    CONTOUR_INTERVAL = "CONTOUR_INTERVAL"
    INDEX_MULTIPLIER = "INDEX_MULTIPLIER"
    SPOT_PCT = "SPOT_PCT"
    SMOOTHING = "SMOOTHING"
    SIMPLIFY_TOLERANCE = "SIMPLIFY_TOLERANCE"
    ACCUMULATION = "ACCUMULATION"
    GEOMORPHON_RADIUS_M = "GEOMORPHON_RADIUS_M"
    GEOMORPHON_TOLERANCE = "GEOMORPHON_TOLERANCE"
    MULTIHAZARD_WEIGHT_LANDSLIDE = "MULTIHAZARD_WEIGHT_LANDSLIDE"
    MULTIHAZARD_WEIGHT_TWI = "MULTIHAZARD_WEIGHT_TWI"
    MULTIHAZARD_WEIGHT_SLOPE = "MULTIHAZARD_WEIGHT_SLOPE"

    WORKING_DEM = "WORKING_DEM"
    FILLED_DEM = "FILLED_DEM"
    FLOW_DIRECTION = "FLOW_DIRECTION"
    FLOW_ACCUMULATION = "FLOW_ACCUMULATION"
    STREAM_RASTER = "STREAM_RASTER"
    STREAMS = "STREAMS"
    STREAMS_SMOOTH = "STREAMS_SMOOTH"
    BASINS = "BASINS"
    TWI = "TWI"
    HYDROLOGY_REPORT = "HYDROLOGY_REPORT"
    COLOR_RELIEF = "COLOR_RELIEF"
    HILLSHADE = "HILLSHADE"
    MULTI_HILLSHADE = "MULTI_HILLSHADE"
    SLOPE = "SLOPE"
    ASPECT = "ASPECT"
    TRI = "TRI"
    TPI = "TPI"
    ROUGHNESS = "ROUGHNESS"
    PROFILE_CURVATURE = "PROFILE_CURVATURE"
    PLANFORM_CURVATURE = "PLANFORM_CURVATURE"
    CONTOURS = "CONTOURS"
    CONTOURS_SMOOTH = "CONTOURS_SMOOTH"
    SPOT_ELEVATIONS = "SPOT_ELEVATIONS"
    SUITABILITY = "SUITABILITY"
    LANDSLIDE_HAZARD = "LANDSLIDE_HAZARD"
    LS_FACTOR = "LS_FACTOR"
    GEOMORPHON = "GEOMORPHON"
    SPI = "SPI"
    STI = "STI"
    MULTIHAZARD = "MULTIHAZARD"
    BUNDLE = "BUNDLE"
    VIEWER_3D = "VIEWER_3D"
    INTELLIGENCE_REPORT = "INTELLIGENCE_REPORT"
    REPORT = "REPORT"

    _PALETTE_KEYS = PALETTE_ORDER
    _COMPRESSION_VALUES = ("DEFLATE", "ZSTD", "LZW", "NONE")

    @staticmethod
    def tr(message):
        return QCoreApplication.translate("TerrainProductStudio", message)

    def name(self):
        return "buildterrainpackage"

    def displayName(self):
        return self.tr("Build terrain product package")

    def group(self):
        return self.tr("Terrain Product Studio")

    def groupId(self):
        return "terrainstudio"

    def shortHelpString(self):
        return self.tr(
            "Creates a consistent package of DEM-derived cartographic and analytical products. "
            "A DEM in angular coordinates is automatically reprojected to a local UTM CRS before "
            "slope and relief calculations. Existing files are never overwritten. Hydrology runs "
            "inside the same dependency pipeline before products which require flow accumulation."
        )

    def createInstance(self):
        return BuildTerrainPackageAlgorithm()

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
        self.addParameter(
            QgsProcessingParameterFolderDestination(self.OUTPUT_FOLDER, self.tr("Output folder"))
        )
        self.addParameter(
            QgsProcessingParameterString(self.PREFIX, self.tr("Output filename prefix"), "terrain")
        )
        self.addParameter(
            QgsProcessingParameterExtent(
                self.EXTENT,
                self.tr("Processing extent (clip boundary, optional)"),
                optional=True,
            )
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
            QgsProcessingParameterBoolean(
                self.AUTO_REPROJECT,
                self.tr("Automatically reproject geographic DEM to local UTM"),
                defaultValue=True,
            )
        )
        self.addParameter(
            QgsProcessingParameterEnum(
                self.PALETTE,
                self.tr("Elevation color palette"),
                options=[TERRAIN_PALETTES[key]["label"] for key in self._PALETTE_KEYS],
                defaultValue=PALETTE_ORDER.index(DEFAULT_PALETTE),
            )
        )
        self.addParameter(
            QgsProcessingParameterEnum(
                self.COMPRESSION,
                self.tr("GeoTIFF compression"),
                options=list(self._COMPRESSION_VALUES),
                defaultValue=0,
            )
        )
        self.addParameter(
            QgsProcessingParameterEnum(
                self.WEB_3D_QUALITY,
                self.tr("Web 3D display quality"),
                options=[
                    self.tr("Fast · 256 samples"),
                    self.tr("Balanced · 384 samples"),
                    self.tr("High · 512 samples"),
                ],
                defaultValue=1,
            )
        )
        self.addParameter(
            QgsProcessingParameterBoolean(
                self.PORTABLE_DEM_COPY,
                self.tr("Include a portable numeric DEM copy for sharing"),
                defaultValue=False,
            )
        )

        self.addParameter(
            QgsProcessingParameterNumber(
                self.VERTICAL_EXAGGERATION,
                self.tr("Hillshade vertical exaggeration"),
                type=_number_type_double(),
                minValue=0.01,
                maxValue=100.0,
                defaultValue=1.0,
            )
        )

        self.addParameter(
            QgsProcessingParameterNumber(
                self.AZIMUTH,
                self.tr("Hillshade azimuth"),
                type=_number_type_double(),
                minValue=0.0,
                maxValue=360.0,
                defaultValue=315.0,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.ALTITUDE,
                self.tr("Hillshade light altitude"),
                type=_number_type_double(),
                minValue=0.0,
                maxValue=90.0,
                defaultValue=45.0,
            )
        )
        self.addParameter(
            QgsProcessingParameterBoolean(
                self.ZEVENBERGEN,
                self.tr("Use Zevenbergen–Thorne formula"),
                defaultValue=False,
            )
        )

        # The numeric working DEM is always exposed and styled.  Default
        # products add multidirectional hillshade and spot peaks; the rendered
        # RGB color-relief copy is now opt-in for interoperability.
        for product in DEFAULT_PRODUCT_REGISTRY.specs(section="terrain"):
            self.addParameter(
                QgsProcessingParameterBoolean(
                    product.parameter,
                    self.tr(product.processing_label),
                    defaultValue=product.default_enabled,
                )
            )

        self.addParameter(
            QgsProcessingParameterRasterLayer(
                self.ACCUMULATION,
                self.tr(
                    "Existing flow accumulation raster (optional — otherwise "
                    "hydrology is generated automatically when required)"
                ),
                optional=True,
            )
        )
        self.addParameter(
            QgsProcessingParameterBoolean(
                self.CREATE_HYDROLOGY,
                self.tr("Create hydrology and river network"),
                defaultValue=False,
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
            QgsProcessingParameterBoolean(
                self.CREATE_BASINS,
                self.tr("Create watershed basin raster"),
                defaultValue=True,
            )
        )
        self.addParameter(
            QgsProcessingParameterBoolean(
                self.CREATE_TWI,
                self.tr("Create Topographic Wetness Index (TWI)"),
                defaultValue=False,
            )
        )
        self.addParameter(
            QgsProcessingParameterEnum(
                self.STREAM_SMOOTHING,
                self.tr("River smoothness (cartographic copy)"),
                options=[self.tr("Off"), self.tr("Light"), self.tr("Medium"), self.tr("Heavy")],
                defaultValue=0,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.STREAM_SIMPLIFY_TOLERANCE,
                self.tr("Simplify rivers before smoothing (map units, 0 = off)"),
                type=_number_type_double(),
                minValue=0.0,
                defaultValue=0.0,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.GEOMORPHON_RADIUS_M,
                self.tr("Geomorphon search radius (m)"),
                type=_number_type_double(),
                minValue=1.0,
                maxValue=100000.0,
                defaultValue=100.0,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.GEOMORPHON_TOLERANCE,
                self.tr("Geomorphon flatness tolerance (fraction of relief)"),
                type=_number_type_double(),
                minValue=0.0001,
                maxValue=1.0,
                defaultValue=0.01,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.MULTIHAZARD_WEIGHT_LANDSLIDE,
                self.tr("Multi-hazard weight: landslide"),
                type=_number_type_double(),
                minValue=0.0,
                maxValue=1.0,
                defaultValue=0.5,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.MULTIHAZARD_WEIGHT_TWI,
                self.tr("Multi-hazard weight: TWI"),
                type=_number_type_double(),
                minValue=0.0,
                maxValue=1.0,
                defaultValue=0.3,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.MULTIHAZARD_WEIGHT_SLOPE,
                self.tr("Multi-hazard weight: slope"),
                type=_number_type_double(),
                minValue=0.0,
                maxValue=1.0,
                defaultValue=0.2,
            )
        )
        bundle_product = DEFAULT_PRODUCT_REGISTRY.require(self.BUNDLE)
        self.addParameter(
            QgsProcessingParameterBoolean(
                bundle_product.parameter,
                self.tr(bundle_product.processing_label),
                defaultValue=bundle_product.default_enabled,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.CONTOUR_INTERVAL,
                self.tr("Minor contour interval (elevation units)"),
                type=_number_type_double(),
                minValue=0.000001,
                defaultValue=10.0,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.INDEX_MULTIPLIER,
                self.tr("Index contour multiplier"),
                type=_number_type_integer(),
                minValue=1,
                maxValue=20,
                defaultValue=5,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.SPOT_PCT,
                self.tr(
                    "Spot peak elevation threshold (% of relief; 0 = all local peaks)"
                ),
                type=_number_type_integer(),
                minValue=0,
                maxValue=100,
                defaultValue=80,
            )
        )
        self.addParameter(
            QgsProcessingParameterEnum(
                self.SMOOTHING,
                self.tr("Contour smoothness (cartographic copy)"),
                options=[self.tr("Off"), self.tr("Light"), self.tr("Medium"), self.tr("Heavy")],
                defaultValue=2,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.SIMPLIFY_TOLERANCE,
                self.tr("Simplify contours before smoothing (map units, 0 = off)"),
                type=_number_type_double(),
                minValue=0.0,
                defaultValue=0.0,
            )
        )

        self.addOutput(QgsProcessingOutputRasterLayer(self.WORKING_DEM, self.tr("Working DEM")))
        self.addOutput(QgsProcessingOutputRasterLayer(self.FILLED_DEM, self.tr("Filled DEM")))
        self.addOutput(QgsProcessingOutputRasterLayer(self.FLOW_DIRECTION, self.tr("D8 flow direction")))
        self.addOutput(QgsProcessingOutputRasterLayer(self.FLOW_ACCUMULATION, self.tr("Flow accumulation")))
        self.addOutput(QgsProcessingOutputRasterLayer(self.STREAM_RASTER, self.tr("Potential stream raster")))
        self.addOutput(QgsProcessingOutputVectorLayer(self.STREAMS, self.tr("Potential drainage network")))
        self.addOutput(QgsProcessingOutputVectorLayer(self.STREAMS_SMOOTH, self.tr("Smoothed rivers")))
        self.addOutput(QgsProcessingOutputRasterLayer(self.BASINS, self.tr("Watershed basins")))
        self.addOutput(QgsProcessingOutputRasterLayer(self.TWI, self.tr("Topographic Wetness Index")))
        self.addOutput(QgsProcessingOutputFile(self.HYDROLOGY_REPORT, self.tr("Hydrology report")))
        self.addOutput(QgsProcessingOutputRasterLayer(self.COLOR_RELIEF, self.tr("Color relief")))
        self.addOutput(QgsProcessingOutputRasterLayer(self.HILLSHADE, self.tr("Hillshade")))
        self.addOutput(
            QgsProcessingOutputRasterLayer(self.MULTI_HILLSHADE, self.tr("Multidirectional hillshade"))
        )
        self.addOutput(QgsProcessingOutputRasterLayer(self.SLOPE, self.tr("Slope")))
        self.addOutput(QgsProcessingOutputRasterLayer(self.ASPECT, self.tr("Aspect")))
        self.addOutput(QgsProcessingOutputRasterLayer(self.TRI, self.tr("TRI")))
        self.addOutput(QgsProcessingOutputRasterLayer(self.TPI, self.tr("TPI")))
        self.addOutput(QgsProcessingOutputRasterLayer(self.ROUGHNESS, self.tr("Roughness")))
        self.addOutput(QgsProcessingOutputRasterLayer(self.PROFILE_CURVATURE, self.tr("Profile curvature")))
        self.addOutput(QgsProcessingOutputRasterLayer(self.PLANFORM_CURVATURE, self.tr("Planform curvature")))
        self.addOutput(QgsProcessingOutputVectorLayer(self.CONTOURS, self.tr("Contours")))
        self.addOutput(
            QgsProcessingOutputVectorLayer(
                self.CONTOURS_SMOOTH, self.tr("Smoothed contours (cartographic copy)")
            )
        )
        self.addOutput(QgsProcessingOutputVectorLayer(self.SPOT_ELEVATIONS, self.tr("Spot elevation peaks")))
        self.addOutput(QgsProcessingOutputRasterLayer(self.SUITABILITY, self.tr("Slope construction suitability")))
        self.addOutput(QgsProcessingOutputRasterLayer(self.LANDSLIDE_HAZARD, self.tr("Landslide hazard risk")))
        self.addOutput(QgsProcessingOutputRasterLayer(self.LS_FACTOR, self.tr("RUSLE LS factor")))
        self.addOutput(QgsProcessingOutputRasterLayer(self.GEOMORPHON, self.tr("Geomorphon terrain forms")))
        self.addOutput(QgsProcessingOutputRasterLayer(self.SPI, self.tr("Stream Power Index (SPI)")))
        self.addOutput(QgsProcessingOutputRasterLayer(self.STI, self.tr("Sediment Transport Index (STI)")))
        self.addOutput(QgsProcessingOutputRasterLayer(self.MULTIHAZARD, self.tr("Multi-hazard composite index")))
        self.addOutput(QgsProcessingOutputFile(self.BUNDLE, self.tr("GeoPackage bundle of all products")))
        self.addOutput(QgsProcessingOutputFile(self.VIEWER_3D, self.tr("Interactive 3D Web Viewer")))
        self.addOutput(QgsProcessingOutputFile(self.INTELLIGENCE_REPORT, self.tr("Topographic Intelligence Report")))
        self.addOutput(QgsProcessingOutputFile(self.REPORT, self.tr("Processing report")))


    @staticmethod
    def _available_parameters(algorithm_id):
        algorithm = QgsApplication.processingRegistry().algorithmById(algorithm_id)
        if algorithm is None:
            if algorithm_id.startswith("terrainstudio:"):
                provider_name = "Terrain Product Studio"
            elif algorithm_id.startswith("grass:"):
                provider_name = "GRASS"
            else:
                provider_name = "GDAL"
            raise QgsProcessingException(
                f"Required Processing algorithm '{algorithm_id}' is not available. "
                f"Enable the {provider_name} provider in QGIS Processing settings."
            )
        return {definition.name() for definition in algorithm.parameterDefinitions()}

    def _run_child(self, algorithm_id, parameters, context, feedback):
        available = self._available_parameters(algorithm_id)
        compatible = {key: value for key, value in parameters.items() if key in available}
        return processing.run(
            algorithm_id,
            compatible,
            context=context,
            feedback=feedback,
            is_child_algorithm=True,
        )

    @staticmethod
    def _creation_options(compression):
        # GTiff compression and overview-friendly tiling can use multiple CPU
        # cores without sharing a QGIS Processing context across threads.
        options = ["TILED=YES", "BIGTIFF=IF_SAFER", "NUM_THREADS=ALL_CPUS"]
        if compression != "NONE":
            options.insert(0, f"COMPRESS={compression}")
        return "|".join(options)

    @staticmethod
    def _output_path(folder, prefix, suffix, extension):
        return unique_path(os.path.join(folder, f"{prefix}_{suffix}.{extension}"))

    @staticmethod
    def _write_color_table(path, minimum, maximum, palette):
        stops = resolve_palette_stops(palette, minimum, maximum)
        with open(path, "w", encoding="utf-8") as stream:
            stream.write("nv 255 255 255 0\n")
            for value, red, green, blue in stops:
                stream.write(f"{value:.12g} {red} {green} {blue} 255\n")

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
    def _rasters_share_grid(first, second):
        """Return True when two QGIS rasters share CRS, dimensions and extent."""

        if first.crs() != second.crs():
            return False
        if first.width() != second.width() or first.height() != second.height():
            return False
        first_extent = first.extent()
        second_extent = second.extent()
        tolerance = max(
            abs(first_extent.width()), abs(first_extent.height()), 1.0
        ) * 1e-9
        return all(
            abs(left - right) <= tolerance
            for left, right in (
                (first_extent.xMinimum(), second_extent.xMinimum()),
                (first_extent.yMinimum(), second_extent.yMinimum()),
                (first_extent.xMaximum(), second_extent.xMaximum()),
                (first_extent.yMaximum(), second_extent.yMaximum()),
            )
        )

    def processAlgorithm(self, parameters, context, feedback):
        source = self.parameterAsRasterLayer(parameters, self.INPUT, context)
        band = self.parameterAsInt(parameters, self.BAND, context)
        folder = self.parameterAsString(parameters, self.OUTPUT_FOLDER, context)
        prefix = sanitize_prefix(self.parameterAsString(parameters, self.PREFIX, context))
        z_unit_index = self.parameterAsEnum(parameters, self.Z_UNIT, context)
        auto_reproject = self.parameterAsBool(parameters, self.AUTO_REPROJECT, context)
        palette_index = self.parameterAsEnum(parameters, self.PALETTE, context)
        compression_index = self.parameterAsEnum(parameters, self.COMPRESSION, context)
        web_3d_quality = self.parameterAsEnum(
            parameters, self.WEB_3D_QUALITY, context
        )
        portable_dem_copy = self.parameterAsBool(
            parameters, self.PORTABLE_DEM_COPY, context
        )
        vertical_exaggeration = self.parameterAsDouble(
            parameters, self.VERTICAL_EXAGGERATION, context
        )
        azimuth = self.parameterAsDouble(parameters, self.AZIMUTH, context)
        altitude = self.parameterAsDouble(parameters, self.ALTITUDE, context)
        zevenbergen = self.parameterAsBool(parameters, self.ZEVENBERGEN, context)
        contour_interval = self.parameterAsDouble(parameters, self.CONTOUR_INTERVAL, context)
        index_multiplier = self.parameterAsInt(parameters, self.INDEX_MULTIPLIER, context)
        spot_pct = self.parameterAsInt(parameters, self.SPOT_PCT, context)
        geomorphon_radius_m = self.parameterAsDouble(parameters, self.GEOMORPHON_RADIUS_M, context)
        geomorphon_tolerance = self.parameterAsDouble(parameters, self.GEOMORPHON_TOLERANCE, context)
        smoothing_index = self.parameterAsEnum(parameters, self.SMOOTHING, context)
        simplify_tolerance = self.parameterAsDouble(
            parameters, self.SIMPLIFY_TOLERANCE, context
        )
        create_hydrology_requested = self.parameterAsBool(
            parameters, self.CREATE_HYDROLOGY, context
        )
        stream_threshold_ha = self.parameterAsDouble(
            parameters, self.STREAM_THRESHOLD_HA, context
        )
        create_basins = self.parameterAsBool(parameters, self.CREATE_BASINS, context)
        create_twi_requested = self.parameterAsBool(parameters, self.CREATE_TWI, context)
        stream_smoothing = self.parameterAsEnum(
            parameters, self.STREAM_SMOOTHING, context
        )
        stream_simplify_tolerance = self.parameterAsDouble(
            parameters, self.STREAM_SIMPLIFY_TOLERANCE, context
        )
        accumulation_input = None
        accumulation_layer = self.parameterAsRasterLayer(parameters, self.ACCUMULATION, context)
        if accumulation_layer is not None and accumulation_layer.isValid():
            try:
                accumulation_input = accumulation_layer.source().split("|")[0]
            except (AttributeError, ValueError):
                accumulation_input = None

        if source is None or not source.isValid():
            raise QgsProcessingException(self.tr("Input DEM is missing or invalid."))
        if band < 1 or band > source.bandCount():
            raise QgsProcessingException(self.tr("Elevation band is outside the raster band range."))
        if not source.crs().isValid():
            raise QgsProcessingException(
                self.tr("Input DEM has no valid CRS. Assign the correct CRS before processing.")
            )
        if not folder:
            raise QgsProcessingException(self.tr("Choose an output folder."))
        os.makedirs(folder, exist_ok=True)
        style_folder = os.path.join(folder, "styles")
        os.makedirs(style_folder, exist_ok=True)

        palette_index = min(max(0, palette_index), len(self._PALETTE_KEYS) - 1)
        palette_key = self._PALETTE_KEYS[palette_index]
        compression_index = min(max(0, compression_index), len(self._COMPRESSION_VALUES) - 1)
        compression = self._COMPRESSION_VALUES[compression_index]
        creation_options = self._creation_options(compression)

        selected = {
            product.key: self.parameterAsBool(
                parameters, product.parameter, context
            )
            for product in DEFAULT_PRODUCT_REGISTRY.specs()
        }
        if not any(selected.values()) and not create_hydrology_requested:
            raise QgsProcessingException(self.tr("Select at least one terrain product."))

        pipeline_plan = plan_pipeline(
            (key for key, enabled in selected.items() if enabled),
            create_hydrology=create_hydrology_requested,
            create_twi=create_twi_requested,
            accumulation_available=bool(accumulation_input),
        )
        for auto_product in pipeline_plan.auto_enabled_products:
            selected[auto_product] = True

        step_count = (
            sum(selected.values())
            + 4
            + int(pipeline_plan.run_hydrology)
            + int(pipeline_plan.create_twi and not pipeline_plan.run_hydrology)
            + int(portable_dem_copy)
        )
        multi = QgsProcessingMultiStepFeedback(step_count, feedback)
        current_step = 0
        outputs = {self.OUTPUT_FOLDER: folder}
        warnings = []

        if pipeline_plan.auto_enabled_products:
            warnings.append(
                "Pipeline dependency auto-enabled: "
                + ", ".join(sorted(pipeline_plan.auto_enabled_products))
            )
        if pipeline_plan.run_hydrology and not create_hydrology_requested:
            warnings.append(
                "Hydrology was auto-enabled because selected products require real "
                "flow accumulation."
            )

        source_info = inspect_dem_layer(source, band, sum(selected.values()))
        warnings.extend(source_info["warnings"])
        def advance(message):
            nonlocal current_step
            multi.setCurrentStep(current_step)
            current_step += 1
            multi.pushInfo(message)

        preprocessor = DemPreprocessor(
            run_child=lambda algorithm_id, child_parameters: self._run_child(
                algorithm_id, child_parameters, context, multi
            ),
            output_path=lambda suffix, extension: self._output_path(
                folder, prefix, suffix, extension
            ),
            extent_resolver=lambda crs: self.parameterAsExtent(
                parameters, self.EXTENT, context, crs
            ),
            advance=advance,
            feedback=multi,
            creation_options=creation_options,
            prefix=prefix,
            translate=self.tr,
        )
        prepared_dem = preprocessor.prepare(
            source,
            auto_reproject=auto_reproject,
            source_info=source_info,
        )
        outputs.update(prepared_dem.output_paths)
        warnings.extend(prepared_dem.warnings)
        working_dem = prepared_dem.processing_input
        working_layer = prepared_dem.layer
        working_crs = prepared_dem.crs
        applied_clip_extent = prepared_dem.applied_clip_extent
        # Always expose one canonical numeric DEM.  For an unchanged projected
        # input this deliberately references the source instead of duplicating
        # a potentially large raster in the output directory.
        canonical_dem_path = (
            working_dem
            if isinstance(working_dem, str)
            else source.source().split("|")[0]
        )
        if portable_dem_copy:
            try:
                already_portable = os.path.commonpath(
                    [os.path.abspath(canonical_dem_path), os.path.abspath(folder)]
                ) == os.path.abspath(folder)
            except ValueError:
                already_portable = False
            if not already_portable:
                advance(self.tr("Copying one canonical DEM for portable sharing…"))
                portable_path = self._output_path(
                    folder, prefix, "canonical_dem", "tif"
                )
                canonical_dem_path = preprocessor.create_portable_copy(
                    canonical_dem_path, portable_path, band
                )
        outputs[self.WORKING_DEM] = canonical_dem_path

        if multi.isCanceled():
            return outputs

        if accumulation_input and not pipeline_plan.run_hydrology:
            accumulation_grid = QgsRasterLayer(
                accumulation_input, f"{prefix}_flow_accumulation_input"
            )
            if not accumulation_grid.isValid() or not self._rasters_share_grid(
                working_layer, accumulation_grid
            ):
                raise QgsProcessingException(
                    self.tr(
                        "The supplied flow accumulation raster must have the same "
                        "CRS, dimensions and extent as the preprocessed DEM."
                    )
                )

        stats = working_layer.dataProvider().bandStatistics(
            band,
            all_raster_statistics_flag(),
            working_layer.extent(),
            250000,
        )
        minimum = float(stats.minimumValue)
        maximum = float(stats.maximumValue)
        display_minimum, display_maximum = minimum, maximum
        try:
            cut_minimum, cut_maximum = working_layer.dataProvider().cumulativeCut(
                band, 0.02, 0.98, working_layer.extent(), 250000
            )
            if cut_minimum < cut_maximum:
                display_minimum, display_maximum = float(cut_minimum), float(cut_maximum)
        except (AttributeError, TypeError, RuntimeError):
            pass
        horizontal_m = self._horizontal_meters_per_unit(working_crs)
        vertical_m = 1.0 if z_unit_index == 0 else 0.3048
        scale = horizontal_m / vertical_m

        # Hydrology is part of the master DAG in v2.2: preprocessing happens
        # once, then real accumulation is available before any dependent
        # terrain indices are calculated.
        if pipeline_plan.run_hydrology:
            if multi.isCanceled():
                return outputs
            multi.setCurrentStep(current_step)
            current_step += 1
            multi.pushInfo(
                self.tr(
                    "Running hydrology before flow-dependent terrain products…"
                )
            )
            hydrology_outputs = self._run_child(
                "terrainstudio:buildhydrology",
                {
                    "INPUT": working_dem,
                    "BAND": band,
                    "OUTPUT_FOLDER": folder,
                    "PREFIX": prefix,
                    "Z_UNIT": z_unit_index,
                    "STREAM_THRESHOLD_HA": stream_threshold_ha,
                    "CREATE_BASINS": create_basins,
                    "CREATE_TWI": pipeline_plan.create_twi,
                    "SMOOTHING": stream_smoothing,
                    "SIMPLIFY_TOLERANCE": stream_simplify_tolerance,
                },
                context,
                multi,
            )
            outputs.update(hydrology_outputs)
            accumulation_input = str(
                hydrology_outputs.get(self.FLOW_ACCUMULATION, "")
            )
            if not accumulation_input or not os.path.exists(accumulation_input):
                raise QgsProcessingException(
                    self.tr("Hydrology did not create a valid flow accumulation raster.")
                )
            hydrology_report_path = str(
                hydrology_outputs.get(self.HYDROLOGY_REPORT, "")
            )
            if hydrology_report_path and os.path.exists(hydrology_report_path):
                try:
                    with open(hydrology_report_path, encoding="utf-8") as stream:
                        hydrology_manifest = json.load(stream)
                    if hydrology_manifest.get("summary", {}).get(
                        "stream_reaches", 0
                    ) == 0:
                        warnings.append(
                            "No stream reaches met the selected contributing-area "
                            "threshold; hydrology rasters remain valid."
                        )
                except (OSError, ValueError, TypeError):
                    warnings.append(
                        "The hydrology summary could not be read into the final manifest."
                    )

        def run_product(output_key, algorithm_id, suffix, algorithm_parameters, extension="tif"):
            nonlocal current_step
            if not selected[output_key]:
                return
            if multi.isCanceled():
                return
            multi.setCurrentStep(current_step)
            current_step += 1
            destination = self._output_path(folder, prefix, suffix, extension)
            child_parameters = dict(algorithm_parameters)
            child_parameters.update(
                {
                    "INPUT": working_dem,
                    "BAND": band,
                    "OUTPUT": destination,
                }
            )
            if extension.lower() in {"tif", "tiff"}:
                child_parameters["CREATION_OPTIONS"] = creation_options
                child_parameters["OPTIONS"] = creation_options
            child_parameters.setdefault("EXTRA", "")
            multi.pushInfo(self.tr(f"Creating {suffix.replace('_', ' ')}…"))
            result = self._run_child(algorithm_id, child_parameters, context, multi)
            if not os.path.exists(destination):
                raise QgsProcessingException(
                    self.tr(f"The {suffix.replace('_', ' ')} output was not created.")
                )
            outputs[output_key] = result["OUTPUT"]

        if selected[self.COLOR_RELIEF]:
            color_table = unique_path(os.path.join(style_folder, f"{prefix}_elevation_colors.txt"))
            self._write_color_table(
                color_table,
                display_minimum,
                display_maximum,
                TERRAIN_PALETTES[palette_key],
            )
            run_product(
                self.COLOR_RELIEF,
                "gdal:colorrelief",
                "color_relief",
                {"COLOR_TABLE": color_table, "MATCH_MODE": 2, "EXTRA": "-alpha"},
            )

        hillshade_parameters = {
            "Z_FACTOR": vertical_exaggeration,
            "SCALE": scale,
            "AZIMUTH": azimuth,
            "ALTITUDE": altitude,
            "COMPUTE_EDGES": True,
            "ZEVENBERGEN": zevenbergen,
        }
        run_product(
            self.HILLSHADE,
            "gdal:hillshade",
            "hillshade",
            dict(hillshade_parameters, MULTIDIRECTIONAL=False),
        )
        run_product(
            self.MULTI_HILLSHADE,
            "gdal:hillshade",
            "hillshade_multidirectional",
            dict(hillshade_parameters, MULTIDIRECTIONAL=True),
        )
        run_product(
            self.SLOPE,
            "gdal:slope",
            "slope_deg",
            {
                "SCALE": scale,
                "AS_PERCENT": False,
                "COMPUTE_EDGES": True,
                "ZEVENBERGEN": zevenbergen,
            },
        )
        run_product(
            self.ASPECT,
            "gdal:aspect",
            "aspect",
            {
                "TRIG_ANGLE": False,
                "ZERO_FLAT": False,
                "COMPUTE_EDGES": True,
                "ZEVENBERGEN": zevenbergen,
            },
        )
        run_product(
            self.TRI,
            "gdal:triterrainruggednessindex",
            "tri",
            {"COMPUTE_EDGES": True},
        )
        run_product(
            self.TPI,
            "gdal:tpitopographicpositionindex",
            "tpi",
            {"COMPUTE_EDGES": True},
        )
        run_product(
            self.ROUGHNESS,
            "gdal:roughness",
            "roughness",
            {"COMPUTE_EDGES": True},
        )
        run_product(
            self.CONTOURS,
            "gdal:contour",
            "contours",
            {
                "INTERVAL": contour_interval,
                "FIELD_NAME": "ELEV",
                "OFFSET": 0.0,
                "CREATE_3D": False,
                "IGNORE_NODATA": False,
                "NODATA": None,
            },
            extension="gpkg",
        )

        # Cartographic copy: Chaikin smoothing (+ optional Douglas-Peucker
        # pre-pass) on a display-only contours file. The raw contours keep
        # their exact coordinates for analytical use.
        if selected[self.CONTOURS] and outputs.get(self.CONTOURS):
            if smoothing_index > 0 or simplify_tolerance > 0:
                if not multi.isCanceled():
                    multi.setCurrentStep(current_step)
                    current_step += 1
                    smooth_path = self._output_path(
                        folder, prefix, "contours_smooth", "gpkg"
                    )
                    multi.pushInfo(self.tr("Smoothing contours for cartographic display…"))
                    try:
                        summary = smooth_geometries(
                            outputs[self.CONTOURS],
                            smooth_path,
                            iterations=smoothing_index,
                            simplify_tolerance=simplify_tolerance,
                        )
                        if os.path.exists(smooth_path) and summary.get(
                            "smoothed_features", 0
                        ) > 0:
                            outputs[self.CONTOURS_SMOOTH] = smooth_path
                    except Exception as err:
                        warnings.append(f"Contour smoothing notice: {err}")

        if selected[self.SPOT_ELEVATIONS]:
            if not multi.isCanceled():
                multi.setCurrentStep(current_step)
                current_step += 1
                spot_path = self._output_path(folder, prefix, "spot_elevations", "gpkg")
                multi.pushInfo(self.tr("Extracting spot elevation peaks…"))
                try:
                    dem_path = working_dem if isinstance(working_dem, str) else source.source().split("|")[0]
                    count = extract_spot_elevations(
                        dem_path,
                        band,
                        spot_path,
                        threshold_pct=float(spot_pct),
                    )
                    if count > 0:
                        outputs[self.SPOT_ELEVATIONS] = spot_path
                except Exception as err:
                    warnings.append(f"Spot elevation extraction notice: {err}")

        # Slope Suitability for Construction
        if selected[self.SUITABILITY] and outputs.get(self.SLOPE):
            if not multi.isCanceled():
                multi.setCurrentStep(current_step)
                current_step += 1
                suit_path = self._output_path(folder, prefix, "slope_suitability", "tif")
                multi.pushInfo(self.tr("Evaluating urban construction slope suitability…"))
                try:
                    calculate_slope_suitability(outputs[self.SLOPE], suit_path)
                    if os.path.exists(suit_path):
                        outputs[self.SUITABILITY] = suit_path
                except Exception as err:
                    warnings.append(f"Suitability notice: {err}")

        flow_builder = FlowProductBuilder(
            output_path=lambda suffix, extension: self._output_path(
                folder, prefix, suffix, extension
            ),
            advance=advance,
            feedback=multi,
            translate=self.tr,
        )
        try:
            warnings.extend(
                flow_builder.build(
                    outputs,
                    selected,
                    create_twi=pipeline_plan.create_twi,
                    accumulation_path=accumulation_input,
                    multihazard_weights=(
                        float(
                            self.parameterAsDouble(
                                parameters,
                                self.MULTIHAZARD_WEIGHT_LANDSLIDE,
                                context,
                            )
                        ),
                        float(
                            self.parameterAsDouble(
                                parameters,
                                self.MULTIHAZARD_WEIGHT_TWI,
                                context,
                            )
                        ),
                        float(
                            self.parameterAsDouble(
                                parameters,
                                self.MULTIHAZARD_WEIGHT_SLOPE,
                                context,
                            )
                        ),
                    ),
                )
            )
        except FlowProductError as error:
            raise QgsProcessingException(str(error)) from error

        working_dem_path = working_dem if isinstance(working_dem, str) else source.source().split("|")[0]

        # Geomorphon Terrain Forms
        if selected[self.GEOMORPHON]:
            if not multi.isCanceled():
                multi.setCurrentStep(current_step)
                current_step += 1
                geomorphon_path = self._output_path(folder, prefix, "geomorphon", "tif")
                multi.pushInfo(self.tr("Classifying 10 geomorphon terrain forms…"))
                try:
                    geomorphon_stats = classify_geomorphon(
                        working_dem_path,
                        geomorphon_path,
                        radius_m=geomorphon_radius_m,
                        tolerance=geomorphon_tolerance,
                    )
                    if os.path.exists(geomorphon_path):
                        outputs[self.GEOMORPHON] = geomorphon_path
                        dominant = ", ".join(
                            f"{name} {pct:.0f}%"
                            for name, pct in sorted(
                                geomorphon_stats.items(),
                                key=lambda item: item[1],
                                reverse=True,
                            )[:3]
                        )
                        multi.pushInfo(self.tr(f"Geomorphon dominant forms: {dominant}"))
                except Exception as err:
                    warnings.append(f"Geomorphon notice: {err}")

        # 3D Interactive Web Viewer
        if selected[self.VIEWER_3D]:
            if not multi.isCanceled():
                multi.setCurrentStep(current_step)
                current_step += 1
                v3d_path = self._output_path(folder, prefix, "interactive_3d_terrain", "html")
                multi.pushInfo(self.tr("Generating Interactive 3D Web Terrain Viewer…"))
                try:
                    generate_3d_web_viewer(
                        dem_path=working_dem_path,
                        output_html_path=v3d_path,
                        title=f"{prefix.title()} 3D Interactive WebGIS Studio",
                        stream_vector_path=outputs.get(self.STREAMS_SMOOTH)
                        or outputs.get(self.STREAMS),
                        contour_vector_path=outputs.get(self.CONTOURS),
                        spot_peaks_path=outputs.get(self.SPOT_ELEVATIONS),
                        slope_path=outputs.get(self.SLOPE),
                        twi_path=outputs.get(self.TWI),
                        suitability_path=outputs.get(self.SUITABILITY),
                        hazard_path=outputs.get(self.LANDSLIDE_HAZARD),
                        band_number=band,
                        palette_key=palette_key,
                        grid_size=(256, 384, 512)[
                            min(max(0, web_3d_quality), 2)
                        ],
                    )
                    if os.path.exists(v3d_path):
                        outputs[self.VIEWER_3D] = v3d_path
                except Exception as err:
                    warnings.append(f"3D viewer notice: {err}")

        # Topographic Intelligence Summary Report
        if selected[self.INTELLIGENCE_REPORT]:
            if not multi.isCanceled():
                multi.setCurrentStep(current_step)
                current_step += 1
                intel_path = self._output_path(folder, prefix, "topographic_intelligence_report", "html")
                multi.pushInfo(self.tr("Compiling Topographic Intelligence Summary Report…"))
                try:
                    generate_intelligence_report(
                        dem_path=working_dem_path,
                        output_html_path=intel_path,
                        title=f"{prefix.title()} Topographic Intelligence Report",
                        slope_path=outputs.get(self.SLOPE),
                        aspect_path=outputs.get(self.ASPECT),
                        stream_vector_path=outputs.get(self.STREAMS_SMOOTH)
                        or outputs.get(self.STREAMS),
                        suitability_path=outputs.get(self.SUITABILITY),
                        hazard_path=outputs.get(self.LANDSLIDE_HAZARD),
                        twi_path=outputs.get(self.TWI),
                        geomorphon_path=outputs.get(self.GEOMORPHON),
                        spi_path=outputs.get(self.SPI),
                        sti_path=outputs.get(self.STI),
                        band_number=band,
                    )
                    if os.path.exists(intel_path):
                        outputs[self.INTELLIGENCE_REPORT] = intel_path
                except Exception as err:
                    warnings.append(f"Intelligence report notice: {err}")

        # GeoPackage bundle: every raster/vector product in one portable file
        if selected[self.BUNDLE]:
            if not multi.isCanceled():
                multi.setCurrentStep(current_step)
                current_step += 1
                bundle_path = self._output_path(folder, prefix, "bundle", "gpkg")
                multi.pushInfo(self.tr("Bundling all products into a single GeoPackage…"))
                try:
                    written = create_bundle(outputs, bundle_path, multi)
                    if written:
                        outputs[self.BUNDLE] = bundle_path
                        multi.pushInfo(
                            self.tr(
                                f"Bundle: {len(written)} layers → "
                                f"{os.path.basename(bundle_path)}"
                            )
                        )
                    else:
                        warnings.append(
                            "Bundle skipped: no raster or vector products to bundle."
                        )
                except Exception as err:
                    warnings.append(f"Bundle notice: {err}")

        # The manifest is intentionally last so it describes the final output
        # set, including hydrology and the bundle, plus any late warnings.
        multi.setCurrentStep(min(current_step, step_count - 1))
        report_path = self._output_path(folder, prefix, "report", "json")
        report = {
            "plugin": "Terrain Product Studio",
            "version": plugin_version(),
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "source": source.source(),
            "source_band": band,
            "source_crs": source.crs().authid() or source.crs().description(),
            "working_crs": working_crs.authid() or working_crs.description(),
            "elevation_unit": "m" if z_unit_index == 0 else "ft",
            "elevation_minimum": minimum,
            "elevation_maximum": maximum,
            "display_minimum_2pct": display_minimum,
            "display_maximum_98pct": display_maximum,
            "contour_interval": contour_interval,
            "index_contour_interval": contour_interval * index_multiplier,
            "palette": palette_key,
            "compression": compression,
            "pipeline": {
                "requested_products": sorted(pipeline_plan.requested_products),
                "effective_products": sorted(pipeline_plan.effective_products),
                "auto_enabled_products": sorted(
                    pipeline_plan.auto_enabled_products
                ),
                "hydrology_run": pipeline_plan.run_hydrology,
                "accumulation_source": pipeline_plan.accumulation_source,
                "twi_dependency_enabled": pipeline_plan.create_twi,
            },
            "hillshade": {
                "azimuth": azimuth,
                "altitude": altitude,
                "vertical_exaggeration": vertical_exaggeration,
                "zevenbergen_thorne": zevenbergen,
            },
            "provenance": build_run_provenance(
                source_info,
                source_path=source.source(),
                source_band=band,
                source_crs=source.crs().authid() or source.crs().description(),
                working_crs=working_crs.authid() or working_crs.description(),
                auto_reproject=auto_reproject,
                compression=compression,
                clip_extent=applied_clip_extent,
                smoothing_iterations=smoothing_index,
                simplify_tolerance=simplify_tolerance,
            ),
            "analytical_assumptions": analytical_assumptions(
                (key for key, enabled in selected.items() if enabled),
                accumulation_supplied=bool(accumulation_input),
                smoothing_iterations=smoothing_index,
            ),
            "warnings": warnings,
            "outputs": {
                key: value
                for key, value in outputs.items()
                if key != self.OUTPUT_FOLDER
            },
        }
        with open(report_path, "w", encoding="utf-8") as stream:
            json.dump(report, stream, ensure_ascii=False, indent=2)
        outputs[self.REPORT] = report_path

        multi.pushInfo(self.tr(f"Terrain package completed: {folder}"))
        return outputs
