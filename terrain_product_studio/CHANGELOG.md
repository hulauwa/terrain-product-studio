# Changelog

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
