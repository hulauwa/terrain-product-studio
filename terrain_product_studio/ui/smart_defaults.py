"""Debounced, asynchronous DEM inspection for the Assistant tab.

Inspection of large DEMs (band statistics, projection, extent math) can take
a second or more, so it runs inside a :class:`QgsTask` instead of blocking
the GUI.  The :class:`DebouncedDemInspector` restarts a 700 ms timer on every
input change and emits ``inspected`` / ``failed`` with a generation counter —
the dock keeps the same single sink for both this async path and the manual
"Inspect DEM" button, and a stale slow result can never overwrite a newer one.
"""

from __future__ import annotations

from qgis.PyQt.QtCore import QObject, QTimer, pyqtSignal
from qgis.core import QgsApplication, QgsTask

from ..core.dem_info import inspect_dem_layer


class _InspectDemTask(QgsTask):
    """Runs :func:`inspect_dem_layer` off the GUI thread."""

    def __init__(self, layer, band):
        super().__init__(f"Terrain Product Studio — inspect {layer.name()}", QgsTask.CanCancel)
        self._layer = layer
        self._band = int(band)
        self.info = None
        self.error = None

    def run(self):
        try:
            self.info = inspect_dem_layer(self._layer, self._band)
            return True
        except Exception as error:  # surfaced via failed() — never crash QGIS
            self.error = str(error)
            return False


class DebouncedDemInspector(QObject):
    """Inspect the selected DEM 700 ms after the last change, off the GUI thread."""

    inspected = pyqtSignal(object, int)  # info dict, generation
    failed = pyqtSignal(str, int)        # message, generation

    def __init__(self, parent=None):
        super().__init__(parent)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(700)
        self._timer.timeout.connect(self._run)
        self._layer = None
        self._band = 1
        self._generation = 0

    @property
    def generation(self) -> int:
        """Current generation — the dock ignores results with older ones."""
        return self._generation

    def set_inputs(self, layer, band):
        """Restart the debounce with a new DEM layer / band."""
        self._layer = layer
        self._band = int(band or 1)
        self._timer.start()

    def mark_fresh(self, info):
        """Ingest an already-computed inspection synchronously (manual button).

        Bumps the generation so any pending async result is dropped.
        """
        self._generation += 1
        self.inspected.emit(info, self._generation)

    def _run(self):
        layer = self._layer
        if layer is None or not layer.isValid():
            return
        self._generation += 1
        generation = self._generation
        task = _InspectDemTask(layer, self._band)
        task.taskCompleted.connect(
            lambda t=task: self._emit_result(t, generation)
        )
        task.taskTerminated.connect(
            lambda t=task: self._emit_failure(t, generation)
        )
        QgsApplication.taskManager().addTask(task)

    def _emit_result(self, task, generation):
        if task.info is not None:
            self.inspected.emit(task.info, generation)
        else:
            self.failed.emit(
                task.error or "DEM inspection returned no data.", generation
            )

    def _emit_failure(self, task, generation):
        self.failed.emit(task.error or "DEM inspection was cancelled.", generation)
