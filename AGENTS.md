# Terrain Product Studio — AI/Contributor Guide

Read this file before changing the plugin. It is the shortest reliable map of
the repository and its invariants.

## Product

Terrain Product Studio is a QGIS Processing plugin. One DEM becomes a set of
analytical rasters, cartographic vectors, hydrology products, styled QGIS
layers, print layouts, reports, 3D exports and shareable bundles.

Supported runtime: QGIS 3.34+ and QGIS 4.x. The package must not require Python
dependencies outside a standard QGIS/GDAL installation.

## Repository map

- `terrain_product_studio/plugin.py`: plugin lifecycle only.
- `terrain_product_studio/dock.py`: dock composition and result presentation.
  Keep domain calculations and task ownership out of this file.
- `terrain_product_studio/ui/task_controller.py`: asynchronous Processing task,
  context, progress, cancellation and cleanup ownership.
- `terrain_product_studio/provider.py`: registers Processing algorithms.
- `terrain_product_studio/algorithms/`: Processing-facing parameter and output
  contracts. Algorithms orchestrate reusable core services.
- `terrain_product_studio/core/`: reusable domain modules.
- `core/pipeline.py`: dependency planner for the one-click processing DAG.
- `core/product_registry.py`: shared product declarations, dependency graph,
  validation and explicit extension-module discovery.
- `core/preprocessing.py`: projected/clipped DEM preparation and typed hand-off.
- `core/flow_products.py`: flow-dependent product orchestration.
- `core/map_recipes.py`: logical canvas/layout stacks and raw/smooth selection.
- `core/presets.py`: palette, cartography and industry data definitions.
- `core/layers.py`, `core/styles.py`, `core/layouts.py`: QGIS presentation layer.
- `core/native_hydrology.py`: D8 flow and watershed computation.
- `core/provenance.py`: source, preprocessing and analytical assumptions.
- `core/qgis_compat.py`: every QGIS 3/4 enum compatibility branch belongs here.
- `tests/test_*.py`: pure tests; `tests/qgis_*` are runtime probes inside QGIS.
- `scripts/package_plugin.py`: builds the only ZIP users should install.

## Runtime flow

1. The dock validates input and captures a run configuration; the task controller
   owns the asynchronous QGIS Processing lifecycle.
2. `core/pipeline.py` resolves requested, effective and auto-enabled dependencies.
3. `DemPreprocessor` inspects/reprojects/clips the DEM exactly once.
4. Hydrology runs next when requested or required; it supplies real accumulation
   and TWI before landslide, SPI, STI and multi-hazard calculations.
5. Viewer/report exports use the complete result set, then the bundle is created.
6. The final JSON manifest records the pipeline plan, provenance, assumptions,
   warnings and complete outputs. The dock only loads/styles these final results.

Never reintroduce cached accumulation or a slope-as-drainage proxy. An external
accumulation raster must match the preprocessed DEM CRS, dimensions and extent.

## Non-negotiable invariants

- Preserve raw analytical values. Styling and smoothing must never overwrite raw data.
- If a smooth contour/stream exists, show it and keep the raw layer loaded but hidden.
- All distance/area derivatives run in a projected metric working CRS.
- Record DEM path/band/resolution/NoData, source and working CRS, resampling,
  clipping, smoothing and limitations in the run report.
- Risk/suitability outputs are screening aids. State assumptions and fitness limits.
- Layouts contain an intentional map recipe, never every generated analytical layer.
- Keep QGIS API version branches centralized in `core/qgis_compat.py`.
- Never hardcode output paths or overwrite existing user products.

## Extending the plugin

New analytical product:

1. Read `docs/EXTENDING_PRODUCTS.md` and add a validated `ProductSpec`.
2. Put the calculation in a small `core/` service with a clear input/output contract.
3. Add the Processing output and builder integration in the relevant algorithm.
4. Add styling/layer loading only if it should appear in QGIS.
5. Add provenance/fitness notes and pure/QGIS tests.

New map type:

