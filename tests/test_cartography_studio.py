import json
import os
import tempfile
import unittest

from terrain_product_studio.core.cartography_qa import (
    inspect_layer_recipe,
    validate_layout_config,
)
from terrain_product_studio.core.font_resolver import resolve_font_family
from terrain_product_studio.core.design_presets import (
    DEFAULT_DESIGN_PRESET,
    DESIGN_PRESETS,
    validate_design_presets,
)
from terrain_product_studio.core.map_recipes import resolve_recipe_keys
from terrain_product_studio.core.layout_geometry import (
    plan_layout_geometry,
    validate_layout_geometry,
)
from terrain_product_studio.core.product_registry import DEFAULT_PRODUCT_REGISTRY
from terrain_product_studio.core.share_package import write_share_manifest
from terrain_product_studio.core.style_packs import (
    LAYOUT_TEMPLATES,
    STYLE_PACKS,
    validate_style_packs,
)


class CartographyStudioTests(unittest.TestCase):
    def test_small_curated_design_library_is_valid_and_lightweight(self):
        self.assertEqual(DEFAULT_DESIGN_PRESET, "standard_topo")
        self.assertEqual(validate_design_presets(), ())
        self.assertEqual(len(DESIGN_PRESETS), 6)
        preview_root = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "terrain_product_studio",
            "assets",
            "preset_previews",
        )
        preview_paths = [
            os.path.join(preview_root, design.preview)
            for design in DESIGN_PRESETS.values()
        ]
        self.assertTrue(all(os.path.isfile(path) for path in preview_paths))
        self.assertLess(sum(os.path.getsize(path) for path in preview_paths), 200_000)

    def test_style_packs_are_complete_and_use_diverse_templates(self):
        self.assertEqual(validate_style_packs(), ())
        self.assertGreaterEqual(len(STYLE_PACKS), 5)
        self.assertGreaterEqual(
            len({pack.layout_template for pack in STYLE_PACKS.values()}), 5
        )
        self.assertTrue(
            all(pack.layout_template in LAYOUT_TEMPLATES for pack in STYLE_PACKS.values())
        )

    def test_font_resolver_reports_substitution(self):
        resolved = resolve_font_family("Missing Serif", ("Noto Sans", "Arial"))
        self.assertEqual(resolved.family, "Noto Sans")
        self.assertTrue(resolved.substituted)
        exact = resolve_font_family("arial", ("Noto Sans", "Arial"))
        self.assertEqual(exact.family, "Arial")
        self.assertFalse(exact.substituted)

    def test_numeric_dem_is_preferred_over_rgb_compatibility_copy(self):
        self.assertFalse(
            DEFAULT_PRODUCT_REGISTRY.require("COLOR_RELIEF").default_enabled
        )
        keys = resolve_recipe_keys(
            {"WORKING_DEM", "COLOR_RELIEF", "MULTI_HILLSHADE"},
            "natural_earth",
            target="layout",
        )
        self.assertIn("WORKING_DEM", keys)
        self.assertNotIn("COLOR_RELIEF", keys)

    def test_every_design_recipe_keeps_the_numeric_dem(self):
        available = {"WORKING_DEM", "MULTI_HILLSHADE"}
        for design in DESIGN_PRESETS.values():
            with self.subTest(design=design.key):
                keys = resolve_recipe_keys(
                    available, design.map_style, target="layout"
                )
                self.assertIn("WORKING_DEM", keys)

    def test_recipe_inspector_explains_smoothed_variant(self):
        selected, notes = inspect_layer_recipe(
            {"WORKING_DEM", "CONTOURS", "CONTOURS_SMOOTH"},
            "natural_earth",
        )
        self.assertIn("CONTOURS_SMOOTH", selected)
        self.assertTrue(any("raw layer" in note for note in notes))

    def test_layout_qa_flags_font_and_low_dpi(self):
        findings = validate_layout_config(
            {"title": "Map", "dpi": 150},
            {"WORKING_DEM"},
            font_substituted=True,
        )
        messages = " ".join(finding.message for finding in findings)
        self.assertIn("below 200", messages)
        self.assertIn("font is not installed", messages)

    def test_every_template_has_collision_free_a_series_geometry(self):
        pages = ((297, 210), (210, 297), (420, 297), (297, 420), (841, 594), (594, 841))
        for template in LAYOUT_TEMPLATES.values():
            for page_width, page_height in pages:
                with self.subTest(template=template.key, page=(page_width, page_height)):
                    geometry = plan_layout_geometry(
                        template.key,
                        template.legend_position,
                        page_width,
                        page_height,
                        show_legend=template.show_legend,
                        show_metadata=template.show_metadata,
                    )
                    self.assertEqual(validate_layout_geometry(geometry), ())
                    self.assertIn("map", geometry.boxes)
                    self.assertIn("scale", geometry.boxes)
                    self.assertIn("north", geometry.boxes)

    def test_share_manifest_indexes_without_copying_dem(self):
        with tempfile.TemporaryDirectory() as folder:
            dem = os.path.join(folder, "dem.tif")
            with open(dem, "wb") as stream:
                stream.write(b"dem")
            manifest_path = write_share_manifest(
                folder,
                "terrain",
                {"WORKING_DEM": dem},
                {"preset": "natural_earth", "font_family": "Noto Sans"},
                ("Terrain Map",),
            )
            with open(manifest_path, encoding="utf-8") as stream:
                manifest = json.load(stream)
            self.assertEqual(manifest["canonical_dem_role"], "WORKING_DEM")
            self.assertEqual(manifest["layouts"], ["Terrain Map"])
            self.assertEqual(manifest["files"][0]["path"], "dem.tif")

    def test_share_manifest_keeps_layout_choice_independent_from_style(self):
        with tempfile.TemporaryDirectory() as folder:
            dem = os.path.join(folder, "dem.tif")
            with open(dem, "wb") as stream:
                stream.write(b"dem")
            manifest_path = write_share_manifest(
                folder,
                "terrain",
                {"WORKING_DEM": dem},
                {
                    "preset": "night_dark",
                    "palette_key": "natural",
                    "layout_template": "classic_topo",
                },
            )
            with open(manifest_path, encoding="utf-8") as stream:
                manifest = json.load(stream)
            style = manifest["style_pack"]
            self.assertEqual(style["key"], "night_dark")
            self.assertEqual(style["palette"], "natural")
            self.assertEqual(style["layout_template"], "classic_topo")


if __name__ == "__main__":
    unittest.main()
