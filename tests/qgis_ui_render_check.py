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

from qgis.PyQt.QtCore import QRect
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
