# Changelog

## 2.7.1 — 2026-08-21

- Fixed the QGIS 3.40+ / QGIS 4 deprecation warning from `QgsRasterInterface.bandStatistics()`: band statistics now go through a centralized compatibility helper which uses the typed `Qgis.RasterBandStatistic` overload instead of the deprecated integer argument, across DEM inspection, layer styling and bundle building.
- Fixed a QGIS 4 / Qt 6 scoped-enum error on `QFrame.NoFrame` in the dock's scroll areas; the Qt 5 unscoped fallback is preserved.

## 2.7.0 — 2026-08-20

- Added a compact one-click design library with six curated combinations of layout template, QGIS layer styles, numeric DEM palette and coordinate-grid mode. Standard Topographic remains the simple recommended default and advanced overrides stay collapsed.
- Added lightweight built-in JPEG previews rendered from a central crop of the Lai Chau DEM; all six thumbnails total under 100 KB and the source DEM is never packaged.
- Added selectable map-CRS, WGS 84 (EPSG:4326), dual projected/WGS 84 and custom-EPSG grids. Dual grids reserve projected labels for left/bottom and geographic labels for right/top.
- Fixed real exported layouts still overlapping after collision planning: QGIS can resize a map item when fitting its extent, so the planned safe-zone position and dimensions are now reasserted after the extent is applied.
- Ensured every curated design, including Engineering Blueprint, explicitly keeps the numeric DEM and hillshade in its layer recipe; palettes remain QGIS renderer snapshots and do not require an RGB raster export.
- Renamed and documented the optional portable DEM copy so it is clear that it is a numeric GeoTIFF for sharing, not a color image.

## 2.6.0 — 2026-08-20

- Removed the A/B style comparison controls and restored a simpler map-design workflow.
- Layout template, map style and elevation color palette are now three independent choices; changing a palette no longer silently changes the map style or sheet composition.
- Added a pure collision-free geometry planner for all seven templates across A4/A3/A1 portrait and landscape pages. Map, grid marginalia, legend, north arrow, scale bar, metadata, title and source footer use reserved safe zones.
- Reworked typography around the official US Topo marginal hierarchy: compact 5–12 pt supporting text, 12–13 pt titles, horizontal grid labels outside the map frame and an Arial default for the classic topographic sheet.
- Added map-readiness warnings for overly long titles, unavailable templates and low-contrast dark-palette/light-style combinations.

## 2.5.2 — 2026-08-20

- Fixed the portable canonical DEM path failing with `NameError: gdal is not defined`.
- Moved portable GeoTIFF creation into the object-oriented DEM preprocessing service and added a real GDAL copy regression test.

## 2.5.1 — 2026-08-20

- Fixed the QGIS 4 / Qt 6 font crash in the Layout tab and at run time by resolving installed fonts through a centralized QGIS 3/4 compatibility helper.
- Reworked the dock for small screens: each long option page scrolls independently, while Quick Basemap, progress, Build/Cancel and result actions remain pinned at the bottom.
- The clean starter recipe now enables the canonical styled DEM, multidirectional hillshade, spot elevations and contours with Medium smoothing; raw contours remain available but hidden when the smooth cartographic copy exists.

## 2.5.0 — 2026-08-20

Map Design Studio release: one numeric DEM can now drive multiple independent layout designs without duplicated RGB rasters.

- Added cohesive Style Packs combining layout composition, QGIS layer styles, palette, typography, layer recipe and Web 3D colors; seven genuinely different sheet compositions replace the single shared layout skeleton.
- Added per-layout style snapshots generated from temporary layer clones. Multiple layouts can use the same QGIS layers with independent DEM, contour, stream, peak, ridge, hillshade and font styling.
- Added a drag-reorder map-book queue with Add, Duplicate, Remove and Generate All actions; PDF/PNG names include the layout name and every selected Style Pack is exported as reusable QML.
- The canonical `WORKING_DEM` is always exposed and styled as a single-band pseudocolor basemap. The physical RGB color-relief output is now an optional compatibility copy instead of the default basemap.
- Fixed font selection with installed-family resolution and visible fallback reporting; legend component enums now work across QGIS 3 and QGIS 4.
- Added map-readiness QA, an explainable layer-recipe inspector and a transparent share manifest recording files, styles, layouts and browser constraints.
- Raised the portable Web 3D preview from 240 to selectable 256/384/512 samples; fixed geographic aspect, surface coordinates and orthographic resize; added direct user-selected GeoTIFF/COG and GeoJSON loading.
- Improved throughput with `NUM_THREADS=ALL_CPUS` for tiled GeoTIFF creation and concurrent independent raster reads during Web 3D preparation. QGIS child Processing operations remain serialized for context safety.

