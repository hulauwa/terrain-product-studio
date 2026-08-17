"""QGIS startup script which verifies the real plugin GUI lifecycle."""

from __future__ import annotations

import json
import os
import traceback

from qgis.PyQt.QtCore import QCoreApplication, QTimer


MARKER = "/private/tmp/terrain-studio-gui-probe.json"
SCREENSHOT = "/private/tmp/terrain-studio-gui-probe.png"


def run_probe():
    result = {"success": False}
    try:
        import qgis.utils

        captured_errors = []
        original_show_exception = qgis.utils.showException

        def capture_exception(error_type, error_value, error_tb, message, *args, **kwargs):
            captured_errors.append(
                message + "\n" + "".join(traceback.format_exception(error_type, error_value, error_tb))
            )
            return original_show_exception(
                error_type, error_value, error_tb, message, *args, **kwargs
            )

        qgis.utils.showException = capture_exception
        loaded = True
        if "terrain_product_studio" not in __import__("sys").modules:
            loaded = bool(qgis.utils.loadPlugin("terrain_product_studio"))
        started = True
        if "terrain_product_studio" not in qgis.utils.plugins:
            started = bool(qgis.utils.startPlugin("terrain_product_studio"))
        result["load_plugin"] = loaded
        result["start_plugin"] = started
        result["captured_errors"] = captured_errors
        plugin = qgis.utils.plugins.get("terrain_product_studio")
        if plugin is None:
            raise RuntimeError("Plugin instance was not registered by QGIS")
        plugin.show_dock()
        dock = plugin.dock
        if dock is None:
            raise RuntimeError("Plugin did not create its dock")
        result.update(
            {
                "success": True,
                "dock_visible": dock.isVisible(),
                "dock_title": dock.windowTitle(),
                "product_count": len(dock.products),
                "provider_available": bool(
                    QgsApplication.processingRegistry().algorithmById(
                        "terrainstudio:buildterrainpackage"
                    )
                ),
                "qgis_version": Qgis.QGIS_VERSION,
            }
        )
        qgis.utils.iface.mainWindow().grab().save(SCREENSHOT)
        result["screenshot"] = SCREENSHOT
    except Exception:
        result["traceback"] = traceback.format_exc()
    finally:
        with open(MARKER, "w", encoding="utf-8") as stream:
            json.dump(result, stream, ensure_ascii=False, indent=2)
        QTimer.singleShot(750, QCoreApplication.quit)


from qgis.core import Qgis, QgsApplication

QTimer.singleShot(1500, run_probe)
