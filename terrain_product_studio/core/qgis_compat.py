"""Small compatibility helpers spanning supported QGIS 3 and QGIS 4 APIs."""

from __future__ import annotations

from qgis.core import Qgis, QgsLayoutItemMapGrid, QgsRasterBandStats


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
        return getattr(QgsRasterBandStats, "All")


def map_grid_line_border_style():
    """Return the line-border grid-frame enum on QGIS 3 and QGIS 4.

    QGIS 4 moved ``QgsLayoutItemMapGrid.FrameStyle`` into
    ``Qgis.MapGridFrameStyle``. Keeping that difference here prevents layout
    code from having version branches scattered through the composer.
    """

    try:
        return Qgis.MapGridFrameStyle.LineBorder
    except AttributeError:
        pass
    try:
        return QgsLayoutItemMapGrid.FrameStyle.LineBorder
    except AttributeError:
        return getattr(QgsLayoutItemMapGrid, "LineBorder")
