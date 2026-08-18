"""JSON run history stored next to the QGIS settings directory.

Each entry records one successful package run (timestamp, output folder,
prefix, checked products and the generated report/bundle paths) so the
Inspect tab can list recent runs and reopen their outputs.
"""

from __future__ import annotations

import json
import os

from qgis.core import QgsApplication

_MAX_ENTRIES = 20
_HISTORY_FILENAME = "terrain_product_studio_history.json"


def history_path():
    """Absolute path of the history file (inside QGIS settings)."""
    return os.path.join(QgsApplication.qgisSettingsDirPath(), _HISTORY_FILENAME)


def load_history():
    """Return the list of recorded entries (oldest last); [] on any error."""
    try:
        with open(history_path(), encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, list) else []
    except (OSError, ValueError):
        return []


def append_history(entry):
    """Prepend one entry, capped at _MAX_ENTRIES. Best-effort: failures are
    silent so a locked settings directory never breaks the run."""
    entries = load_history()
    entries.insert(0, entry)
    del entries[_MAX_ENTRIES:]
    try:
        with open(history_path(), "w", encoding="utf-8") as handle:
            json.dump(entries, handle, ensure_ascii=False, indent=1)
    except OSError:
        pass