1. Add the visual tokens to `CARTOGRAPHY_PRESETS`.
2. Add a special `MapRecipe` only when its visible layer stack differs from default.
3. Use logical roles; do not name raw/smooth variants in UI code.
4. Verify canvas order, layout order, light/dark background, labels and legend.

## Verification

Run from repository root:

```bash
python3 -m unittest tests.test_math_utils tests.test_plugin_package \
  tests.test_map_recipes tests.test_pipeline tests.test_flow_products \
  tests.test_product_registry tests.test_provenance -v
python3 -m compileall -q terrain_product_studio tests
python3 scripts/package_plugin.py
```

QGIS-dependent probes require a real QGIS Python runtime. A system-Python import
failure for `qgis` or `osgeo` is an environment limitation, not a plugin result.

## Release rules

- `terrain_product_studio/metadata.txt` is mandatory and must be committed.
- Keep metadata version, changelog and documented release ZIP version aligned.
- Set `experimental=False` only for a release intended for normal users.
- Users install `terrain_product_studio-X.Y.Z.zip` from GitHub Releases or the
  QGIS repository. GitHub `Code -> Download ZIP` is a source archive and is not
  an installable plugin.
- The ZIP must have exactly one top-level `terrain_product_studio/` directory.
- Do not commit generated `dist/`, caches, local profiles or temporary DEM output.

## Completed roadmap through 2.5.0

- Phase 1 — pipeline correctness: completed in 2.2.0.
- Phase 2 — maintainability foundation: completed in 2.3.0 with preprocessing,
  flow-product and task-lifecycle services. UI panels can be extracted gradually
  without changing their behavior.
- Phase 3 — extensibility: completed in 2.4.0 with the product registry,
  dependency/capability declarations, validation and explicit module discovery.
- Phase 4 — Map Design Studio: completed in 2.5.0 with cohesive style packs,
  canonical styled DEMs, per-layout style snapshots, map-book batches,
  cartographic QA, direct Web 3D data loading and safe parallel I/O.
- Quality gates now cover registry contracts, dependency golden behavior, release
  packaging and QGIS 4.x runtime probes. Expanding hosted CI across every supported
  QGIS build remains ongoing release engineering rather than a product phase.

## Roadmap through 3.0.2

- Phase 5 — Restyle, smart defaults & hydrology geometry (kept in 3.0.2):

  - `core/math_utils.py` gained pure formulas: `suggest_stream_threshold`,
    `river_width_m`/`river_depth_m` (Horton–Leopold) and
    `suggest_vertical_exaggeration`; `core/dem_info.py` reports `relief_m` and
    `extent_width_m`.
  - Hydrology (`core/native_hydrology.py`, `algorithms/build_hydrology.py`,
    `algorithms/build_package.py`) exports `WIDTH_M`/`DEPTH_M` into the
    GeoPackage, driven by `RIVER_WIDTH_FACTOR` / `RIVER_DEPTH_FACTOR`.
  - The 3D WebGIS viewer is the proven 2.7.1 engine: inline
    `_HTML_TEMPLATE` inside `core/web_3d_viewer.py`, grid-cell world frame,
    CDN three.js/geotiff at view time. The 3.0.0 viewer redesign (real-metre
    frame, overlay textures, basemaps, vertical-exaggeration param) was
    removed in 3.0.2; do not re-add external template assets or SCENE_*
    parameters.
  - Restyle (`core/restyle.py` + `layers.apply_result_styles` +
    `layout_styles.apply_style_overrides_to_layout`): re-applies current
    cartography to canvas/QML/layouts from `report.json` without re-running
    the pipeline. The never-overwrite invariant has one sanctioned exception:
    the plugin's own products (its QML packs, layout style overrides) are
    overwritten in place.
  - Smart defaults (`core/smart_defaults.py` + `ui/smart_defaults.py`): four
    DEM-derived suggestions; async inspection is debounced in a `QgsTask` with a
    generation counter so a stale result can never win over a manual Inspect.
  - New invariants: a restyle must never create groups, never recompute
    analysis, never touch `report.json`; the viewer must keep `viewer_version`
    semantics readable by older plugins.
