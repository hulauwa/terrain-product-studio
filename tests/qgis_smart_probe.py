"""Runtime probe: DebouncedDemInspector + compute_smart_defaults under QGIS.

Execute with the Python bundled inside QGIS:

    /Applications/QGIS.app/Contents/MacOS/QGIS --nocrashdialog \
        --headless --noplugins python3 tests/qgis_smart_probe.py

Asserts:
- the async QgsTask inspection emits ``inspected`` with generation 1
- compute_smart_defaults produces the expected suggestion set
- mark_fresh (manual inspect) bumps the generation and wins over stale results
"""

from __future__ import annotations

import math
import os
import struct
import sys
import tempfile
import time

WORKSPACE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, WORKSPACE)

from osgeo import gdal, osr  # noqa: E402


def make_dem(folder, name="dem.tif", size=64, res=10.0):
    path = os.path.join(folder, name)
    driver = gdal.GetDriverByName("GTiff")
    ds = driver.Create(path, size, size, 1, gdal.GDT_Float32)
    ds.SetGeoTransform((500000.0, res, 0.0, 2450000.0, 0.0, -res))
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(32648)
    ds.SetProjection(srs.ExportToWkt())
    band = ds.GetRasterBand(1)
    for row in range(size):
        scan = [
            100.0 * math.sin(math.pi * col / float(size)) + 20.0 * row / float(size) + 80.0
            for col in range(size)
        ]
        band.WriteRaster(0, row, size, 1, struct.pack("<%df" % size, *scan))
    band.FlushCache()
    ds = None
    return path


def pump_until(predicate, timeout_s=15.0):
    """Run the Qt event loop (feeding QgsTask callbacks) until predicate."""
    from qgis.core import QgsApplication

    deadline = time.time() + timeout_s
    while time.time() < deadline:
        QgsApplication.processEvents()
        if predicate():
            return True
        time.sleep(0.05)
    return False


def main():
    from qgis.core import QgsApplication

    prefix = os.environ.get("QGIS_PREFIX_PATH", "")
    if prefix:
        QgsApplication.setPrefixPath(prefix, True)
    application = QgsApplication([], False)
    application.initQgis()

    from qgis.core import QgsRasterLayer  # noqa: E402
    from terrain_product_studio.core.smart_defaults import compute_smart_defaults  # noqa: E402
    from terrain_product_studio.ui.smart_defaults import DebouncedDemInspector  # noqa: E402

    failures = []
    with tempfile.TemporaryDirectory() as folder:
        dem = make_dem(folder)
        layer = QgsRasterLayer(dem, "probe dem")
        if not layer.isValid():
            failures.append("DEM layer did not open")
            return _report(failures)

        inspector = DebouncedDemInspector()
        results = []
        inspector.inspected.connect(
            lambda info, generation: results.append((info, generation))
        )
        failures_list = []
        inspector.failed.connect(
            lambda message, generation: failures_list.append((message, generation))
        )

        inspector.set_inputs(layer, 1)
        if not pump_until(lambda: results or failures_list):
            failures.append("async inspection never emitted")
        elif failures_list:
            failures.append(f"async inspection failed: {failures_list[0][0]}")
        else:
            info, generation = results[-1]
            if generation != 1:
                failures.append(f"generation != 1: {generation}")
            if info.get("relief_m") is None or info.get("extent_width_m") is None:
                failures.append("info missing relief_m/extent_width_m")
            suggestions = compute_smart_defaults(info)
            keys = [suggestion.key for suggestion in suggestions]
            if "contour_interval" not in keys or "stream_threshold" not in keys:
                failures.append(f"unexpected suggestion set: {keys}")

            # Manual inspect bumps the generation; a stale result (emitted
            # with the old generation) must be ignored by the dock sink.
            inspector.mark_fresh(info)
            stale = (info, 0)
            # simulate the dock sink guard directly
            accepted = stale[1] == inspector.generation
            if accepted:
                failures.append("stale generation result would be accepted")
            if inspector.generation != 2:
                failures.append(f"generation not bumped: {inspector.generation}")

    if failures:
        return _report(failures)
    print("SMART PROBE OK")
    return 0


def _report(failures):
    print("SMART PROBE FAILURES:")
    for failure in failures:
        print(" -", failure)
    return 1


if __name__ == "__main__":
    sys.exit(main())
