"""Lifecycle controller for asynchronous QGIS Processing runs."""

from __future__ import annotations

from qgis.core import (
    QgsApplication,
    QgsProcessingAlgRunnerTask,
    QgsProcessingContext,
    QgsProcessingFeedback,
    QgsProject,
)


class ProcessingTaskController:
    """Own one Processing task, its context, feedback and cancellation state."""

    def __init__(self, *, task_manager=None, project=None):
        self.task_manager = task_manager or QgsApplication.taskManager()
        self.project = project or QgsProject.instance()
        self.task = None
        self.context = None
        self.feedback = None

    @property
    def active(self):
        return self.task is not None

    def start(
        self,
        algorithm,
        parameters,
        *,
        progress_callback,
        finished_callback,
    ):
        """Create and queue one task, rejecting overlapping runs."""

        if self.active:
            raise RuntimeError("A terrain Processing task is already active.")

        self.context = QgsProcessingContext()
        self.context.setProject(self.project)
        self.feedback = QgsProcessingFeedback()
        self.feedback.progressChanged.connect(progress_callback)
        self.task = QgsProcessingAlgRunnerTask(
            algorithm,
            parameters,
            self.context,
            self.feedback,
        )
        self.task.executed.connect(
            lambda successful, results: self._finished(
                successful,
                results,
                finished_callback,
            )
        )
        try:
            self.task_manager.addTask(self.task)
        except Exception:
            self.task = None
            self.context = None
            self.feedback = None
            raise
        return self.task

    def cancel(self):
        """Request cancellation through both QGIS task APIs."""

        if self.task is not None:
            self.task.cancel()
        if self.feedback is not None:
            self.feedback.cancel()

    def _finished(self, successful, results, callback):
        self.task = None
        self.context = None
        self.feedback = None
        callback(successful, results)
