"""Dependency planning for the one-click terrain processing DAG.

The planner has no QGIS imports. It converts the user's requested products
into an effective product set and makes every automatically enabled dependency
explicit and testable.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import FrozenSet, Iterable, Optional

from .product_registry import DEFAULT_PRODUCT_REGISTRY, ProductRegistry


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
    registry: Optional[ProductRegistry] = None,
) -> PipelinePlan:
    """Resolve the minimal correct pipeline for a product selection."""

    requested = frozenset(requested_products)
    product_registry = registry or DEFAULT_PRODUCT_REGISTRY
    resolution = product_registry.resolve(requested)
    effective = set(resolution.effective)
    resolved_twi = bool(create_twi or "twi" in resolution.capabilities)
    needs_accumulation = bool(
        "flow_accumulation" in resolution.capabilities or resolved_twi
    )
    run_hydrology = bool(
        create_hydrology or (needs_accumulation and not accumulation_available)
    )
    if resolved_twi and not run_hydrology and "SLOPE" not in effective:
        product_registry.require("SLOPE")
        effective.add("SLOPE")

    auto_enabled = effective - requested

    if run_hydrology:
        accumulation_source = "generated"
    elif accumulation_available:
        accumulation_source = "external"
    else:
        accumulation_source = "none"

    return PipelinePlan(
        requested_products=requested,
        effective_products=frozenset(effective),
        auto_enabled_products=frozenset(auto_enabled),
        run_hydrology=run_hydrology,
        create_twi=resolved_twi,
        accumulation_source=accumulation_source,
    )
