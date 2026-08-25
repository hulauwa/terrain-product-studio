"""Unit tests for core/smart_defaults.py — suggestion math (no QGIS)."""

import unittest

from terrain_product_studio.core.math_utils import (
    river_depth_m,
    river_width_m,
    suggest_stream_threshold,
)
from terrain_product_studio.core.smart_defaults import compute_smart_defaults


def sample_info(**overrides):
    info = {
        "name": "sample_dem",
        "approx_pixel_m": 10.0,
        "relief_m": 1400.0,
        "extent_width_m": 50000.0,
        "suggested_contour_interval": 50.0,
        "recommended_contour_interval": 50.0,
        "suggested_working_crs": ("EPSG:32648", "UTM 48N fits the AOI."),
    }
    info.update(overrides)
    return info


class ComputeSmartDefaultsTests(unittest.TestCase):
    def test_full_fixture(self):
        suggestions = compute_smart_defaults(sample_info())
        keys = [suggestion.key for suggestion in suggestions]
        self.assertEqual(
            keys,
            [
                "contour_interval",
                "stream_threshold",
                "river_dimensions",
                "working_crs",
            ],
        )

    def test_contour_interval_value_and_rationale(self):
        suggestion = next(
            s
            for s in compute_smart_defaults(sample_info())
            if s.key == "contour_interval"
        )
        self.assertEqual(suggestion.value, 50.0)
        self.assertIn("1,400", suggestion.rationale)  # relief
        self.assertIn("50 km", suggestion.rationale)
        self.assertIn("28", suggestion.rationale)  # 1400 / 50 lines

    def test_stream_threshold_matches_formula(self):
        suggestion = next(
            s
            for s in compute_smart_defaults(sample_info())
            if s.key == "stream_threshold"
        )
        expected_ha, _ = suggest_stream_threshold(10.0)
        self.assertEqual(suggestion.value, expected_ha)
        self.assertEqual(suggestion.unit, "ha")

    def test_river_dimensions_headwater_example(self):
        suggestion = next(
            s
            for s in compute_smart_defaults(sample_info())
            if s.key == "river_dimensions"
        )
        self.assertEqual(suggestion.value, 1.0)
        threshold_ha, _ = suggest_stream_threshold(10.0)
        width = river_width_m(threshold_ha)
        depth = river_depth_m(width)
        self.assertIn(f"{width:.1f} m", suggestion.rationale)
        self.assertIn(f"{depth:.1f} m", suggestion.rationale)

    def test_working_crs_suggestion(self):
        suggestion = next(
            s
            for s in compute_smart_defaults(sample_info())
            if s.key == "working_crs"
        )
        self.assertEqual(suggestion.value, "EPSG:32648")
        self.assertIn("UTM 48N", suggestion.rationale)

    def test_flat_terrain_omits_relief_suggestions(self):
        suggestions = compute_smart_defaults(
            sample_info(relief_m=0.0, extent_width_m=5000.0)
        )
        keys = {suggestion.key for suggestion in suggestions}
        self.assertNotIn("contour_interval", keys)
        # stream threshold still works from pixel size
        self.assertIn("stream_threshold", keys)

    def test_missing_keys_fall_back_to_defaults(self):
        suggestions = compute_smart_defaults({"name": "bare"})
        self.assertTrue(suggestions)  # stream threshold from default 30 m pixel

    def test_non_dict_returns_empty(self):
        self.assertEqual(compute_smart_defaults(None), [])
        self.assertEqual(compute_smart_defaults(["x"]), [])

    def test_working_crs_as_plain_string(self):
        suggestions = compute_smart_defaults(
            sample_info(suggested_working_crs="EPSG:32648")
        )
        suggestion = next(
            s for s in suggestions if s.key == "working_crs"
        )
        self.assertEqual(suggestion.value, "EPSG:32648")


if __name__ == "__main__":
    unittest.main()
