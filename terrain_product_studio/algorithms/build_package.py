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
    QgsCoordinateReferenceSystem,
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
from ..core.math_utils import interpolate_color_stops, sanitize_prefix, unique_path
from ..core.presets import TERRAIN_PALETTES
from ..core.qgis_compat import all_raster_statistics_flag
from ..core.spot_elevations import extract_spot_elevations
from ..core.thematic_terrain import calculate_landslide_hazard, calculate_slope_suitability
from ..core.web_3d_viewer import generate_3d_web_viewer



def _number_type_double():
    """Return QgsProcessingParameterNumber Double type enum (Qt5 & Qt6 safe)."""
    try:
        return QgsProcessingParameterNumber.Type.Double
    except AttributeError:
        return QgsProcessingParameterNumber.Double


def _number_type_integer():
    """Return QgsProcessingParameterNumber Integer type enum (Qt5 & Qt6 safe)."""
    try:
        return QgsProcessingParameterNumber.Type.Integer
    except AttributeError:
        return QgsProcessingParameterNumber.Integer


class BuildTerrainPackageAlgorithm(QgsProcessingAlgorithm):
    INPUT = "INPUT"
    BAND = "BAND"
    OUTPUT_FOLDER = "OUTPUT_FOLDER"
    PREFIX = "PREFIX"
    Z_UNIT = "Z_UNIT"
    AUTO_REPROJECT = "AUTO_REPROJECT"
    PALETTE = "PALETTE"
    COMPRESSION = "COMPRESSION"
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
    CREATE_3D_VIEWER = "CREATE_3D_VIEWER"
    CREATE_INTELLIGENCE_REPORT = "CREATE_INTELLIGENCE_REPORT"
    CONTOUR_INTERVAL = "CONTOUR_INTERVAL"
    INDEX_MULTIPLIER = "INDEX_MULTIPLIER"

    WORKING_DEM = "WORKING_DEM"
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
    SPOT_ELEVATIONS = "SPOT_ELEVATIONS"
    SUITABILITY = "SUITABILITY"
    LANDSLIDE_HAZARD = "LANDSLIDE_HAZARD"
    LS_FACTOR = "LS_FACTOR"
    VIEWER_3D = "VIEWER_3D"
    INTELLIGENCE_REPORT = "INTELLIGENCE_REPORT"
    REPORT = "REPORT"

    _PALETTE_KEYS = tuple(TERRAIN_PALETTES.keys())
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
            "slope and relief calculations. Existing files are never overwritten. Hydrology is "
            "available as a separate provider algorithm and is chained automatically by the dock."
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
                "EXTENT",
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
                defaultValue=0,
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

        products = (
            (self.CREATE_COLOR_RELIEF, self.tr("Elevation color relief"), True),
            (self.CREATE_HILLSHADE, self.tr("Standard hillshade"), False),
            (self.CREATE_MULTI_HILLSHADE, self.tr("Multidirectional hillshade"), True),
            (self.CREATE_SLOPE, self.tr("Slope in degrees"), True),
            (self.CREATE_ASPECT, self.tr("Aspect"), True),
            (self.CREATE_TRI, self.tr("Terrain Ruggedness Index"), True),
            (self.CREATE_TPI, self.tr("Topographic Position Index"), True),
            (self.CREATE_ROUGHNESS, self.tr("Roughness"), True),
            (self.CREATE_PROFILE_CURVATURE, self.tr("Profile curvature"), False),
            (self.CREATE_PLANFORM_CURVATURE, self.tr("Planform curvature"), False),
            (self.CREATE_CONTOURS, self.tr("Contours"), True),
            (self.CREATE_SPOT_ELEVATIONS, self.tr("Spot elevation peaks"), True),
            (self.CREATE_SUITABILITY, self.tr("Slope construction suitability"), True),
            (self.CREATE_LANDSLIDE, self.tr("Landslide hazard & RUSLE LS factor"), True),
            (self.CREATE_3D_VIEWER, self.tr("Interactive 3D Web Terrain Viewer (HTML)"), True),
            (self.CREATE_INTELLIGENCE_REPORT, self.tr("Topographic Intelligence Report (HTML)"), True),
        )
        for name, label, default in products:
            self.addParameter(QgsProcessingParameterBoolean(name, label, defaultValue=default))

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

        self.addOutput(QgsProcessingOutputRasterLayer(self.WORKING_DEM, self.tr("Working DEM")))
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
        self.addOutput(QgsProcessingOutputVectorLayer(self.SPOT_ELEVATIONS, self.tr("Spot elevation peaks")))
        self.addOutput(QgsProcessingOutputRasterLayer(self.SUITABILITY, self.tr("Slope construction suitability")))
        self.addOutput(QgsProcessingOutputRasterLayer(self.LANDSLIDE_HAZARD, self.tr("Landslide hazard risk")))
        self.addOutput(QgsProcessingOutputRasterLayer(self.LS_FACTOR, self.tr("RUSLE LS factor")))
        self.addOutput(QgsProcessingOutputFile(self.VIEWER_3D, self.tr("Interactive 3D Web Viewer")))
        self.addOutput(QgsProcessingOutputFile(self.INTELLIGENCE_REPORT, self.tr("Topographic Intelligence Report")))
        self.addOutput(QgsProcessingOutputFile(self.REPORT, self.tr("Processing report")))


    @staticmethod
    def _available_parameters(algorithm_id):
        algorithm = QgsApplication.processingRegistry().algorithmById(algorithm_id)
        if algorithm is None:
            provider_name = "GRASS" if algorithm_id.startswith("grass:") else "GDAL"
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
        options = ["TILED=YES", "BIGTIFF=IF_SAFER"]
        if compression != "NONE":
            options.insert(0, f"COMPRESS={compression}")
        return "|".join(options)

    @staticmethod
    def _output_path(folder, prefix, suffix, extension):
        return unique_path(os.path.join(folder, f"{prefix}_{suffix}.{extension}"))

    @staticmethod
    def _write_color_table(path, minimum, maximum, palette):
        stops = interpolate_color_stops(minimum, maximum, palette)
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
                dist_meters = QgsUnitTypes.DistanceMeters
            factor = QgsUnitTypes.fromUnitToUnitFactor(crs.mapUnits(), dist_meters)
            if math.isfinite(factor) and factor > 0:
                return float(factor)
        except (AttributeError, TypeError, ValueError):
            pass
        return 1.0

    def processAlgorithm(self, parameters, context, feedback):
        source = self.parameterAsRasterLayer(parameters, self.INPUT, context)
        band = self.parameterAsInt(parameters, self.BAND, context)
        folder = self.parameterAsString(parameters, self.OUTPUT_FOLDER, context)
        prefix = sanitize_prefix(self.parameterAsString(parameters, self.PREFIX, context))
        z_unit_index = self.parameterAsEnum(parameters, self.Z_UNIT, context)
        auto_reproject = self.parameterAsBool(parameters, self.AUTO_REPROJECT, context)
        palette_index = self.parameterAsEnum(parameters, self.PALETTE, context)
        compression_index = self.parameterAsEnum(parameters, self.COMPRESSION, context)
        vertical_exaggeration = self.parameterAsDouble(
            parameters, self.VERTICAL_EXAGGERATION, context
        )
        azimuth = self.parameterAsDouble(parameters, self.AZIMUTH, context)
        altitude = self.parameterAsDouble(parameters, self.ALTITUDE, context)
        zevenbergen = self.parameterAsBool(parameters, self.ZEVENBERGEN, context)
        contour_interval = self.parameterAsDouble(parameters, self.CONTOUR_INTERVAL, context)
        index_multiplier = self.parameterAsInt(parameters, self.INDEX_MULTIPLIER, context)

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
            self.COLOR_RELIEF: self.parameterAsBool(parameters, self.CREATE_COLOR_RELIEF, context),
            self.HILLSHADE: self.parameterAsBool(parameters, self.CREATE_HILLSHADE, context),
            self.MULTI_HILLSHADE: self.parameterAsBool(
                parameters, self.CREATE_MULTI_HILLSHADE, context
            ),
            self.SLOPE: self.parameterAsBool(parameters, self.CREATE_SLOPE, context),
            self.ASPECT: self.parameterAsBool(parameters, self.CREATE_ASPECT, context),
            self.TRI: self.parameterAsBool(parameters, self.CREATE_TRI, context),
            self.TPI: self.parameterAsBool(parameters, self.CREATE_TPI, context),
            self.ROUGHNESS: self.parameterAsBool(parameters, self.CREATE_ROUGHNESS, context),
            self.PROFILE_CURVATURE: self.parameterAsBool(parameters, self.CREATE_PROFILE_CURVATURE, context),
            self.PLANFORM_CURVATURE: self.parameterAsBool(parameters, self.CREATE_PLANFORM_CURVATURE, context),
            self.CONTOURS: self.parameterAsBool(parameters, self.CREATE_CONTOURS, context),
            self.SPOT_ELEVATIONS: self.parameterAsBool(parameters, self.CREATE_SPOT_ELEVATIONS, context),
            self.SUITABILITY: self.parameterAsBool(parameters, self.CREATE_SUITABILITY, context),
            self.LANDSLIDE_HAZARD: self.parameterAsBool(parameters, self.CREATE_LANDSLIDE, context),
            self.VIEWER_3D: self.parameterAsBool(parameters, self.CREATE_3D_VIEWER, context),
            self.INTELLIGENCE_REPORT: self.parameterAsBool(parameters, self.CREATE_INTELLIGENCE_REPORT, context),
        }
        if not any(selected.values()):
            raise QgsProcessingException(self.tr("Select at least one terrain product."))

        step_count = sum(selected.values()) + 2
        multi = QgsProcessingMultiStepFeedback(step_count, feedback)
        current_step = 0
        outputs = {self.OUTPUT_FOLDER: folder}
        warnings = []

        source_info = inspect_dem_layer(source, band, sum(selected.values()))
        warnings.extend(source_info["warnings"])
        working_dem = source
        working_crs = source.crs()

        if source.crs().isGeographic():
            if not auto_reproject:
                raise QgsProcessingException(
                    self.tr(
                        "The DEM uses angular coordinates. Enable automatic reprojection or "
                        "reproject it to a suitable metric CRS before running terrain analysis."
                    )
                )
            target_authid = source_info["suggested_working_crs"]
            target_crs = QgsCoordinateReferenceSystem(target_authid)
            if not target_crs.isValid():
                raise QgsProcessingException(self.tr("Could not determine a valid working CRS."))
            multi.setCurrentStep(current_step)
            current_step += 1
            multi.pushInfo(self.tr(f"Reprojecting DEM to {target_authid} using bilinear resampling…"))
            projected_path = self._output_path(folder, prefix, "working_dem", "tif")
            warp = self._run_child(
                "gdal:warpreproject",
                {
                    "INPUT": source,
                    "SOURCE_CRS": source.crs(),
                    "TARGET_CRS": target_crs,
                    "RESAMPLING": 1,
                    "NODATA": None,
                    "TARGET_RESOLUTION": None,
                    "MULTITHREADING": True,
                    "CREATION_OPTIONS": creation_options,
                    "OPTIONS": creation_options,
                    "EXTRA": "",
                    "DATA_TYPE": 0,
                    "OUTPUT": projected_path,
                },
                context,
                multi,
            )
            working_dem = warp["OUTPUT"]
            working_crs = target_crs
            outputs[self.WORKING_DEM] = working_dem
        else:
            multi.setCurrentStep(current_step)
            current_step += 1
            multi.pushInfo(self.tr("Input DEM already has a projected CRS; no working copy was required."))

        if multi.isCanceled():
            return outputs

        # Optional user boundary extent clipping
        extent_param = self.parameterAsExtent(parameters, "EXTENT", context)
        if extent_param is not None and not extent_param.isNull() and not extent_param.isEmpty():
            clipped_path = self._output_path(folder, prefix, "clipped_roi", "tif")
            multi.pushInfo(self.tr(f"Clipping DEM to selected ROI extent…"))
            try:
                clip_res = self._run_child(
                    "gdal:cliprasterbyextent",
                    {
                        "INPUT": working_dem,
                        "PROJWIN": extent_param,
                        "NODATA": None,
                        "OPTIONS": creation_options,
                        "DATA_TYPE": 0,
                        "OUTPUT": clipped_path,
                    },
                    context=context,
                    feedback=multi,
                )
                if os.path.exists(clipped_path):
                    working_dem = clipped_path
            except Exception as e:
                warnings.append(f"ROI Extent clip notice: {e}")

        working_layer = source
        if isinstance(working_dem, str):
            working_layer = QgsRasterLayer(working_dem, f"{prefix}_working_dem")
            if not working_layer.isValid():
                raise QgsProcessingException(self.tr("The working DEM could not be opened."))

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
                TERRAIN_PALETTES[palette_key]["stops"],
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

        if selected[self.SPOT_ELEVATIONS]:
            if not multi.isCanceled():
                multi.setCurrentStep(current_step)
                current_step += 1
                spot_path = self._output_path(folder, prefix, "spot_elevations", "gpkg")
                multi.pushInfo(self.tr("Extracting spot elevation peaks…"))
                try:
                    dem_path = working_dem if isinstance(working_dem, str) else source.source().split("|")[0]
                    count = extract_spot_elevations(dem_path, band, spot_path)
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

        # Landslide Hazard & RUSLE LS Factor
        if selected[self.LANDSLIDE_HAZARD] and outputs.get(self.SLOPE):
            if not multi.isCanceled():
                multi.setCurrentStep(current_step)
                current_step += 1
                hazard_path = self._output_path(folder, prefix, "landslide_hazard", "tif")
                ls_path = self._output_path(folder, prefix, "rusle_ls_factor", "tif")
                multi.pushInfo(self.tr("Calculating landslide hazard and RUSLE LS factor…"))
                try:
                    calculate_landslide_hazard(outputs[self.SLOPE], outputs[self.SLOPE], hazard_path, ls_path)
                    if os.path.exists(hazard_path):
                        outputs[self.LANDSLIDE_HAZARD] = hazard_path
                    if os.path.exists(ls_path):
                        outputs[self.LS_FACTOR] = ls_path
                except Exception as err:
                    warnings.append(f"Landslide hazard notice: {err}")

        working_dem_path = working_dem if isinstance(working_dem, str) else source.source().split("|")[0]

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
                        contour_vector_path=outputs.get(self.CONTOURS),
                        spot_peaks_path=outputs.get(self.SPOT_ELEVATIONS),
                        slope_path=outputs.get(self.SLOPE),
                        suitability_path=outputs.get(self.SUITABILITY),
                        hazard_path=outputs.get(self.LANDSLIDE_HAZARD),
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
                        suitability_path=outputs.get(self.SUITABILITY),
                        hazard_path=outputs.get(self.LANDSLIDE_HAZARD),
                    )
                    if os.path.exists(intel_path):
                        outputs[self.INTELLIGENCE_REPORT] = intel_path
                except Exception as err:
                    warnings.append(f"Intelligence report notice: {err}")

        multi.setCurrentStep(min(current_step, step_count - 1))
        report_path = self._output_path(folder, prefix, "report", "json")
        report = {
            "plugin": "Terrain Product Studio",
            "version": "0.2.0",
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
            "hillshade": {
                "azimuth": azimuth,
                "altitude": altitude,
                "vertical_exaggeration": vertical_exaggeration,
                "zevenbergen_thorne": zevenbergen,
            },
            "warnings": warnings,
            "outputs": {key: value for key, value in outputs.items() if key != self.OUTPUT_FOLDER},
        }
        with open(report_path, "w", encoding="utf-8") as stream:
            json.dump(report, stream, ensure_ascii=False, indent=2)
        outputs[self.REPORT] = report_path
        multi.pushInfo(self.tr(f"Terrain package completed: {folder}"))
        return outputs
