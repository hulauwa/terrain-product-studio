import os
import tempfile
import unittest

from terrain_product_studio.core.flow_products import (
    FlowCalculators,
    FlowProductBuilder,
    FlowProductError,
)


class _Feedback:
    def __init__(self):
        self.messages = []

    def isCanceled(self):
        return False

    def pushInfo(self, message):
        self.messages.append(message)


class FlowProductBuilderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.calls = []
        self.feedback = _Feedback()
        self.advances = []

        def raster(name):
            def calculate(*args, **kwargs):
                self.calls.append((name, args, kwargs))
                output_index = 3 if name == "multihazard" else 2
                output_path = args[output_index]
                open(output_path, "wb").close()
                if name == "landslide" and len(args) > 3 and args[3]:
                    open(args[3], "wb").close()
                if name == "multihazard":
                    return {"low": 50, "moderate": 30, "high": 20}
                return {}

            return calculate

        self.calculators = FlowCalculators(
            twi=raster("twi"),
            landslide=raster("landslide"),
            spi=raster("spi"),
            sti=raster("sti"),
            multihazard=raster("multihazard"),
        )
        self.builder = FlowProductBuilder(
            output_path=lambda suffix, extension: os.path.join(
                self.temp.name, f"terrain_{suffix}.{extension}"
            ),
            advance=self.advances.append,
            feedback=self.feedback,
            calculators=self.calculators,
        )

    def tearDown(self):
        self.temp.cleanup()

    def test_multihazard_builds_missing_dependencies_once(self):
        slope_path = os.path.join(self.temp.name, "slope.tif")
        accumulation_path = os.path.join(self.temp.name, "acc.tif")
        outputs = {"SLOPE": slope_path}
        warnings = self.builder.build(
            outputs,
            {"MULTIHAZARD": True},
            create_twi=True,
            accumulation_path=accumulation_path,
            multihazard_weights=(0.5, 0.3, 0.2),
        )

        self.assertEqual(warnings, [])
        self.assertTrue(outputs["TWI"].endswith("terrain_twi.tif"))
        self.assertTrue(outputs["LANDSLIDE_HAZARD"].endswith("landslide_hazard.tif"))
        self.assertTrue(outputs["LS_FACTOR"].endswith("rusle_ls_factor.tif"))
        self.assertTrue(outputs["MULTIHAZARD"].endswith("multi_hazard.tif"))
        self.assertEqual(
            [call[0] for call in self.calls],
            ["twi", "landslide", "multihazard"],
        )

    def test_existing_twi_is_not_recalculated(self):
        outputs = {"TWI": "existing_twi.tif"}
        self.builder.build(
            outputs,
            {},
            create_twi=True,
            accumulation_path=None,
            multihazard_weights=(0.5, 0.3, 0.2),
        )
        self.assertEqual(self.calls, [])

    def test_missing_accumulation_fails_before_calculation(self):
        with self.assertRaisesRegex(FlowProductError, "flow accumulation"):
            self.builder.build(
                {"SLOPE": "slope.tif"},
                {"SPI": True},
                create_twi=False,
                accumulation_path=None,
                multihazard_weights=(0.5, 0.3, 0.2),
            )
        self.assertEqual(self.calls, [])


if __name__ == "__main__":
    unittest.main()
