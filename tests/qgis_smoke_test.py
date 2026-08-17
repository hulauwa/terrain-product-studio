"""Runtime smoke test; execute with the Python bundled inside QGIS."""

from __future__ import annotations

import os
import sys


def main():
    from qgis.core import QgsApplication

    workspace = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, workspace)

    prefix = os.environ.get("QGIS_PREFIX_PATH", "")
    if prefix:
        QgsApplication.setPrefixPath(prefix, True)
    application = QgsApplication([], False)
    application.initQgis()
    try:
        from processing.core.Processing import Processing

        Processing.initialize()
        from terrain_product_studio.provider import TerrainStudioProvider

        provider = TerrainStudioProvider()
        if not QgsApplication.processingRegistry().addProvider(provider):
            raise RuntimeError("Terrain Studio provider registration returned False")
        algorithms = {
            algorithm.id(): sorted(parameter.name() for parameter in algorithm.parameterDefinitions())
            for algorithm in provider.algorithms()
        }
        expected = {
            "terrainstudio:inspectdem",
            "terrainstudio:buildterrainpackage",
            "terrainstudio:buildhydrology",
        }
        if set(algorithms) != expected:
            raise RuntimeError(f"Unexpected algorithms: {sorted(algorithms)}")

        required_gdal = {
            "gdal:warpreproject",
            "gdal:colorrelief",
            "gdal:hillshade",
            "gdal:slope",
            "gdal:aspect",
            "gdal:triterrainruggednessindex",
            "gdal:tpitopographicpositionindex",
            "gdal:roughness",
            "gdal:contour",
        }
        available = {
            algorithm.id() for algorithm in QgsApplication.processingRegistry().algorithms()
        }
        missing = sorted(required_gdal - available)
        if missing:
            raise RuntimeError(f"Missing required GDAL algorithms: {missing}")
        print("QGIS_RUNTIME_OK")
        for algorithm_id, parameters in sorted(algorithms.items()):
            print(f"{algorithm_id}: {', '.join(parameters)}")
        QgsApplication.processingRegistry().removeProvider(provider)
    finally:
        application.exitQgis()


if __name__ == "__main__":
    main()
