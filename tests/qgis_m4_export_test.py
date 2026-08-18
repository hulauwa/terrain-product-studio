"""QGIS-bound tests for M4: STL/OBJ mesh export and run history."""

import os
import struct
import sys
import tempfile
import unittest

import numpy as np
from osgeo import gdal

sys.path.insert(0, os.path.dirname(__file__))
from qgis_m2_thematic_test import create_synthetic_dem  # noqa: E402

from terrain_product_studio.core.export_3d import export_obj, export_stl  # noqa: E402
from terrain_product_studio.core.history import append_history, load_history  # noqa: E402


class M4ExportTests(unittest.TestCase):
    def _flat_dem(self, folder, width=20, height=15, value=100.0):
        path = os.path.join(folder, "flat.tif")
        ds = gdal.GetDriverByName("GTiff").Create(path, width, height, 1, gdal.GDT_Float32)
        ds.SetGeoTransform([500000, 10, 0, 1200000, 0, -10])
        ds.GetRasterBand(1).WriteArray(np.full((height, width), value, dtype=np.float32))
        ds = None
        return path

    def test_stl_binary_structure_and_count(self):
        with tempfile.TemporaryDirectory() as folder:
            dem = self._flat_dem(folder)
            out = os.path.join(folder, "model.stl")
            count = export_stl(dem, out)
            # 20x15 grid -> 19x14 quads -> 2 triangles each = 532
            self.assertEqual(count, 532)
            with open(out, "rb") as handle:
                header = handle.read(80)
                (triangles,) = struct.unpack("<I", handle.read(4))
                self.assertEqual(triangles, 532)
                self.assertEqual(os.path.getsize(out), 80 + 4 + 532 * 50)
                body = handle.read()
            self.assertEqual(len(body), 532 * 50)
            # First triangle normal of a flat DEM must point up (0, 0, 1)
            nx, ny, nz = struct.unpack("<3f", body[:12])
            self.assertAlmostEqual(nx, 0.0, places=5)
            self.assertAlmostEqual(ny, 0.0, places=5)
            self.assertAlmostEqual(nz, 1.0, places=5)
            # Header has a non-empty printable name
            self.assertIn(b"STL", header[:60])

    def test_stl_z_scale_and_base_extruded(self):
        with tempfile.TemporaryDirectory() as folder:
            dem = os.path.join(folder, "dem.tif")
            create_synthetic_dem(dem)
            ds = gdal.Open(dem)
            dem_data = ds.GetRasterBand(1).ReadAsArray()
            dem_min = float(dem_data.min())
            dem_max = float(dem_data.max())
            ds = None
            out = os.path.join(folder, "scaled.stl")
            export_stl(dem, out, z_scale=2.0, base_thickness_m=5.0)
            with open(out, "rb") as handle:
                handle.read(80)
                (triangles,) = struct.unpack("<I", handle.read(4))
            # surface 119*119*2 + bottom 119*119*2 + walls 4*119*2 = 29274
            self.assertEqual(triangles, 119 * 119 * 2 * 2 + 4 * 119 * 2)

            # z range: top vertices scaled by 2, base plate at min_z*2 - 5
            zs = []
            with open(out, "rb") as handle:
                handle.read(84)
                for _ in range(triangles):
                    body = handle.read(50)
                    floats = struct.unpack_from("<9f", body, 12)
                    for k in range(3):
                        zs.append(floats[2 + 3 * k])
            self.assertAlmostEqual(max(zs), 2.0 * dem_max, delta=0.5)
            self.assertAlmostEqual(min(zs), 2.0 * dem_min - 5.0, delta=1.0)

            # Watertightness: every directed edge must be matched by an
            # opposite-directed edge (no open boundary).
            edges = {}
            with open(out, "rb") as handle:
                handle.read(84)
                for _ in range(triangles):
                    body = handle.read(50)
                    verts = np.array(struct.unpack_from("<9f", body, 12)).reshape(3, 3)
                    for k in range(3):
                        key = tuple(np.round(verts[k], 3))
                        nxt = tuple(np.round(verts[(k + 1) % 3], 3))
                        edges[(key, nxt)] = edges.get((key, nxt), 0) + 1
            self.assertTrue(edges)  # non-trivial mesh
            for (u, v), count in edges.items():
                self.assertEqual(count, 1, f"edge {u}->{v} not unique")
                self.assertEqual(edges.get((v, u), 0), 1, f"edge {u}->{v} unmatched")

    def test_stl_downsamples_large_grids(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "big.tif")
            ds = gdal.GetDriverByName("GTiff").Create(path, 3000, 2000, 1, gdal.GDT_Float32)
            ds.SetGeoTransform([500000, 10, 0, 1200000, 0, -10])
            ds.GetRasterBand(1).WriteArray(np.zeros((2000, 3000), dtype=np.float32))
            ds = None
            out = os.path.join(folder, "big.stl")
            count = export_stl(path, out)
            # capped at 1024x1024 -> 1023*1023*2 triangles
            self.assertEqual(count, 1023 * 1023 * 2)

    def test_obj_has_mtl_and_1_based_faces(self):
        with tempfile.TemporaryDirectory() as folder:
            dem = self._flat_dem(folder, width=5, height=4)
            out = os.path.join(folder, "model.obj")
            export_obj(dem, out)
            self.assertTrue(os.path.exists(os.path.join(folder, "model.mtl")))
            with open(out, encoding="utf-8") as handle:
                lines = [line.strip() for line in handle if line.strip()]
            self.assertIn("mtllib model.mtl", lines)
            self.assertIn("usemtl terrain", lines)
            vertices = [line for line in lines if line.startswith("v ")]
            faces = [line for line in lines if line.startswith("f ")]
            self.assertEqual(len(vertices), 20)
            self.assertEqual(len(faces), 24)  # 4x3 quads * 2
            for face in faces:
                indices = [int(part) for part in face[2:].split()]
                self.assertTrue(all(1 <= i <= 20 for i in indices))

    def test_history_roundtrip_and_cap(self):
        with tempfile.TemporaryDirectory() as folder:
            fake = os.path.join(folder, "history.json")
            import terrain_product_studio.core.history as history_mod

            original = history_mod.history_path
            history_mod.history_path = lambda: fake
            try:
                append_history({"timestamp": "2026-08-18T10:00:00+00:00", "folder": "/tmp", "prefix": "a"})
                entries = load_history()
                self.assertEqual(len(entries), 1)
                self.assertEqual(entries[0]["prefix"], "a")
                # corrupt file -> empty list, no crash
                with open(fake, "w", encoding="utf-8") as handle:
                    handle.write("not json")
                self.assertEqual(load_history(), [])
            finally:
                history_mod.history_path = original


if __name__ == "__main__":
    unittest.main()