## 2.4.0 — 2026-08-20

Extensibility and final roadmap release: one validated product catalog shared by the UI, Processing contract and dependency planner.

- Added an ordered `ProductRegistry` and immutable `ProductSpec` declarations for all 21 selectable Processing products and the 19-product dock grid.
- Product-to-product dependencies and analytical capabilities (`flow_accumulation`, `twi`) are declared with each product and resolved transitively; duplicate identifiers, missing dependencies and cycles fail validation immediately.
- Processing booleans/defaults, dock labels/order and runtime selection now consume the same registry instead of maintaining three independent lists.
- Added explicit `register_products(registry)` module discovery for trusted extensions without implicit filesystem scanning.
- Added registry/discovery/contract tests, a custom-product pipeline test, release-workflow coverage and a dedicated product-extension guide.
- Preserved every v2.3 Processing parameter, default and output key.

## 2.3.0 — 2026-08-20

Maintainability release: smaller object-oriented services with the same v2.2 Processing and output contract.

- Extracted DEM reprojection and optional ROI clipping into `DemPreprocessor`, with a typed `PreparedDem` hand-off shared by every downstream product.
- Extracted TWI, landslide/RUSLE, SPI, STI and multi-hazard orchestration into `FlowProductBuilder`; flow-grid requirements are now validated in one place and analytical calculators can be injected for focused tests.
- Extracted QGIS task/context/feedback ownership from the dock into `ProcessingTaskController`, centralizing overlap prevention, progress delivery, cancellation and cleanup.
- Reduced the main package algorithm by roughly 300 lines while retaining parameter names, output keys, the v2.2 dependency plan and report provenance.
- Added pure unit coverage for flow-product dependency reuse and missing-accumulation failures.

## 2.2.0 — 2026-08-20

Pipeline correctness release: one preprocessed DEM, explicit dependencies and real drainage for every flow-driven product.

- Replaced the dock's two-task terrain-then-hydrology chain with one master dependency DAG: preprocess → hydrology → terrain/flow products → viewer/report → bundle → final manifest.
- Removed cached accumulation from previous runs and removed every slope-as-drainage fallback. Landslide hazard, SPI, STI and multi-hazard now auto-trigger hydrology when no compatible accumulation raster is supplied.
- Added a pure-Python `PipelinePlan` which records requested, effective and automatically enabled products; slope and TWI dependencies are resolved before processing starts.
- External accumulation rasters are validated against the preprocessed DEM CRS, dimensions and extent before use.
- Hydrology, flow indices, TWI, 3D viewer and intelligence report now share the same run outputs; the final JSON manifest is written after bundling and includes the complete output set and late warnings.
- Fixed hydrology reporting so river smoothing statistics no longer overwrite the D8/Strahler calculation summary.
- A stream threshold above the DEM contributing area now produces a valid empty stream layer and warning instead of aborting all hydrology outputs.

## 2.1.1 — 2026-08-20

Stable packaging and cartography hotfix.

- Removed the experimental flag and added release-archive validation so every installable ZIP has exactly one `terrain_product_studio/` root and includes `metadata.txt` plus the plugin entry points.
- Fixed print-layout grid frames on QGIS 3.x while retaining QGIS 4 scoped-enum compatibility.
- Fixed explicit A-series portrait/landscape page orientation.
- Added map recipes which prefer smoothed contours and rivers whenever available, while preserving raw analytical layers as hidden source data.
- Added Engineering Blueprint and Minimal Contour Poster map styles.
- Processing reports and DEM inspection now expose source/preprocessing choices and analytical assumptions.

