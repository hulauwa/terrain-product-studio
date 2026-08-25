"""Unit tests for core/restyle.py — report manifest parsing (no QGIS)."""

import json
import os
import tempfile
import unittest

from terrain_product_studio.core.restyle import parse_run_manifest


class ParseRunManifestTests(unittest.TestCase):
    def _write_report(self, folder, data):
        path = os.path.join(folder, "report.json")
        with open(path, "w", encoding="utf-8") as stream:
            json.dump(data, stream)
        return path

    def test_happy_path(self):
        with tempfile.TemporaryDirectory() as folder:
            path = self._write_report(
                folder,
                {
                    "contour_interval": 10.0,
                    "index_contour_interval": 50.0,
                    "elevation_unit": "m",
                    "scene3d": {"basemap": "osm", "texture_size": 3072},
                    "outputs": {
                        "WORKING_DEM": "/tmp/dem.tif",
                        "CONTOURS": "/tmp/contours.gpkg",
                        "REPORT": "/tmp/report.json",
                    },
                },
            )
            plan = parse_run_manifest(path)
            self.assertIsNotNone(plan)
            self.assertEqual(plan.contour_interval, 10.0)
            self.assertEqual(plan.index_multiplier, 5)
            self.assertEqual(plan.elevation_unit, "m")
            self.assertEqual(plan.outputs["WORKING_DEM"], "/tmp/dem.tif")
            self.assertEqual(plan.scene3d["basemap"], "osm")

    def test_missing_file_returns_none(self):
        self.assertIsNone(parse_run_manifest("/nonexistent/report.json"))
        self.assertIsNone(parse_run_manifest(""))

    def test_invalid_json_returns_none(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "report.json")
            with open(path, "w", encoding="utf-8") as stream:
                stream.write("{not json")
            self.assertIsNone(parse_run_manifest(path))

    def test_non_dict_returns_none(self):
        with tempfile.TemporaryDirectory() as folder:
            path = self._write_report(folder, ["not", "a", "dict"])
            self.assertIsNone(parse_run_manifest(path))

    def test_missing_keys_graceful(self):
        with tempfile.TemporaryDirectory() as folder:
            path = self._write_report(folder, {})
            plan = parse_run_manifest(path)
            self.assertIsNotNone(plan)
            self.assertEqual(plan.outputs, {})
            self.assertEqual(plan.contour_interval, 10.0)
            self.assertEqual(plan.index_multiplier, 5)
            self.assertEqual(plan.elevation_unit, "m")
            self.assertEqual(plan.scene3d, {})

    def test_index_multiplier_derivation(self):
        cases = ((10.0, 50.0, 5), (25.0, 125.0, 5), (5.0, 100.0, 20), (0.0, 0.0, 5))
        with tempfile.TemporaryDirectory() as folder:
            for contour, index, expected in cases:
                path = self._write_report(
                    folder,
                    {
                        "contour_interval": contour,
                        "index_contour_interval": index,
                    },
                )
                plan = parse_run_manifest(path)
                self.assertEqual(plan.index_multiplier, expected)

    def test_outputs_skip_empty_values(self):
        with tempfile.TemporaryDirectory() as folder:
            path = self._write_report(
                folder,
                {"outputs": {"VIEWER_3D": "/tmp/scene.html", "REPORT": ""}},
            )
            plan = parse_run_manifest(path)
            self.assertIn("VIEWER_3D", plan.outputs)
            self.assertNotIn("REPORT", plan.outputs)


if __name__ == "__main__":
    unittest.main()
