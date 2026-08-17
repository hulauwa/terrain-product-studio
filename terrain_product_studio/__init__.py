"""QGIS entry point for Terrain Product Studio."""


def classFactory(iface):
    from .plugin import TerrainProductStudioPlugin

    return TerrainProductStudioPlugin(iface)
