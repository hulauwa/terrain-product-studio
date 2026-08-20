import unittest

from terrain_product_studio.core.provenance import (
    analytical_assumptions,
    build_run_provenance,
)


class ProvenanceTests(unittest.TestCase):
    def test_missing_flow_dependency_is_disclosed(self):
        notes = analytical_assumptions(
            {"LANDSLIDE_HAZARD"}, accumulation_supplied=False, smoothing_iterations=0
        )
        flow_note = next(note for note in notes if note["scope"] == "flow-dependent products")
        self.assertIn("No flow-accumulation", flow_note["method"])
        self.assertIn("must not be generated", flow_note["fitness_note"])

    def test_preprocessing_records_reprojection_and_clip(self):
        provenance = build_run_provenance(
            {"width": 10, "height": 20, "pixel_size_x": 0.1, "pixel_size_y": 0.1},
            source_path="dem.tif",
            source_band=1,
            source_crs="EPSG:4326",
            working_crs="EPSG:32648",
            auto_reproject=True,
            compression="DEFLATE",
            clip_extent=[1, 2, 3, 4],
            smoothing_iterations=2,
            simplify_tolerance=0.5,
        )
        self.assertTrue(provenance["crs"]["reprojected"])
        self.assertEqual(
            provenance["preprocessing"]["reprojection_resampling"], "bilinear"
        )
        self.assertEqual(
            provenance["preprocessing"]["clip_extent_working_crs_xmin_ymin_xmax_ymax"],
            [1, 2, 3, 4],
        )
        self.assertTrue(provenance["preprocessing"]["raw_vectors_retained"])


if __name__ == "__main__":
    unittest.main()
