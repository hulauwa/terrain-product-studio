"""Dependency planning for the one-click terrain processing DAG.

The planner has no QGIS imports. It converts the user's requested products
into an effective product set and makes every automatically enabled dependency
explicit and testable.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import FrozenSet, Iterable


SLOPE_DEPENDENTS = frozenset(
    {"SUITABILITY", "LANDSLIDE_HAZARD", "SPI", "STI", "MULTIHAZARD"}
)
ACCUMULATION_DEPENDENTS = frozenset(
    {"LANDSLIDE_HAZARD", "SPI", "STI", "MULTIHAZARD"}
)


@dataclass(frozen=True)
class PipelinePlan:
    """Resolved dependencies and hydrology execution decisions for one run."""

    requested_products: FrozenSet[str]
    effective_products: FrozenSet[str]
    auto_enabled_products: FrozenSet[str]
    run_hydrology: bool
    create_twi: bool
    accumulation_source: str


def plan_pipeline(
    requested_products: Iterable[str],
    *,
    create_hydrology: bool,
    create_twi: bool,
    accumulation_available: bool,
) -> PipelinePlan:
    """Resolve the minimal correct pipeline for a product selection."""

    requested = frozenset(requested_products)
    auto_enabled = set()
    if requested & SLOPE_DEPENDENTS and "SLOPE" not in requested:
        auto_enabled.add("SLOPE")

    resolved_twi = bool(create_twi or "MULTIHAZARD" in requested)
    needs_accumulation = bool(
        requested & ACCUMULATION_DEPENDENTS or resolved_twi
    )
    run_hydrology = bool(
        create_hydrology or (needs_accumulation and not accumulation_available)
    )
    if resolved_twi and not run_hydrology and "SLOPE" not in requested:
        auto_enabled.add("SLOPE")

    if run_hydrology:
        accumulation_source = "generated"
    elif accumulation_available:
        accumulation_source = "external"
    else:
        accumulation_source = "none"

    return PipelinePlan(
        requested_products=requested,
        effective_products=frozenset(set(requested) | auto_enabled),
        auto_enabled_products=frozenset(auto_enabled),
        run_hydrology=run_hydrology,
        create_twi=resolved_twi,
        accumulation_source=accumulation_source,
    )
