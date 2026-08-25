import os
import tempfile
import unittest

from terrain_product_studio.core.math_utils import (
    STANDARD_INTERVALS,
    estimate_output_bytes,
    human_bytes,
    index_interval,
    interpolate_color_stops,
    nice_interval,
    river_depth_m,
    river_width_m,
    sanitize_prefix,
    snap_interval,
    suggest_contour_interval,
    suggest_stream_threshold,
    suggest_vertical_exaggeration,
    unique_path,
    utm_epsg_for_lon_lat,
)


class MathUtilsTests(unittest.TestCase):
    def test_nice_interval_uses_cartographic_sequence(self):
        self.assertEqual(nice_interval(300, 30), 10.0)
        self.assertEqual(nice_interval(720, 30), 25.0)
        self.assertEqual(nice_interval(75, 30), 2.5)
        self.assertEqual(nice_interval(0, 30), 1.0)

    def test_nice_interval_never_creates_more_than_target_density(self):
        for relief in (0.01, 1, 17, 240, 9850):
            interval = nice_interval(relief, 30)
            self.assertGreater(interval, 0)
            self.assertLessEqual(relief / interval, 30.0000001)

    def test_index_interval(self):
        self.assertEqual(index_interval(10, 5), 50.0)
        with self.assertRaises(ValueError):
            index_interval(0, 5)

    def test_utm_epsg(self):
        self.assertEqual(utm_epsg_for_lon_lat(105.8, 21.0), 32648)
        self.assertEqual(utm_epsg_for_lon_lat(106.7, 10.8), 32648)
        self.assertEqual(utm_epsg_for_lon_lat(151.2, -33.9), 32756)
        self.assertEqual(utm_epsg_for_lon_lat(180.0, 0.0), 32660)

    def test_invalid_utm_coordinates(self):
        with self.assertRaises(ValueError):
            utm_epsg_for_lon_lat(181, 0)

    def test_sanitize_prefix(self):
        self.assertEqual(sanitize_prefix("Địa hình Hà Nội 01"), "dia_hinh_ha_noi_01")
        self.assertEqual(sanitize_prefix(" *** "), "terrain")

    def test_color_stop_interpolation(self):
        stops = interpolate_color_stops(
            100,
            200,
            ((0.0, 1, 2, 3), (0.5, 4, 5, 6), (1.0, 7, 8, 9)),
        )
        self.assertEqual(stops[0], (100.0, 1, 2, 3))
        self.assertEqual(stops[1], (150.0, 4, 5, 6))
        self.assertEqual(stops[2], (200.0, 7, 8, 9))

    def test_size_helpers(self):
        self.assertEqual(estimate_output_bytes(100, 100, 2, 4, 1), 80000)
        self.assertEqual(human_bytes(1024), "1.0 KB")

    def test_snap_interval(self):
        self.assertEqual(snap_interval(3.0), 5.0)
        self.assertEqual(snap_interval(10.0), 10.0)
        self.assertEqual(snap_interval(12.0), 20.0)
        self.assertEqual(snap_interval(27.0), 50.0)
        self.assertEqual(snap_interval(0.5), 1.0)
        self.assertEqual(snap_interval(-4.0), 1.0)

    def test_suggest_contour_interval_scales_with_aoi(self):
        # Small AOI (2 km town) keeps a fine interval; large AOI (100 km
        # province) thins contours out to keep the map legible.
        small = suggest_contour_interval(relief=500.0, extent_width_m=2000.0)
        large = suggest_contour_interval(relief=500.0, extent_width_m=100000.0)
        self.assertLess(small, large)
        self.assertIn(small, STANDARD_INTERVALS)
        self.assertIn(large, STANDARD_INTERVALS)
        # Flat terrain still produces a sensible minimum.
        self.assertGreaterEqual(suggest_contour_interval(1.0, 10000.0), 1.0)

    def test_suggest_stream_threshold_scales_with_pixel_size(self):
        # Fine pixels are clamped to the minimum so LiDAR rill noise is
        # suppressed; coarse pixels grow the area threshold so only real
        # channels appear.
        self.assertEqual(suggest_stream_threshold(1.0)[0], 0.5)
        self.assertEqual(suggest_stream_threshold(10.0)[0], 0.5)
        self.assertAlmostEqual(suggest_stream_threshold(30.0)[0], 4.41, places=2)
        self.assertAlmostEqual(suggest_stream_threshold(100.0)[0], 90.0, places=1)
        # Monotonic non-decreasing in pixel size.
        previous = 0.0
        for pixel in (1, 5, 10, 30, 60, 100, 250):
            value = suggest_stream_threshold(float(pixel))[0]
            self.assertGreaterEqual(value, previous - 1e-9)
            previous = value
        # Clamps honored.
        self.assertEqual(suggest_stream_threshold(10000.0)[0], 250.0)
        self.assertEqual(suggest_stream_threshold(0.0)[0], 0.5)
        # Rationale carries the worked numbers.
        value, rationale = suggest_stream_threshold(30.0)
        self.assertIn(f"{value:g}", rationale)
        self.assertIn("resolution", rationale)

    def test_river_width_follows_horton_scaling(self):
        self.assertAlmostEqual(river_width_m(25.0), 1.5, places=1)
        self.assertAlmostEqual(river_width_m(500.0), 6.7, places=1)
        self.assertAlmostEqual(river_width_m(10000.0), 30.0, places=1)
        self.assertAlmostEqual(river_width_m(100000.0), 94.9, places=1)
        # Factor scales linearly.
        self.assertAlmostEqual(river_width_m(500.0, factor=2.0), 13.4, places=1)
        # Degenerate input and clamps.
        self.assertEqual(river_width_m(0.0), 0.8)
        self.assertEqual(river_width_m(-5.0), 0.8)
        self.assertEqual(river_width_m(1e12), 400.0)

    def test_river_depth_power_law(self):
        self.assertAlmostEqual(river_depth_m(1.5), 0.70, places=2)
        self.assertAlmostEqual(river_depth_m(30.0), 4.2, places=1)
        self.assertAlmostEqual(river_depth_m(94.87), 8.4, delta=0.1)
        self.assertEqual(river_depth_m(0.0), 0.3)
        self.assertEqual(river_depth_m(1e9), 40.0)

    def test_suggest_vertical_exaggeration_balances_relief(self):
        self.assertAlmostEqual(suggest_vertical_exaggeration(100.0, 2000.0), 2.4)
        self.assertAlmostEqual(suggest_vertical_exaggeration(1400.0, 50000.0), 4.3, places=1)
        self.assertAlmostEqual(suggest_vertical_exaggeration(2000.0, 20000.0), 1.2)
        # Clamps.
        self.assertEqual(suggest_vertical_exaggeration(500.0, 100000.0), 10.0)
        self.assertEqual(suggest_vertical_exaggeration(10000.0, 2000.0), 0.5)
        # Degenerate input falls back to a neutral 1.0.
        self.assertEqual(suggest_vertical_exaggeration(0.0, 2000.0), 1.0)
        self.assertEqual(suggest_vertical_exaggeration(100.0, 0.0), 1.0)
        self.assertEqual(suggest_vertical_exaggeration(-3.0, 2000.0), 1.0)

    def test_unique_path_does_not_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "terrain.tif")
            self.assertEqual(unique_path(path), path)
            with open(path, "w", encoding="utf-8") as stream:
                stream.write("test")
            self.assertEqual(unique_path(path), os.path.join(folder, "terrain_2.tif"))


if __name__ == "__main__":
    unittest.main()
