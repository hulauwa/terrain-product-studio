import unittest

from terrain_product_studio.core.map_recipes import (
    recipe_for,
    resolve_recipe_keys,
    resolve_role,
)


class MapRecipeTests(unittest.TestCase):
    def test_smoothed_variant_replaces_raw_layer(self):
        available = {"CONTOURS", "CONTOURS_SMOOTH", "STREAMS", "STREAMS_SMOOTH"}
        self.assertEqual(resolve_role(available, "contours"), "CONTOURS_SMOOTH")
        self.assertEqual(resolve_role(available, "streams"), "STREAMS_SMOOTH")

    def test_raw_variant_is_fallback(self):
        self.assertEqual(resolve_role({"CONTOURS"}, "contours"), "CONTOURS")
        self.assertEqual(resolve_role({"STREAMS"}, "streams"), "STREAMS")

    def test_default_canvas_stays_minimal(self):
        available = {
            "SPOT_ELEVATIONS",
            "STREAMS_SMOOTH",
            "RIDGES",
            "CONTOURS_SMOOTH",
            "MULTI_HILLSHADE",
            "COLOR_RELIEF",
        }
        keys = resolve_recipe_keys(available, "usgs_classic", target="canvas")
        self.assertEqual(
            keys,
            ("SPOT_ELEVATIONS", "CONTOURS_SMOOTH", "MULTI_HILLSHADE", "COLOR_RELIEF"),
        )

    def test_blueprint_is_a_linework_recipe(self):
        available = {"STREAMS", "CONTOURS", "MULTI_HILLSHADE", "COLOR_RELIEF"}
        keys = resolve_recipe_keys(available, "engineering_blueprint", target="canvas")
        self.assertEqual(keys, ("STREAMS", "CONTOURS"))
        self.assertEqual(recipe_for("engineering_blueprint").key, "engineering_blueprint")


if __name__ == "__main__":
    unittest.main()
