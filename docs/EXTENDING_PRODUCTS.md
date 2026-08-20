# Extending Terrain Product Studio products

The built-in product catalog lives in
`terrain_product_studio/core/product_registry.py`. It is the shared source for:

- Processing boolean parameters and their defaults;
- the dock product grid, labels and ordering;
- transitive product dependencies;
- analytical capabilities such as real flow accumulation and TWI.

## Product declaration

Add a `ProductSpec` to `BUILTIN_PRODUCTS` with a stable output `key`, a stable
`CREATE_*` Processing parameter, UI labels, category, dependencies and required
capabilities. The registry rejects duplicate keys/parameters, unknown dependencies
and dependency cycles at import time.

Use `dependencies` for another generated product and `capabilities` for an input
the pipeline must provide. Supported core capabilities are:

- `flow_accumulation`: use an external compatible grid or run hydrology;
- `twi`: create TWI and supply real flow accumulation first.

The planner resolves transitive dependencies automatically. For example,
`MULTIHAZARD` declares `SLOPE`, `flow_accumulation` and `twi`; selecting only that
product therefore schedules the complete valid chain.

## Calculation and presentation checklist

The registry declares the contract; it does not hide implementation choices.
For a new built-in product:

1. Implement the calculator in a focused `core/` module.
2. Add the `ProductSpec` and a Processing output definition.
3. Call the calculator from the relevant builder and publish its output key.
4. Add styling/layer-loading rules only if it should appear in QGIS.
5. Add provenance, assumptions and fitness limitations.
6. Add registry, calculator and QGIS runtime tests.

Do not overwrite analytical values, substitute slope for drainage, or bypass the
projected working DEM.

## Extension-module hook

An explicitly trusted Python module can expose:

```python
def register_products(registry):
    registry.register(ProductSpec(...))
```

Pass that module name to `ProductRegistry.discover()`. Discovery is explicit—there
is no implicit filesystem scan—and the combined graph is validated before use.
The host still owns the Processing parameter/output and calculation integration.