## 2.1.0 — 2026-08-18

Cartography & workflow release: a real palette library, cleaner USA-standard maps, and a shareable QGIS project.

- **20-map palette library**: the color-relief combo now offers 20 ramps grouped **Classic** (USGS Classic, Natural Earth, Swiss Topo), **Artistic** (Imhof, Vintage Atlas, Copper Relief), **Environment** (Alpine, Desert, Tropical, Arctic), **Scientific** (Viridis, Turbo, Grayscale, Spectral) and **Dark Terrain** — six true dark ramps (Midnight Terrain, Dark Forest, Dark Alpine, Dark Copper, Dark Volcano, Dark Oceanic) whose elevation-anchored stops are written verbatim to the gdaldem color table, so they keep their intended contrast instead of just inverting the light colors.
- **Dark map styling**: selecting a Dark Terrain palette auto-switches the cartography theme to **Night Dark** — hillshade at 45% opacity, deep-ink canvas background `#090B0D`, cyan-gray contour lines with subdued alpha, cyan river network, all persisted into the saved project. Picking a light palette only reverts if the user had not chosen a manual light theme.
- **Peak-point density control**: new *Peak point threshold (% of relief)* setting — only summits whose elevation lies in the top N% of the terrain relief (default 80%) become spot-elevation markers; set to 0 (Off) to keep every local peak.
- **QGIS project creation**: new *Create QGIS project (.qgz)* option saves the current project with all layers, styling, groups and the print layout into the output folder — ready to reopen or share. The Layout Designer is **no longer auto-opened** after processing; the layout is created and saved, and the user opens it manually.
- **Default basemap**: generated layers default to a minimal visible stack (color relief, multi-hillshade, contours, peak points); hydrology (streams, ridges) and analytical groups load hidden for a clean first view.
- **USA-standard map logic**: grid annotations sit outside the map frame and always read horizontal (never rotated with the frame edge); raster layers carry no labels (labeling stays on contour / spot-elevation vectors only); river colors reworked — light themes use a deeper hydro-blue ramp, dark themes a cyan ramp; contour line weights increased slightly (0.15 / 0.35 / 0.55 mm) for a clearer print.

## 2.0.0 — 2026-08-18

Publication-grade release: smarter setup, deeper analysis, and shareable outputs.

- **Smart Setup Assistant (M0)**: contour interval is suggested from AOI scale and terrain relief (snapped to the standard `1/2/2.5/5/10/20/25/50/100` table) with a one-click Apply; palette combo now shows real gradient thumbnails; new **Dark / Night** cartographic theme with a live swatch preview; paper-size combo (A4/A3/A1 × orientation) with one-line layout summary.
- **Cartographic Smoothing (M1)**: Chaikin corner-cutting and Douglas–Peucker smoothing for contours and river networks — optional `SMOOTHING`/`SIMPLIFY_TOLERANCE` parameters on the algorithms and a smoothness combo in the dock.
- **New Analytical Products (M2)**: Geomorphon terrain forms (Jasiewicz & Stepinski 2013), Stream Power Index (SPI) and Sediment Transport Index (STI); **bugfix** — landslide hazard now uses the real flow accumulation grid instead of slope as a proxy (new optional `ACCUMULATION` input).
- **Multi-Hazard & Sharing (M3)**: weighted composite **multi-hazard index** (landslide × slope × TWI with user-adjustable weights) and a single **GeoPackage bundle** merging every generated raster and vector layer (byte rasters as lossless PNG tiles, float rasters via the OGC 2D-gridded-coverage extension) ready to share.
- **3D Printing & Workflow (M4)**: binary **STL / OBJ** export of the terrain (≤1024² auto-downsampling, z exaggeration, optional base-plate extrusion into a watertight solid); **industry presets** (Urban, Agriculture, Disaster, Mining) that tick the right product set in one click; **run history** journal in the QGIS profile — reopen the folder and intelligence report of any of the last 20 runs from the Inspect tab.
- Interactive 3D Web Viewer (from 1.2.0) extended with Z-up orbit controls.

