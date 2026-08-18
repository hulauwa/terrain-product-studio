import os

from qgis.PyQt.QtCore import Qt, QCoreApplication, QTranslator
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction
from qgis.core import QgsApplication

from .dock import TerrainStudioDock
from .provider import TerrainStudioProvider


class TerrainProductStudioPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.provider = None
        self.action = None
        self.dock = None
        self.translator = None

        # Set up translation if available for active locale
        locale = QgsApplication.locale()
        locale_path = os.path.join(
            os.path.dirname(__file__), "i18n", f"terrain_product_studio_{locale[:2]}.qm"
        )
        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)
            QCoreApplication.installTranslator(self.translator)

        self.menu_name = self.tr("&Terrain Product Studio")

    @staticmethod
    def tr(message):
        return QCoreApplication.translate("TerrainProductStudioPlugin", message)

    def initProcessing(self):
        if self.provider is None:
            self.provider = TerrainStudioProvider()
            QgsApplication.processingRegistry().addProvider(self.provider)

    def initGui(self):
        self.initProcessing()

        # qgis_process loads enabled plugins without a desktop interface. The
        # Processing provider must remain usable in that headless context.
        if self.iface is None:
            return

        icon_path = os.path.join(os.path.dirname(__file__), "icons", "terrain_studio.png")
        self.action = QAction(QIcon(icon_path), self.tr("Terrain Product Studio"), self.iface.mainWindow())
        self.action.setObjectName("terrainProductStudioAction")
        self.action.setCheckable(True)
        self.action.triggered.connect(self.show_dock)
        self.iface.addPluginToRasterMenu(self.menu_name, self.action)
        self.iface.addToolBarIcon(self.action)

    def show_dock(self):
        if self.dock is None:
            self.dock = TerrainStudioDock(self.iface, self.iface.mainWindow())
            self.dock.setObjectName("TerrainProductStudioDock")
            self.dock.visibilityChanged.connect(self.action.setChecked)
            try:
                dock_area = Qt.DockWidgetArea.RightDockWidgetArea
            except AttributeError:  # Qt 5 unscoped enum
                dock_area = getattr(Qt, "RightDockWidgetArea")
            self.iface.addDockWidget(dock_area, self.dock)
        self.dock.show()
        self.dock.raise_()
        self.action.setChecked(True)

    def unload(self):
        if self.dock is not None:
            self.dock.cancel_task()
            self.iface.removeDockWidget(self.dock)
            self.dock.deleteLater()
            self.dock = None
        if self.action is not None and self.iface is not None:
            self.iface.removePluginRasterMenu(self.menu_name, self.action)
            self.iface.removeToolBarIcon(self.action)
            self.action.deleteLater()
            self.action = None
        if self.provider is not None:
            QgsApplication.processingRegistry().removeProvider(self.provider)
            self.provider = None
