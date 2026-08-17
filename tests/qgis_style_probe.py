"""Manual qgis_process probe for generated layer renderers and grouping."""

from __future__ import annotations

import os
import sys
import traceback

from qgis.core import QgsProcessingAlgorithm, QgsProcessingException, QgsProject


class TerrainStudioStyleProbe(QgsProcessingAlgorithm):
    def name(self):
        return "terrainstudiostyleprobe"

    def displayName(self):
        return "Terrain Studio style probe"

    def group(self):
        return "Tests"

    def groupId(self):
        return "tests"

    def createInstance(self):
        return TerrainStudioStyleProbe()

    def initAlgorithm(self, config=None):
        pass

    def processAlgorithm(self, parameters, context, feedback):
        workspace = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        sys.path.insert(0, workspace)
        output = "/private/tmp/terrain-studio-integration/output"
        results = {
            "COLOR_RELIEF": os.path.join(output, "smoke_projected2_color_relief.tif"),
            "MULTI_HILLSHADE": os.path.join(
                output, "smoke_projected2_hillshade_multidirectional.tif"
            ),
            "SLOPE": os.path.join(output, "smoke_projected2_slope_deg.tif"),
            "ASPECT": os.path.join(output, "smoke_projected2_aspect.tif"),
            "TRI": os.path.join(output, "smoke_projected2_tri.tif"),
            "TPI": os.path.join(output, "smoke_projected2_tpi.tif"),
            "ROUGHNESS": os.path.join(output, "smoke_projected2_roughness.tif"),
            "CONTOURS": os.path.join(output, "smoke_projected2_contours.gpkg"),
        }
        try:
            from terrain_product_studio.core.layers import add_terrain_results

            loaded, failed = add_terrain_results(results, 5.0, 5, "m")
            if loaded != len(results) or failed:
                raise RuntimeError(f"loaded={loaded}, failed={failed}")
            project_path = "/private/tmp/terrain-studio-integration/style_probe.qgz"
            if not QgsProject.instance().write(project_path):
                raise RuntimeError("Could not write style probe project")
            feedback.pushInfo(f"Styled {loaded} layers and wrote {project_path}")
            return {}
        except Exception as error:
            raise QgsProcessingException(traceback.format_exc()) from error
