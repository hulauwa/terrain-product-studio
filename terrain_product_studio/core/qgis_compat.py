"""Small compatibility helpers spanning supported QGIS 3 and QGIS 4 APIs."""

from __future__ import annotations

from qgis.PyQt.QtGui import QFontDatabase
from qgis.core import Qgis, QgsLayoutItemMapGrid, QgsRasterBandStats

try:
    from qgis.core import QgsLegendStyle
except ImportError:  # QGIS 4 may remove the legacy enum container
    QgsLegendStyle = None


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


def raster_band_statistics(provider, band, extent, sample_size=0):
    """Return all band statistics without selecting QGIS' deprecated overload.

    QGIS 3.40+ exposes both an old ``int`` overload and a new
    ``Qgis.RasterBandStatistic`` overload. Some SIP builds still route an
    explicitly supplied ``RasterBandStatistic.All`` value to the old overload
    and emit a deprecation warning. Omitting ``stats`` selects the new overload
    and uses its typed ``All`` default. The positional fallback retains support
    for older QGIS 3 bindings.
    """

    try:
        return provider.bandStatistics(
            bandNo=int(band),
            extent=extent,
            sampleSize=int(sample_size),
        )
    except TypeError:
        return provider.bandStatistics(
            int(band),
            all_raster_statistics_flag(),
            extent,
            int(sample_size),
        )


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


def legend_component(name):
    """Resolve Title/Group/SymbolLabel across QGIS 3 and QGIS 4."""

    try:
        return getattr(Qgis.LegendComponent, name)
    except AttributeError:
        pass
    try:
        return getattr(QgsLegendStyle.Style, name)
    except AttributeError:
        if QgsLegendStyle is None:
            raise
        return getattr(QgsLegendStyle, name)


def font_families():
    """Return installed font families on both Qt 5 and Qt 6.

    Qt 6 exposes ``QFontDatabase.families`` as a static method and no longer
    accepts the zero-argument ``QFontDatabase()`` construction used by Qt 5.
    QGIS 4 therefore needs the class call, while older QGIS builds may still
    require an instance.
    """

    try:
        return list(QFontDatabase.families())
    except TypeError:  # Qt 5 bindings which expose only the instance method
        return list(QFontDatabase().families())
