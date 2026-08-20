"""Declarative registry for terrain products and their dependencies."""

from __future__ import annotations

from dataclasses import dataclass, field
from importlib import import_module
from typing import Dict, FrozenSet, Iterable, Optional, Tuple


class ProductRegistryError(ValueError):
    """Raised when a product declaration or dependency graph is invalid."""


@dataclass(frozen=True)
class ProductSpec:
    """Stable declaration shared by Processing, the dock and the planner."""

    key: str
    parameter: str
    processing_label: str
    ui_label: str
    category: str
    default_enabled: bool = False
    show_in_product_grid: bool = True
    section: str = "terrain"
    dependencies: FrozenSet[str] = field(default_factory=frozenset)
    capabilities: FrozenSet[str] = field(default_factory=frozenset)
    ui_order: Optional[int] = None


@dataclass(frozen=True)
class DependencyResolution:
    """Transitive product and capability requirements for one selection."""

    requested: FrozenSet[str]
    effective: FrozenSet[str]
    auto_enabled: FrozenSet[str]
    capabilities: FrozenSet[str]


class ProductRegistry:
    """Ordered, validated collection of built-in or discovered products."""

    def __init__(self, specs: Iterable[ProductSpec] = ()):
        self._specs: Dict[str, ProductSpec] = {}
        for spec in specs:
            self.register(spec)

    def register(self, spec: ProductSpec):
        """Register one declaration and reject ambiguous identifiers."""

        if not isinstance(spec, ProductSpec):
            raise ProductRegistryError("Product declarations must be ProductSpec values.")
        if not spec.key or spec.key != spec.key.upper():
            raise ProductRegistryError("Product keys must be non-empty uppercase identifiers.")
        if not spec.parameter.startswith("CREATE_"):
            raise ProductRegistryError(
                f"Product {spec.key} must use a CREATE_* Processing parameter."
            )
        if spec.key in self._specs:
            raise ProductRegistryError(f"Duplicate product key: {spec.key}")
        if any(existing.parameter == spec.parameter for existing in self._specs.values()):
            raise ProductRegistryError(
                f"Duplicate product parameter: {spec.parameter}"
            )
        self._specs[spec.key] = spec
        return spec

    def discover(self, module_names: Iterable[str]):
        """Load explicit extension modules exposing ``register_products(registry)``."""

        for module_name in module_names:
            module = import_module(module_name)
            register_products = getattr(module, "register_products", None)
            if not callable(register_products):
                raise ProductRegistryError(
                    f"Product module {module_name!r} has no register_products hook."
                )
            register_products(self)
        self.validate()
        return self

    def get(self, key: str) -> Optional[ProductSpec]:
        return self._specs.get(key)

    def require(self, key: str) -> ProductSpec:
        spec = self.get(key)
        if spec is None:
            raise ProductRegistryError(f"Unknown product key: {key}")
        return spec

    def specs(self, *, section: Optional[str] = None) -> Tuple[ProductSpec, ...]:
        values = tuple(self._specs.values())
        if section is None:
            return values
        return tuple(spec for spec in values if spec.section == section)

    def product_grid_specs(self) -> Tuple[ProductSpec, ...]:
        ordered = [
            (index, spec)
            for index, spec in enumerate(self._specs.values())
            if spec.show_in_product_grid
        ]
        ordered.sort(
            key=lambda item: (
                item[1].ui_order if item[1].ui_order is not None else item[0]
            )
        )
        return tuple(spec for _, spec in ordered)

    def validate(self):
        """Reject missing product dependencies and dependency cycles."""

        for spec in self._specs.values():
            missing = sorted(spec.dependencies - self._specs.keys())
            if missing:
                raise ProductRegistryError(
                    f"Product {spec.key} has unknown dependencies: {', '.join(missing)}"
                )

        visiting = set()
        visited = set()

        def visit(key):
            if key in visiting:
                raise ProductRegistryError(f"Product dependency cycle includes {key}.")
            if key in visited:
                return
            visiting.add(key)
            for dependency in self._specs[key].dependencies:
                visit(dependency)
            visiting.remove(key)
            visited.add(key)

        for key in self._specs:
            visit(key)
        return self

    def resolve(self, requested_products: Iterable[str]) -> DependencyResolution:
        """Resolve transitive dependencies and analytical capabilities."""

        requested = frozenset(requested_products)
        unknown = sorted(requested - self._specs.keys())
        if unknown:
            raise ProductRegistryError(
                "Unknown requested products: " + ", ".join(unknown)
            )

        effective = set(requested)
        pending = list(requested)
        while pending:
            key = pending.pop()
            for dependency in self._specs[key].dependencies:
                if dependency not in effective:
                    effective.add(dependency)
                    pending.append(dependency)

        capabilities = set()
        for key in effective:
            capabilities.update(self._specs[key].capabilities)
        return DependencyResolution(
            requested=requested,
            effective=frozenset(effective),
            auto_enabled=frozenset(effective - requested),
            capabilities=frozenset(capabilities),
        )


