"""Builders for terrain products that depend on real flow accumulation."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Callable, Mapping, MutableMapping, Optional, Tuple


class FlowProductError(RuntimeError):
    """Raised when a mandatory flow-product dependency cannot be resolved."""


@dataclass(frozen=True)
class FlowCalculators:
    """Injectable analytical functions used by :class:`FlowProductBuilder`."""

    twi: Callable
    landslide: Callable
    spi: Callable
    sti: Callable
    multihazard: Callable

    @classmethod
    def defaults(cls):
        # Keep GDAL/Numpy imports out of this orchestration module so its
        # dependency behavior can be unit-tested without a QGIS runtime.
        from .thematic_terrain import (
            calculate_landslide_hazard,
            calculate_multihazard,
            calculate_spi,
            calculate_sti,
            calculate_twi,
        )

        return cls(
            twi=calculate_twi,
            landslide=calculate_landslide_hazard,
            spi=calculate_spi,
            sti=calculate_sti,
            multihazard=calculate_multihazard,
        )


class FlowProductBuilder:
    """Build TWI, landslide, SPI/STI and multi-hazard from one flow grid."""

    SLOPE = "SLOPE"
    TWI = "TWI"
    LANDSLIDE_HAZARD = "LANDSLIDE_HAZARD"
    LS_FACTOR = "LS_FACTOR"
    SPI = "SPI"
    STI = "STI"
    MULTIHAZARD = "MULTIHAZARD"

    def __init__(
        self,
        *,
        output_path: Callable[[str, str], str],
        advance: Callable[[str], None],
        feedback,
        calculators: Optional[FlowCalculators] = None,
        translate: Callable[[str], str] = lambda value: value,
    ):
        self.output_path = output_path
        self.advance = advance
        self.feedback = feedback
        self.calculators = calculators or FlowCalculators.defaults()
        self.tr = translate

    def build(
        self,
        outputs: MutableMapping[str, str],
        selected: Mapping[str, bool],
        *,
        create_twi: bool,
        accumulation_path: Optional[str],
        multihazard_weights: Tuple[float, float, float],
    ) -> list[str]:
        """Add requested flow products to ``outputs`` and return notices."""

        warnings = []
        slope_path = outputs.get(self.SLOPE)
        needs_new_twi = bool(create_twi and not outputs.get(self.TWI))
        if self._needs_slope(selected, needs_new_twi) and not slope_path:
            raise FlowProductError(
                self.tr("Flow-dependent products require a valid slope raster.")
            )
        if self._needs_accumulation(selected, needs_new_twi) and not accumulation_path:
            raise FlowProductError(
                self.tr("Flow-dependent products require a real flow accumulation raster.")
            )

        if create_twi and not outputs.get(self.TWI) and not self._cancelled():
            self.advance(self.tr("Calculating Topographic Wetness Index…"))
            twi_path = self.output_path("twi", "tif")
            try:
                self.calculators.twi(accumulation_path, slope_path, twi_path)
            except Exception as error:
                raise FlowProductError(str(error)) from error
            if not os.path.exists(twi_path):
                raise FlowProductError(self.tr("TWI output was not created."))
            outputs[self.TWI] = twi_path

        if selected.get(self.LANDSLIDE_HAZARD) and not self._cancelled():
            self.advance(
                self.tr("Calculating landslide hazard and RUSLE LS factor…")
            )
            try:
                self._build_landslide(outputs, slope_path, accumulation_path)
            except Exception as error:
                warnings.append(f"Landslide hazard notice: {error}")

        for output_key, calculator, suffix, label in (
            (self.SPI, self.calculators.spi, "stream_power_index", "SPI"),
            (self.STI, self.calculators.sti, "sediment_transport_index", "STI"),
        ):
            if selected.get(output_key) and not self._cancelled():
                self.advance(self.tr(f"Calculating {label}…"))
                index_path = self.output_path(suffix, "tif")
                try:
                    calculator(accumulation_path, slope_path, index_path)
                    if os.path.exists(index_path):
                        outputs[output_key] = index_path
                except Exception as error:
                    warnings.append(f"{label} notice: {error}")

        if selected.get(self.MULTIHAZARD) and not self._cancelled():
            self.advance(
                self.tr(
                    "Combining landslide, TWI and slope into a multi-hazard index…"
                )
            )
            try:
                landslide_path = outputs.get(self.LANDSLIDE_HAZARD)
                if not landslide_path:
                    self._build_landslide(outputs, slope_path, accumulation_path)
                    landslide_path = outputs.get(self.LANDSLIDE_HAZARD)

                twi_path = outputs.get(self.TWI)
                if not twi_path:
                    raise FlowProductError(
                        self.tr("Multi-hazard dependency error: TWI was not created.")
                    )

                multi_path = self.output_path("multi_hazard", "tif")
                stats = self.calculators.multihazard(
                    landslide_path,
                    twi_path,
                    slope_path,
                    multi_path,
                    weights=multihazard_weights,
                )
                if os.path.exists(multi_path):
                    outputs[self.MULTIHAZARD] = multi_path
                    self.feedback.pushInfo(
                        self.tr(
                            "Multi-hazard: {low}% low, {moderate}% moderate, "
                            "{high}% high"
                        ).format(**stats)
                    )
            except Exception as error:
                warnings.append(f"Multi-hazard notice: {error}")

        return warnings

    def _build_landslide(self, outputs, slope_path, accumulation_path):
        hazard_path = self.output_path("landslide_hazard", "tif")
        ls_path = self.output_path("rusle_ls_factor", "tif")
        self.calculators.landslide(
            slope_path,
            accumulation_path,
            hazard_path,
            ls_path,
        )
        if os.path.exists(hazard_path):
            outputs[self.LANDSLIDE_HAZARD] = hazard_path
        if os.path.exists(ls_path):
            outputs[self.LS_FACTOR] = ls_path

    def _cancelled(self):
        return bool(self.feedback.isCanceled())

    @classmethod
    def _needs_slope(cls, selected, needs_new_twi):
        return bool(
            needs_new_twi
            or any(
                selected.get(key)
                for key in (
                    cls.LANDSLIDE_HAZARD,
                    cls.SPI,
                    cls.STI,
                    cls.MULTIHAZARD,
                )
            )
        )

    @classmethod
    def _needs_accumulation(cls, selected, needs_new_twi):
        return cls._needs_slope(selected, needs_new_twi)
