"""Render the dock offscreen and verify the Run button is always reachable.

Run with QGIS bundled Python (set QGIS_PREFIX_PATH if QGIS is not in /Applications):
  QGIS_PREFIX_PATH=/Applications/QGIS.app/Contents/MacOS \\
    /Applications/QGIS.app/Contents/MacOS/bin/python3 tests/qgis_ui_render_check.py
"""

from __future__ import annotations

import os
import sys
import time

workspace = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, workspace)

from qgis.core import QgsApplication

prefix = os.environ.get("QGIS_PREFIX_PATH", "/Applications/QGIS.app/Contents/MacOS")
QgsApplication.setPrefixPath(prefix, True)
app = QgsApplication([], False)
app.initQgis()
app.setQuitOnLastWindowClosed(False)

from qgis.PyQt.QtWidgets import QScrollArea

from terrain_product_studio.dock import TerrainStudioDock

start = time.time()
dock = TerrainStudioDock(None)
elapsed = (time.time() - start) * 1000
print(f"dock construction: {elapsed:.0f} ms")

failures = []

scroll = dock.widget()
if not isinstance(scroll, QScrollArea):
    failures.append("dock.widget() is not a QScrollArea")
if not scroll.widgetResizable():
    failures.append("scroll area not widget-resizable")

# Simulate a small docked area: shorter than the full content height.
for height in (680, 520, 460):
    dock.resize(460, height)
    dock.show()
    app.processEvents()
    viewport_height = scroll.viewport().height()
    content_height = scroll.widget().sizeHint().height()
    run_bottom = dock.run_button.mapTo(scroll.widget(), dock.run_button.rect().bottomLeft()).y()
    reachable = run_bottom <= content_height and (
        content_height <= viewport_height or scroll.verticalScrollBar().maximum() >= run_bottom - viewport_height
    )
    print(
        f"height={height}: viewport={viewport_height} content={content_height} "
        f"run_button_bottom={run_bottom} max_scroll={scroll.verticalScrollBar().maximum()} "
        f"reachable={reachable}"
    )
    if not reachable:
        failures.append(f"Run button not reachable at dock height {height}")
    if run_bottom > content_height:
        failures.append("Run button bottom exceeds scroll content")

# M4: industry presets tick the right products
expected_presets = 5  # Custom + 4 industries
if dock.industry_combo.count() != expected_presets:
    failures.append(f"industry_combo has {dock.industry_combo.count()} items, expected {expected_presets}")
if dock.industry_combo.currentData():
    failures.append("industry_combo should default to Custom selection")
# Disaster preset: landslide + multi-hazard + hydrology (produces TWI) + 3D viewer
disaster_index = dock.industry_combo.findData("disaster")
if disaster_index < 0:
    failures.append("disaster industry preset missing")
else:
    dock.industry_combo.setCurrentIndex(disaster_index)
    for key in ("CREATE_LANDSLIDE", "CREATE_MULTIHAZARD", "CREATE_3D_VIEWER"):
        if not dock.products[key].isChecked():
            failures.append(f"disaster preset did not tick {key}")
    if not dock.hydrology_check.isChecked():
        failures.append("disaster preset did not tick hydrology")
    if any(cb.isChecked() for key, cb in dock.products.items() if key not in
           ("CREATE_LANDSLIDE", "CREATE_MULTIHAZARD", "CREATE_3D_VIEWER")):
        failures.append("disaster preset left unexpected products ticked")
    dock.industry_combo.setCurrentIndex(0)  # back to custom

# M4: 3D export controls present
for attr in ("stl_button", "obj_button", "z_scale_spin", "base_thickness_spin"):
    if not hasattr(dock, attr):
        failures.append(f"missing 3D export control {attr}")

# M4: recent-runs list loads without crashing
dock._reload_history()
if dock.history_list.count() < 0:
    failures.append("history_list count negative")

# Screenshots at representative sizes for visual inspection
os.makedirs(os.path.join(workspace, "dist"), exist_ok=True)
for height, name in ((680, "dock_full"), (520, "dock_compact")):
    dock.resize(460, height)
    dock.show()
    app.processEvents()
    pix = dock.grab()
    out = os.path.join(workspace, "dist", f"{name}.png")
    pix.save(out)
    print(f"screenshot: {out} ({pix.width()}x{pix.height()})")

dock.close()
dock.deleteLater()

if failures:
    print("FAILURES:")
    for f in failures:
        print(" -", f)
    sys.exit(1)
print("ALL UI CHECKS PASSED")