BUILTIN_PRODUCTS = (
    ProductSpec(
        key="COLOR_RELIEF",
        parameter="CREATE_COLOR_RELIEF",
        processing_label="Elevation color relief",
        ui_label="RGB color relief (compatibility copy)",
        category="cartography",
        default_enabled=False,
    ),
    ProductSpec(
        key="HILLSHADE",
        parameter="CREATE_HILLSHADE",
        processing_label="Standard hillshade",
        ui_label="Hillshade (single light)",
        category="cartography",
    ),
    ProductSpec(
        key="MULTI_HILLSHADE",
        parameter="CREATE_MULTI_HILLSHADE",
        processing_label="Multidirectional hillshade",
        ui_label="Multidirectional hillshade",
        category="cartography",
        default_enabled=True,
    ),
    ProductSpec(
        key="SLOPE",
        parameter="CREATE_SLOPE",
        processing_label="Slope in degrees",
        ui_label="Slope (degrees)",
        category="geomorphometry",
    ),
    ProductSpec(
        key="ASPECT",
        parameter="CREATE_ASPECT",
        processing_label="Aspect",
        ui_label="Aspect (orientation)",
        category="geomorphometry",
    ),
    ProductSpec(
        key="TRI",
        parameter="CREATE_TRI",
        processing_label="Terrain Ruggedness Index",
        ui_label="Terrain Ruggedness Index (TRI)",
        category="geomorphometry",
    ),
    ProductSpec(
        key="TPI",
        parameter="CREATE_TPI",
        processing_label="Topographic Position Index",
        ui_label="Topographic Position Index (TPI)",
        category="geomorphometry",
    ),
    ProductSpec(
        key="ROUGHNESS",
        parameter="CREATE_ROUGHNESS",
        processing_label="Roughness",
        ui_label="Roughness",
        category="geomorphometry",
    ),
    ProductSpec(
        key="PROFILE_CURVATURE",
        parameter="CREATE_PROFILE_CURVATURE",
        processing_label="Profile curvature",
        ui_label="Profile curvature (flow acceleration)",
        category="geomorphometry",
        ui_order=1000,
    ),
    ProductSpec(
        key="PLANFORM_CURVATURE",
        parameter="CREATE_PLANFORM_CURVATURE",
        processing_label="Planform curvature",
        ui_label="Planform curvature (flow convergence)",
        category="geomorphometry",
        ui_order=1010,
    ),
    ProductSpec(
        key="CONTOURS",
        parameter="CREATE_CONTOURS",
        processing_label="Contours",
        ui_label="Contours",
        category="cartography",
        default_enabled=True,
        show_in_product_grid=False,
    ),
    ProductSpec(
        key="SPOT_ELEVATIONS",
        parameter="CREATE_SPOT_ELEVATIONS",
        processing_label="Spot elevation peaks",
        ui_label="Spot elevation peaks (markers)",
        category="cartography",
        default_enabled=True,
    ),
    ProductSpec(
        key="SUITABILITY",
        parameter="CREATE_SUITABILITY",
        processing_label="Slope construction suitability",
        ui_label="Construction suitability (TCVN)",
        category="screening",
        dependencies=frozenset({"SLOPE"}),
    ),
    ProductSpec(
        key="LANDSLIDE_HAZARD",
        parameter="CREATE_LANDSLIDE",
        processing_label="Landslide hazard & RUSLE LS factor",
        ui_label="Landslide hazard & RUSLE LS",
        category="screening",
        dependencies=frozenset({"SLOPE"}),
        capabilities=frozenset({"flow_accumulation"}),
    ),
    ProductSpec(
        key="GEOMORPHON",
        parameter="CREATE_GEOMORPHON",
        processing_label="Geomorphon terrain forms (10 classes)",
        ui_label="Geomorphon terrain forms (10 classes)",
        category="geomorphometry",
    ),
    ProductSpec(
        key="SPI",
        parameter="CREATE_SPI",
        processing_label="Stream Power Index (SPI)",
        ui_label="Stream Power Index (SPI)",
        category="hydrology",
        dependencies=frozenset({"SLOPE"}),
        capabilities=frozenset({"flow_accumulation"}),
    ),
    ProductSpec(
        key="STI",
        parameter="CREATE_STI",
        processing_label="Sediment Transport Index (STI)",
        ui_label="Sediment Transport Index (STI)",
        category="hydrology",
        dependencies=frozenset({"SLOPE"}),
        capabilities=frozenset({"flow_accumulation"}),
    ),
    ProductSpec(
        key="MULTIHAZARD",
        parameter="CREATE_MULTIHAZARD",
        processing_label=(
            "Multi-hazard composite index (landslide + TWI + slope)"
        ),
        ui_label="Multi-hazard composite (landslide + TWI + slope)",
        category="screening",
        dependencies=frozenset({"SLOPE"}),
        capabilities=frozenset({"flow_accumulation", "twi"}),
    ),
    ProductSpec(
        key="VIEWER_3D",
        parameter="CREATE_3D_VIEWER",
        processing_label="Interactive 3D Web Terrain Viewer (HTML)",
        ui_label="Interactive 3D Web Terrain Viewer (HTML)",
        category="export",
    ),
    ProductSpec(
        key="INTELLIGENCE_REPORT",
        parameter="CREATE_INTELLIGENCE_REPORT",
        processing_label="Topographic Intelligence Report (HTML)",
        ui_label="Topographic Intelligence Report (HTML)",
        category="export",
    ),
    ProductSpec(
        key="BUNDLE",
        parameter="CREATE_BUNDLE",
        processing_label="Export all products to a single GeoPackage bundle",
        ui_label="GeoPackage bundle",
        category="export",
        default_enabled=True,
        show_in_product_grid=False,
        section="export",
    ),
)


DEFAULT_PRODUCT_REGISTRY = ProductRegistry(BUILTIN_PRODUCTS).validate()
