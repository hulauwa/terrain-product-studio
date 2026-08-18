"""QGIS-bound tests for the cartographic smoothing engine (requires osgeo)."""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from osgeo import ogr  # noqa: E402

from terrain_product_studio.core.smoothing import (  # noqa: E402
    simplify_dp,
    smooth_chaikin,
    smooth_geometries,
)


class SmoothingUnitTests(unittest.TestCase):
    def test_chaikin_smooths_zigzag(self):
        zigzag = [(0.0, 0.0), (1.0, 1.0), (2.0, 0.0), (3.0, 1.0), (4.0, 0.0)]
        result = smooth_chaikin(zigzag, iterations=1)
        self.assertEqual(len(result), 2 * (len(zigzag) - 1))
        # Endpoints are preserved by construction (25%/75% splits).
        self.assertEqual(result[0], (0.25, 0.25))
        self.assertEqual(result[-1], (3.75, 0.25))

    def test_chaikin_keeps_short_lines(self):
        short = [(0.0, 0.0), (1.0, 1.0)]
        self.assertEqual(smooth_chaikin(short, 3), short)

    def test_dp_removes_collinear_vertices(self):
        line = [(0.0, 0.0), (1.0, 0.0), (2.0, 0.0), (3.0, 0.0)]
        result = simplify_dp(line, tolerance=0.1)
        self.assertEqual(result, [(0.0, 0.0), (3.0, 0.0)])

    def test_dp_keeps_high_curvature_bends(self):
        # A vertex farther than the tolerance from the chord is retained;
        # (2.0, 0.0) sits 2/sqrt(10) ≈ 0.632 from the (0,0)->(3,1) chord.
        line = [(0.0, 0.0), (1.0, 0.0), (2.0, 0.0), (3.0, 1.0)]
        result = simplify_dp(line, tolerance=0.5)
        self.assertEqual(result, [(0.0, 0.0), (2.0, 0.0), (3.0, 1.0)])

    def test_dp_zero_tolerance_keeps_all(self):
        line = [(0.0, 0.0), (1.0, 2.0), (2.0, 0.0)]
        self.assertEqual(simplify_dp(line, 0.0), line)

    def test_roundtrip_preserves_attributes(self):
        with tempfile.TemporaryDirectory() as folder:
            source = os.path.join(folder, "lines.gpkg")
            target = os.path.join(folder, "lines_smooth.gpkg")
            driver = ogr.GetDriverByName("GPKG")
            ds = driver.CreateDataSource(source)
            layer = ds.CreateLayer("lines", None, ogr.wkbLineString)
            field = ogr.FieldDefn("ELEV", ogr.OFTReal)
            layer.CreateField(field)
            line = ogr.Geometry(ogr.wkbLineString)
            for x, y in ((0, 0), (1, 1), (2, 0), (3, 1), (4, 0)):
                line.AddPoint(x, y)
            feature = ogr.Feature(layer.GetLayerDefn())
            feature.SetGeometry(line)
            feature.SetField("ELEV", 123.5)
            layer.CreateFeature(feature)
            ds = None

            summary = smooth_geometries(source, target, iterations=2)
            self.assertEqual(summary["input_features"], 1)
            self.assertEqual(summary["smoothed_features"], 1)

            check = ogr.Open(target, 0)
            check_layer = check.GetLayer(0)
            self.assertEqual(check_layer.GetGeomType(), ogr.wkbLineString)
            out_feature = check_layer.GetNextFeature()
            self.assertEqual(out_feature.GetField("ELEV"), 123.5)
            self.assertGreater(out_feature.GetGeometryRef().GetPointCount(), 5)
            check = None


if __name__ == "__main__":
    unittest.main()
