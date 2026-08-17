"""Small compatibility helpers spanning supported QGIS 3 and QGIS 4 APIs."""

from __future__ import annotations

from qgis.core import Qgis, QgsRasterBandStats


def all_raster_statistics_flag():
    """Return the non-deprecated all-statistics enum where available."""

    try:
        return Qgis.RasterBandStatistic.All
    except AttributeError:
        pass
    # Qt6 scoped enum: QgsRasterBandStats.Stats.All
    try:
        return QgsRasterBandStats.Stats.All
    except AttributeError:
        return QgsRasterBandStats.All
