"""Object-oriented DEM reprojection and extent-clipping service."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from osgeo import gdal
from qgis.core import QgsCoordinateReferenceSystem, QgsProcessingException, QgsRasterLayer


@dataclass
class PreparedDem:
    """Stable hand-off from preprocessing to every downstream product builder."""

    processing_input: Any
    layer: QgsRasterLayer
    crs: QgsCoordinateReferenceSystem
    applied_clip_extent: Optional[List[float]] = None
    output_paths: Dict[str, str] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)


class DemPreprocessor:
    """Prepare one projected/clipped DEM without duplicating workflow logic."""

    def __init__(
        self,
        *,
        run_child: Callable,
        output_path: Callable,
        extent_resolver: Callable,
        advance: Callable[[str], None],
        feedback,
        creation_options: str,
        prefix: str,
        translate: Callable[[str], str] = lambda value: value,
    ):
        self.run_child = run_child
        self.output_path = output_path
        self.extent_resolver = extent_resolver
        self.advance = advance
        self.feedback = feedback
        self.creation_options = creation_options
        self.prefix = prefix
        self.tr = translate

    @staticmethod
    def _clip_coordinates(rect):
        return [
            rect.xMinimum(),
            rect.yMinimum(),
            rect.xMaximum(),
            rect.yMaximum(),
        ]

    def prepare(self, source, *, auto_reproject: bool, source_info) -> PreparedDem:
        processing_input = source
        working_crs = source.crs()
        output_paths = {}
        warnings = []
        applied_clip_extent = None

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
                raise QgsProcessingException(
                    self.tr("Could not determine a valid working CRS.")
                )
            self.advance(
                self.tr(
                    f"Reprojecting DEM to {target_authid} using bilinear resampling…"
                )
            )
            projected_path = self.output_path("working_dem", "tif")
            warp = self.run_child(
                "gdal:warpreproject",
                {
                    "INPUT": source,
                    "SOURCE_CRS": source.crs(),
                    "TARGET_CRS": target_crs,
                    "RESAMPLING": 1,
                    "NODATA": None,
                    "TARGET_RESOLUTION": None,
                    "MULTITHREADING": True,
                    "CREATION_OPTIONS": self.creation_options,
                    "OPTIONS": self.creation_options,
                    "EXTRA": "",
                    "DATA_TYPE": 0,
                    "OUTPUT": projected_path,
                },
            )
            processing_input = warp["OUTPUT"]
            working_crs = target_crs
            output_paths["WORKING_DEM"] = processing_input
        else:
            self.advance(
                self.tr(
                    "Input DEM already has a projected CRS; no working copy was required."
                )
            )

        if self.feedback.isCanceled():
            layer = source
            return PreparedDem(
                processing_input, layer, working_crs, None, output_paths, warnings
            )

        extent = self.extent_resolver(working_crs)
        if extent is not None and not extent.isNull() and not extent.isEmpty():
            current_layer = (
                QgsRasterLayer(processing_input, "terrain_preprocess")
                if isinstance(processing_input, str)
                else source
            )
            if current_layer.isValid():
                clipped_rect = extent.intersect(current_layer.extent())
                if (
                    not clipped_rect.isNull()
                    and not clipped_rect.isEmpty()
                    and clipped_rect.width() > 0
                    and clipped_rect.height() > 0
                ):
                    processing_input, clip_warnings = self._clip(
                        processing_input, source, clipped_rect
                    )
                    warnings.extend(clip_warnings)
                    if isinstance(processing_input, str) and os.path.exists(
                        processing_input
                    ):
                        output_paths["WORKING_DEM"] = processing_input
                        applied_clip_extent = self._clip_coordinates(clipped_rect)

        layer = source
        if isinstance(processing_input, str):
            layer = QgsRasterLayer(processing_input, f"{self.prefix}_working_dem")
            if not layer.isValid():
                raise QgsProcessingException(
                    self.tr("The working DEM could not be opened.")
                )

        return PreparedDem(
            processing_input=processing_input,
            layer=layer,
            crs=working_crs,
            applied_clip_extent=applied_clip_extent,
            output_paths=output_paths,
            warnings=warnings,
        )

    def create_portable_copy(self, input_path, output_path, band_number):
        """Copy the canonical DEM into the package as a tiled GeoTIFF.

        Keeping all GDAL translation in the preprocessing service avoids
        leaking raster-driver details into the master workflow and gives the
        portable-copy path the same creation options as clipping/reprojection.
        """

        try:
            options = gdal.TranslateOptions(
                format="GTiff",
                bandList=[int(band_number)],
                creationOptions=self.creation_options.split("|"),
            )
            dataset = gdal.Translate(output_path, input_path, options=options)
        except Exception as error:
            raise QgsProcessingException(
                self.tr("Could not create the portable canonical DEM: ")
                + str(error)
            ) from error
        if dataset is None:
            raise QgsProcessingException(
                self.tr("Could not create the portable canonical DEM.")
            )
        dataset = None
        if not os.path.exists(output_path):
            raise QgsProcessingException(
                self.tr("Portable canonical DEM was not written to disk.")
            )
        return output_path

    def _clip(self, processing_input, source, clipped_rect):
        warnings = []
        clipped_path = self.output_path("clipped_roi", "tif")
        self.feedback.pushInfo(
            self.tr(
                "Clipping DEM to ROI extent "
                f"({clipped_rect.xMinimum():.1f}, {clipped_rect.yMinimum():.1f}) → "
                f"({clipped_rect.xMaximum():.1f}, {clipped_rect.yMaximum():.1f})…"
            )
        )
        input_path = (
            processing_input
            if isinstance(processing_input, str)
            else source.source().split("|")[0]
        )
        proj_win = [
            clipped_rect.xMinimum(),
            clipped_rect.yMaximum(),
            clipped_rect.xMaximum(),
            clipped_rect.yMinimum(),
        ]

        try:
            options = gdal.TranslateOptions(
                projWin=proj_win,
                creationOptions=self.creation_options.split("|"),
            )
            dataset = gdal.Translate(clipped_path, input_path, options=options)
            if dataset is not None:
                dataset = None
                if os.path.exists(clipped_path):
                    self.feedback.pushInfo(
                        self.tr("Successfully clipped DEM to selected ROI extent.")
                    )
                    return clipped_path, warnings
        except Exception as error:
            warnings.append(f"GDAL Translate ROI clip notice: {error}")

        try:
            self.run_child(
                "gdal:cliprasterbyextent",
                {
                    "INPUT": processing_input,
                    "PROJWIN": clipped_rect,
                    "NODATA": None,
                    "OPTIONS": self.creation_options,
                    "DATA_TYPE": 0,
                    "OUTPUT": clipped_path,
                },
            )
            if os.path.exists(clipped_path):
                return clipped_path, warnings
        except Exception as error:
            warnings.append(f"ROI Extent clip notice: {error}")
        return processing_input, warnings
