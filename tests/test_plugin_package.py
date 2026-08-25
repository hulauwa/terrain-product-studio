import configparser
import os
import unittest


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLUGIN = os.path.join(ROOT, "terrain_product_studio")


class PluginPackageTests(unittest.TestCase):
    def test_required_plugin_files_exist(self):
        required = (
            "__init__.py",
            "metadata.txt",
            "plugin.py",
            "provider.py",
            "dock.py",
            "core/preprocessing.py",
            "core/flow_products.py",
            "core/product_registry.py",
            "core/style_packs.py",
            "core/design_presets.py",
            "core/layout_styles.py",
            "core/layout_geometry.py",
            "core/cartography_qa.py",
            "core/share_package.py",
            "ui/task_controller.py",
            "icons/terrain_studio.png",
            "assets/preset_previews/standard_topo.jpg",
        )
        for relative_path in required:
            self.assertTrue(os.path.isfile(os.path.join(PLUGIN, relative_path)), relative_path)

    def test_metadata_has_processing_provider(self):
        parser = configparser.ConfigParser()
        parser.read(os.path.join(PLUGIN, "metadata.txt"), encoding="utf-8")
        metadata = parser["general"]
        self.assertEqual(metadata.get("hasprocessingprovider"), "yes")
        self.assertEqual(metadata.get("qgisminimumversion"), "3.34")
        self.assertEqual(metadata.get("version"), "3.0.3")
        self.assertEqual(metadata.get("experimental"), "False")
        self.assertEqual(metadata.get("license"), "GPLv2")


if __name__ == "__main__":
    unittest.main()
