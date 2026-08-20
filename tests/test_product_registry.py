import sys
import types
import unittest

from terrain_product_studio.core.product_registry import (
    DEFAULT_PRODUCT_REGISTRY,
    ProductRegistry,
    ProductRegistryError,
    ProductSpec,
)


def _spec(key, *, dependencies=frozenset(), capabilities=frozenset()):
    return ProductSpec(
        key=key,
        parameter=f"CREATE_{key}",
        processing_label=key.title(),
        ui_label=key.title(),
        category="test",
        dependencies=dependencies,
        capabilities=capabilities,
    )


class ProductRegistryTests(unittest.TestCase):
    def test_builtin_registry_matches_the_processing_and_dock_contract(self):
        self.assertEqual(len(DEFAULT_PRODUCT_REGISTRY.specs()), 21)
        grid_parameters = [
            spec.parameter for spec in DEFAULT_PRODUCT_REGISTRY.product_grid_specs()
        ]
        self.assertEqual(len(grid_parameters), 19)
        self.assertEqual(
            grid_parameters[-2:],
            ["CREATE_PROFILE_CURVATURE", "CREATE_PLANFORM_CURVATURE"],
        )
        self.assertNotIn("CREATE_CONTOURS", grid_parameters)
        self.assertNotIn("CREATE_BUNDLE", grid_parameters)

    def test_multihazard_resolves_declared_product_and_capabilities(self):
        resolution = DEFAULT_PRODUCT_REGISTRY.resolve({"MULTIHAZARD"})
        self.assertEqual(
            resolution.effective,
            frozenset({"MULTIHAZARD", "SLOPE"}),
        )
        self.assertEqual(resolution.auto_enabled, frozenset({"SLOPE"}))
        self.assertEqual(
            resolution.capabilities,
            frozenset({"flow_accumulation", "twi"}),
        )

    def test_custom_product_uses_the_same_transitive_resolver(self):
        registry = ProductRegistry(
            (
                _spec("BASE"),
                _spec("DERIVED", dependencies=frozenset({"BASE"})),
                _spec("FINAL", dependencies=frozenset({"DERIVED"})),
            )
        ).validate()
        resolution = registry.resolve({"FINAL"})
        self.assertEqual(
            resolution.effective,
            frozenset({"BASE", "DERIVED", "FINAL"}),
        )

    def test_explicit_module_discovery_calls_register_hook(self):
        module_name = "tests._temporary_product_extension"
        module = types.ModuleType(module_name)

        def register_products(registry):
            registry.register(_spec("EXTENSION"))

        module.register_products = register_products
        sys.modules[module_name] = module
        try:
            registry = ProductRegistry().discover((module_name,))
            self.assertEqual(registry.require("EXTENSION").category, "test")
        finally:
            sys.modules.pop(module_name, None)

    def test_validation_rejects_missing_dependency_and_cycle(self):
        missing = ProductRegistry(
            (_spec("A", dependencies=frozenset({"MISSING"})),)
        )
        with self.assertRaisesRegex(ProductRegistryError, "unknown dependencies"):
            missing.validate()

        cycle = ProductRegistry(
            (
                _spec("A", dependencies=frozenset({"B"})),
                _spec("B", dependencies=frozenset({"A"})),
            )
        )
        with self.assertRaisesRegex(ProductRegistryError, "cycle"):
            cycle.validate()

    def test_duplicate_key_is_rejected(self):
        registry = ProductRegistry((_spec("A"),))
        with self.assertRaisesRegex(ProductRegistryError, "Duplicate product key"):
            registry.register(_spec("A"))


if __name__ == "__main__":
    unittest.main()