## 1.2.0 — 2026-08-18

- **Resubmission after QGIS Plugin Repository security review**: version 1.1.0 is already registered on the repository, so the fully-fixed build (same code as 1.1.0) is published under 1.2.0. Every finding from the automated scan that blocked the previous upload is resolved — Bandit B110 (silent exception handlers now report errors or use safe defaults), Bandit B608 (SQL-injection false positive removed by moving the HTML template to a module constant), Flake8 F821 (missing `from osgeo import gdal` import in the package builder), and 18 Qt6 scoped-enum usages made static-analysis-safe with `getattr()` fallbacks.

## 1.1.0 — 2026-08-18

- **Run button no longer hidden**: dock body is wrapped in a `QScrollArea`, so the progress bar and Build/Cancel buttons stay reachable when QGIS docks the panel into a small area (previously clipped with the fixed 480×810 dock).
- **Compact Products tab**: product checkboxes arranged in a 2-column grid with word-wrapping labels — halves the tab height and keeps the whole dock short.
- **Faster dock startup (~40% quicker)**: system font scanning is deferred until the Layout tab is first opened instead of enumerating 180+ fonts at dock construction (~390 ms → ~210 ms).
- **Test coverage**: added `tests/qgis_ui_render_check.py` (offscreen render check that the Run button is scroll-reachable at any dock size); updated stale UI-probe and smoke-test expectations (15 products, `terrainstudio:buildhydrology`).
- **QGIS Plugin Repository security scan: PASS**: fixed all blockers from the automated review — replaced 13 silent `try-except-pass` blocks with explicit error reporting or safe defaults (Bandit B110), removed the SQL-injection heuristic false positive by moving the HTML template to a module constant (B608), added the missing `from osgeo import gdal` import in the package builder (Flake8 F821 — a real bug where the fallback path silently hid a NameError), and made 18 Qt6 scoped-enum usages static-analysis-safe with `getattr()` fallbacks that still run on PyQt5.
- **Requirement change**: `qgisMinimumVersion` raised from 3.0 to 3.34 — the plugin now requires a QGIS version that ships Qt 5.15 (the scoped-enum fallbacks target QGIS 4 / Qt 6 and modern 3.x).

## 1.0.0 — 2026-08-17

- **QGIS Publishing Compliance**: License updated to GNU GPL v2.0-or-later; updated `metadata.txt` with required author, email, repository, homepage, and tracker fields.
- **USGS Authentic Cartography**: Implemented authentic USGS Topographic map specifications for 3-tier contours (minor 0.12mm, index 0.30mm, master 0.48mm), italic labels with clean background halos, and USGS hydro blue (`#0070c0`).
- **New Terrain Layer Products**: Added Spot Elevation Peak Markers (triangle markers with peak heights), Profile Curvature (flow acceleration), Planform Curvature (flow convergence), and Ridgeline network extraction.
- **Layer Stacking Fix**: Reordered QGIS Layer Panel groups so vector layers (hydrology, contours, peaks) render on top of raster hillshade and elevation basemaps.
- **Internationalization (i18n)**: English default UI across all dialogs, tabs, and processing algorithm descriptions; added Qt translation system (`i18n/terrain_product_studio_vi.ts`) for seamless Vietnamese localization based on QGIS application locale.
- **Clean Packaging**: Added `scripts/package_plugin.py` to create lightweight releases under 25 MB.

## 0.1.1 — 2026-08-16

- Fixed opening the dock on QGIS 4 / Qt 6 by supporting scoped Qt enums.
- Verified the complete GUI lifecycle in `QGIS-master-026d9cd.app` (4.3.0-Master).
- Verified installation from ZIP in a clean QGIS profile.

## 0.1.0 — 2026-08-16

- Initial QGIS Processing Provider and dock interface.
- DEM inspection with statistics, NoData and CRS warnings.
- Automatic local UTM working raster for geographic DEMs.
- Color relief, standard/multidirectional hillshade, slope, aspect, TRI, TPI, roughness and contours.
- Automatic layer groups, hillshade blending, analytical color ramps and minor/index contour styling.
- Non-overwriting file output and JSON processing report.
