import unittest

from terrain_product_studio.core.pipeline import plan_pipeline
from terrain_product_studio.core.product_registry import ProductRegistry, ProductSpec


class PipelinePlanTests(unittest.TestCase):
    def test_flow_product_auto_enables_slope_and_hydrology(self):
        plan = plan_pipeline(
            {"SPI"},
            create_hydrology=False,
            create_twi=False,
            accumulation_available=False,
        )
        self.assertIn("SLOPE", plan.effective_products)
        self.assertEqual(plan.auto_enabled_products, frozenset({"SLOPE"}))
        self.assertTrue(plan.run_hydrology)
        self.assertEqual(plan.accumulation_source, "generated")

    def test_external_accumulation_avoids_unrequested_hydrology(self):
        plan = plan_pipeline(
            {"LANDSLIDE_HAZARD"},
            create_hydrology=False,
            create_twi=False,
            accumulation_available=True,
        )
        self.assertFalse(plan.run_hydrology)
        self.assertEqual(plan.accumulation_source, "external")

    def test_multihazard_always_resolves_twi_dependency(self):
        plan = plan_pipeline(
            {"MULTIHAZARD"},
            create_hydrology=False,
            create_twi=False,
            accumulation_available=False,
        )
        self.assertTrue(plan.create_twi)
        self.assertTrue(plan.run_hydrology)

    def test_explicit_hydrology_runs_for_cartography_only(self):
        plan = plan_pipeline(
            {"COLOR_RELIEF"},
            create_hydrology=True,
            create_twi=True,
            accumulation_available=False,
        )
        self.assertTrue(plan.run_hydrology)
        self.assertTrue(plan.create_twi)
        self.assertEqual(plan.auto_enabled_products, frozenset())

    def test_external_accumulation_twi_auto_enables_slope(self):
        plan = plan_pipeline(
            {"COLOR_RELIEF"},
            create_hydrology=False,
            create_twi=True,
            accumulation_available=True,
        )
        self.assertFalse(plan.run_hydrology)
        self.assertIn("SLOPE", plan.auto_enabled_products)

    def test_twi_without_accumulation_triggers_hydrology(self):
        plan = plan_pipeline(
            {"COLOR_RELIEF"},
            create_hydrology=False,
            create_twi=True,
            accumulation_available=False,
        )
        self.assertTrue(plan.run_hydrology)

    def test_discovered_product_dependencies_feed_the_pipeline(self):
        registry = ProductRegistry(
            (
                ProductSpec(
                    "SLOPE",
                    "CREATE_SLOPE",
                    "Slope",
                    "Slope",
                    "test",
                ),
                ProductSpec(
                    "CUSTOM_FLOW_INDEX",
                    "CREATE_CUSTOM_FLOW_INDEX",
                    "Custom flow index",
                    "Custom flow index",
                    "test",
                    dependencies=frozenset({"SLOPE"}),
                    capabilities=frozenset({"flow_accumulation"}),
                ),
            )
        ).validate()
        plan = plan_pipeline(
            {"CUSTOM_FLOW_INDEX"},
            create_hydrology=False,
            create_twi=False,
            accumulation_available=False,
            registry=registry,
        )
        self.assertEqual(plan.auto_enabled_products, frozenset({"SLOPE"}))
        self.assertTrue(plan.run_hydrology)


if __name__ == "__main__":
    unittest.main()
