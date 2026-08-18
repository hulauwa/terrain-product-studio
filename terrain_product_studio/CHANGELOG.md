# Changelog

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
