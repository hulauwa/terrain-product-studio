# 🏔️ Terrain Product Studio

[![QGIS 3 & 4 Compatible](https://img.shields.io/badge/QGIS-3.34%2B%20%7C%204.x%20(Qt6)-brightgreen.svg)](https://qgis.org)
[![Python 3.9+](https://img.shields.io/badge/Python-3.9%2B-blue.svg)](https://python.org)
[![License: GPL v2+](https://img.shields.io/badge/License-GPL%20v2%2B-orange.svg)](https://www.gnu.org/licenses/gpl-2.0.html)
[![Author](https://img.shields.io/badge/Author-Nguy%E1%BB%85n%20V%C4%83n%20T%C3%ADn-blueviolet.svg)](https://github.com/hulauwa)

> **Turn any single Digital Elevation Model (DEM) into a complete, publication-ready cartographic suite, hydrological network, environmental risk assessment, interactive 3D WebGIS studio, and automated intelligence report in a single click.**

[🇻🇳 Đọc Hướng Dẫn & Tài Liệu Bằng Tiếng Việt (README_VI.md)](README_VI.md)

---

## 📑 Table of Contents
- [🌟 Key Highlights](#-key-highlights)
- [📦 Generated Product Portfolio](#-generated-product-portfolio)
  - [1. Geomorphometry & Analytical Derivatives](#1-geomorphometry--analytical-derivatives)
  - [2. Hydrology & River Network](#2-hydrology--river-network)
  - [3. Geotechnical & Environmental Risk Assessment](#3-geotechnical--environmental-risk-assessment)
  - [4. Publication-Grade Cartography](#4-publication-grade-cartography)
  - [5. Standalone 3D WebGIS Interactive Studio](#5-standalone-3d-webgis-interactive-studio)
  - [6. Topographic Intelligence Summary Report](#6-topographic-intelligence-summary-report)
- [🎯 Scale-Aware Intelligence & Processing Extent](#-scale-aware-intelligence--processing-extent)
- [🚀 Installation](#-installation)
- [📖 User Guide](#-user-guide)
- [🛠️ Architecture & Compatibility](#️-architecture--compatibility)
- [📜 License & Citation](#-license--citation)

---

## 🌟 Key Highlights

- **Zero Data Distortion**: Raw analytical derivatives maintain real floating-point physical units (degrees, radians, meters, index scores) while cartographic layers receive styling.
- **Smart Setup Assistant**: Contour interval suggested from AOI scale and relief (snapped to the standard `1/2/2.5/5/10/20/25/50/100` table) with one-click Apply; **20-map palette library** with gradient thumbnails grouped Classic / Artistic / Environment / Scientific / **Dark Terrain** (six true dark ramps with elevation-anchored stops that auto-switch to the Night Dark cartography theme); live swatch preview.
- **Continuous Strahler Polyline Network**: Advanced D8 topological tracing extracts smooth, continuous vector streams with rich hydraulic attributes (`ORDER`, `LENGTH_M`, `AREA_HA`) — now with optional Chaikin / Douglas–Peucker cartographic smoothing.
- **Dependency-Safe One-Click Pipeline**: The DEM is preprocessed once, hydrology runs before SPI/STI/landslide/multi-hazard products, and slope/TWI dependencies are auto-enabled explicitly. No cached accumulation or slope drainage proxy is used.
- **Multi-Hazard Composite & Shareable Bundle**: Weighted landslide × slope × TWI composite index, exported together with every raster and vector layer into **one GeoPackage** (lossless PNG tiles for byte rasters, OGC 2D-gridded-coverage for float rasters).
- **3D Printing & Workflow**: STL/OBJ mesh export (auto-downsampling, z exaggeration, watertight base plate), one-click industry presets (Urban / Agriculture / Disaster / Mining), a run-history journal (last 20 jobs reopenable from the Inspect tab), and one-click **QGIS project (.qgz)** export that saves every layer, style, group and print layout into the output folder.
- **Map Design Studio**: choose layout template, map style and elevation palette independently; reusable QML and any number of independently styled layouts in a drag-reorder map-book queue. Reserved safe zones prevent map furniture overlap.
- **Real-Time 3D WebGIS Studio (`.html`)**: quality-selectable WebGL terrain viewer with correct map aspect/coordinates, concurrent raster preparation and direct user-selected GeoTIFF/COG or GeoJSON loading.
- **Topographic Intelligence Report (`.html`)**: Executive summary dashboard featuring SVG Aspect Rose radar charts, hypsometric histograms, and TCVN geotechnical matrices.
- **Dual QGIS 3 (Qt5) & QGIS 4 (Qt6) Compatibility**: Fully verified against scoped enum architectures and modern Python 3.12+ environments.

---

## 📦 Generated Product Portfolio

### 1. Geomorphometry & Analytical Derivatives

| Derivative | Method / Formula | Scientific & Engineering Significance |
| :--- | :--- | :--- |
| **Slope** | Horn (1981) / Zevenbergen & Thorne (1987) | Gradient steepness (°/rad). Essential for slope stability, road alignment, earthwork calculation. |
| **Aspect** | 360° Cardinal Orientation | Solar exposure, microclimate classification, vegetation distribution, windward/leeward analysis. |
| **TRI** | Riley et al. (1999) $\sqrt{\sum (z_{ij} - z_{00})^2}$ | Terrain Ruggedness Index: Quantifies local elevation variance for biodiversity and mobility analysis. |
| **TPI** | Guisan et al. (1999) $z_0 - \bar{z}$ | Topographic Position Index: Distinguishes ridge tops, upper slopes, flat plains, and valley bottoms. |
| **Roughness** | $\max(z_{ij}) - \min(z_{ij})$ | Morphological roughness within $3\times3$ kernel. |
| **Curvatures** | Profile & Planform | Flow acceleration (profile) and flow convergence/divergence (planform). |
| **Geomorphon** | Jasiewicz & Stepinski (2013) | 10-terrain-form classification (flat, peak, ridge, slope, valley, pit...) by line-of-sight angle comparison. |
| **SPI** | Moore et al. (1991) $A_s \tan \beta$ | Stream Power Index: erosive power of concentrated flow. |
| **STI** | Sediment Transport Index | Relative sediment flux — erodibility hot spots for soil conservation planning. |

### 2. Hydrology & River Network

- **D8 Flow Direction & Flow Accumulation**: Resolves single-flow direction routing and contributing upslope drainage area ($ha, km^2$).
- **Continuous Strahler Polyline River Network**: ordered by stream class with a clear hydro-blue ramp on light themes (`#74c0e6` → `#0b4489`) and a cyan ramp on dark themes (`#9be1ff` → `#0f7fc9`) so rivers always read against the terrain.
- **Catchment Watershed Basins**: Polygonized micro-basin delineations with automated color palette assignment.
- **Topographic Wetness Index (TWI)**:
  $$\text{TWI} = \ln\left(\frac{A}{\tan \beta}\right)$$
  Quantifies relative soil moisture, groundwater accumulation zones, and wetland potential.

### 3. Geotechnical & Environmental Risk Assessment

- **Urban Construction Suitability (TCVN 4447:2012)**:
  - *Class 1 ($< 3^\circ$)*: Highly Suitable / Flat land (`#2ca25f`).
  - *Class 2 ($3^\circ - 8^\circ$)*: Suitable / Gentle slope (`#99d8c9`).
  - *Class 3 ($8^\circ - 15^\circ$)*: Moderate / Grading required (`#fed976`).
  - *Class 4 ($15^\circ - 25^\circ$)*: Restricted / Steep terrain (`#fd8d3c`).
  - *Class 5 ($> 25^\circ$)*: Unsuitable / Conservation zone (`#e31a1c`).
- **Landslide Hazard & RUSLE LS-Factor**:
  - Topographic length-slope factor $(LS)$ combined with slope angles to classify erosion severity and landslide potential (uses the real flow-accumulation grid).
- **Multi-Hazard Composite Index**:
  - Weighted combination of landslide hazard × slope × TWI (user-adjustable weights) into a single composite risk raster with 4 severity classes.
- **GeoPackage Bundle**:
  - Every raster and vector product merged into **one `.gpkg`** file ready to share (byte rasters as lossless PNG tiles, float rasters via the OGC 2D-gridded-coverage extension).

### 4. Publication-Grade Cartography

- **3-Tier USGS Topographic Contours**:
  - *Minor Contours*: $0.15\text{ mm}$ fine lines at standard interval.
  - *Index Contours*: $0.35\text{ mm}$ bold lines with elevation labels every 5th line.
  - *Master Contours*: $0.55\text{ mm}$ prominent boundary lines.
- **20-Map Palette Library**: color relief from **Classic** (USGS Classic, Natural Earth, Swiss Topo), **Artistic** (Imhof, Vintage Atlas, Copper Relief), **Environment** (Alpine, Desert, Tropical, Arctic), **Scientific** (Viridis, Turbo, Grayscale, Spectral) and **Dark Terrain** (Midnight Terrain, Dark Forest, Dark Alpine, Dark Copper, Dark Volcano, Dark Oceanic) — dark ramps use elevation-anchored stops and pair with the Night Dark theme (45% hillshade, `#090B0D` canvas, cyan contours & rivers).
- **Creative Map Recipes**: **Engineering Blueprint** builds a navy/cyan technical linework map, while **Minimal Contour Poster** keeps only the essential contour, water and spot-elevation layers. Smoothed vectors replace raw copies in the visible stack; raw data remains loaded but hidden.
- **Spot Elevation Peaks**: Morphologically isolated local summits filtered by minimum prominence and col distance, plus a **relief-percent threshold** (default top 80% of the elevation range) that keeps only the summits worth labeling; styled with elevation badges.
- **Hypsometric Color Relief & Multidirectional Hillshade**: 4-azimuth blended lighting ($225^\circ, 270^\circ, 315^\circ, 360^\circ$) eliminates directional shadow bias.
- **USA-Standard Map Logic**: grid annotations sit outside the map frame and always read horizontal; raster layers never carry labels (labeling stays on contour / spot-elevation vectors); cartographic layer names follow USGS naming conventions.
- **QGIS Project Export**: one click writes the current project as a `.qgz` into the output folder with all layers, styles, groups and the print layout — the Layout Designer itself is created but left for you to open manually.
- **Cartographic Smoothing**: Chaikin corner-cutting (rounding) and Douglas–Peucker simplification for both contours and river networks — a `SMOOTHING` combo on the Products tab.

---

### 5. Standalone 3D WebGIS Interactive Studio

Generated as a zero-dependency HTML file (`<prefix>_interactive_3d_terrain.html`):

```
┌────────────────────────────────────────────────────────────────────────┐
│  🏔️ 3D INTERACTIVE WEBGIS STUDIO                                      │
│  ├── 🎨 Base Draping: Topo | Slope | TWI | Suitability | Hazard | Shaded│
│  ├── 🌊 Real-Time Flood Simulation: Dynamic water slider & ha stats    │
│  ├── ✂️ Cross-Section Profile Tool: Click A→B with instant SVG chart   │
│  ├── ☀️ Solar Shadow Engine: SPA algorithm with Sunrise-Sunset loop    │
│  ├── 🤖 AI Terrain Assistant: Natural language queries on peaks/hazards│
│  ├── 🚁 Drone Flythrough: Smooth Catmull-Rom spline camera navigation  │
│  └── 🔍 Live Surface Inspector: Hover Z, Slope, TWI, Landslide Risk    │
└────────────────────────────────────────────────────────────────────────┘
```

---

### 6. Topographic Intelligence Summary Report

Generated as an executive HTML dashboard (`<prefix>_topographic_intelligence_report.html`):
- **🧭 Aspect Rose**: Polar radar chart showing slope distribution across 8 cardinal directions.
- **📈 Hypsometric Distribution**: 10-bin frequency histogram of elevation relief.
- **🌊 Strahler Drainage Structure**: Length ($km$) and percentage breakdown across stream orders.
- **🏛️ & ⚠️ Geotechnical Matrices**: Tabular breakdown of construction land suitability and landslide hazard risk.
- **🖨️ One-Click Print / PDF Export**: Formatted CSS optimized for engineering reports.

---

### 7. 3D Printing & Workflow Automation

- **STL / OBJ Mesh Export**: Binary STL or OBJ+MTL of the terrain, ready for 3D printers — automatic downsampling above $1024^2$ cells, z-exaggeration factor, and optional base-plate extrusion that makes the mesh a **watertight solid**.
- **Industry Presets**: One click ticks the right product set — *Urban / Construction*, *Agriculture*, *Disaster management*, *Mining / Infrastructure* — or stay on *Custom selection*.
- **Run History**: The last 20 runs are journaled in the QGIS profile; reopen the output folder and intelligence report straight from the Inspect tab.

---

## 🎯 Scale-Aware Intelligence & Processing Extent

1. **Processing Extent Modes**:
   - `Full DEM Layer Extent`: Process the entire raster bounding box.
   - `Current Map Canvas Extent`: Real-time ROI clipping matching the active QGIS map view.
   - `Calculate from Another Layer Extent`: Automatically crop to an administrative or project boundary polygon.
2. **Scale-Aware Heuristic Recommendations**:
   - Detects spatial pixel resolution and suggests optimal map scale ($1:5,000$ to $1:250,000$), recommended contour intervals ($2.5\text{ m}, 5\text{ m}, 10\text{ m}, 20\text{ m}$), and summit peak sampling density.

---

## 🚀 Installation

### Option A: Install via QGIS Plugin Manager
1. Download the latest `terrain_product_studio-2.7.0.zip` from [Releases](https://github.com/hulauwa/terrain-product-studio/releases).
2. Open QGIS $\rightarrow$ **Plugins** $\rightarrow$ **Manage and Install Plugins...**
3. Select **Install from ZIP** $\rightarrow$ choose the downloaded `.zip` file $\rightarrow$ Click **Install Plugin**.

> Do **not** install GitHub's **Code → Download ZIP** archive. It contains the repository wrapper, not an installable QGIS plugin. Use the versioned ZIP under **Releases**; it contains `terrain_product_studio/metadata.txt` at the required location.

> **v2.7.0**: Six lightweight previewed design presets bundle layout, QGIS layer style, numeric DEM palette and grid choice. The recommended default stays simple; advanced controls remain optional. Exported layouts now re-lock their safe zones after QGIS fits the map extent, preventing furniture overlap.

### Option B: Manual Installation
Copy the `terrain_product_studio` directory into your QGIS active profile plugin folder:
- **macOS**: `~/Library/Application Support/QGIS/QGIS4/profiles/default/python/plugins/`
- **Windows**: `%APPDATA%\QGIS\QGIS3\profiles\default\python\plugins\`
- **Linux**: `~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/`

---

## 📖 User Guide

1. Open the plugin dock from **Raster** $\rightarrow$ **Terrain Product Studio** $\rightarrow$ **Terrain Product Studio Panel** (or click the toolbar icon).
2. **1 · Input Data**: Select your DEM raster layer and elevation band. Click **Inspect DEM** for scale and contour recommendations.
3. **2 · Processing Extent**: Choose between *Full DEM*, *Current Map Canvas*, or a specific *Boundary Layer*.
4. **3 · Output**: Specify your destination folder (defaults to plugin's `temp/` folder) and custom file prefix.
5. **Tabs**:
   - **Products**: Pick an **industry preset** (Urban / Agriculture / Disaster / Mining) or check products manually; configure smoothing and the composite-index weights; tick **Create QGIS project (.qgz)** to save the styled project next to the outputs.
   - **Contours**: Adjust contour interval and index multiplier, and the **peak point threshold (% of relief)** — only summits in the top N% of the elevation range become spot markers (0 = Off).
   - **Hydrology**: Enable drainage extraction and set stream initiation threshold ($ha$).
   - **Layout**: Choose a layout template and map style independently, check readiness, add designs to the map-book queue and generate PDF/PNG layouts. Elevation colors remain independently selectable under **Settings**.
   - **Settings**: Choose Web 3D quality and configure Z-exaggeration/base thickness for the **STL/OBJ 3D-print export**.
   - **Inspect**: Reopen the output folder / intelligence report of any of the last 20 runs.
6. Click **Build Product Package**.
7. Once finished, click **🌐 View 3D Web Map** or **📊 View Report** to launch the interactive deliverables in your default browser.

---

## 🛠️ Architecture & Compatibility

```
terrain_product_studio/
├── algorithms/
│   ├── build_package.py       # Main Processing algorithm: full product package
│   ├── build_hydrology.py     # Hydrology & drainage Processing algorithm
│   └── inspect_dem.py         # DEM inspection algorithm
├── core/
│   ├── bundle.py              # Single-GeoPackage merge (rasters + vectors)
│   ├── dem_info.py            # Inspection heuristics & scale recommendations
│   ├── export_3d.py           # Binary STL / OBJ mesh export (watertight)
│   ├── geomorphon.py          # Jasiewicz & Stepinski terrain forms
│   ├── history.py             # Run-history journal (last 20 jobs)
│   ├── intelligence_report.py # Topographic Intelligence HTML generator
│   ├── layers.py              # Project layer stacking & grouping
│   ├── layouts.py             # Print layout composer (paper size, themes)
│   ├── layout_styles.py       # Per-layout style snapshots and QML export
│   ├── style_packs.py         # Cohesive style-pack and layout-template model
│   ├── cartography_qa.py      # Map readiness and recipe explanations
│   ├── share_package.py       # Transparent share-package manifest
│   ├── math_utils.py          # nice_interval, snapping, prefix sanitizing
│   ├── native_hydrology.py    # D8 routing & Continuous Strahler tracing
│   ├── pipeline.py            # Product dependency planner
│   ├── product_registry.py    # Product declarations, validation and discovery
│   ├── preprocessing.py       # DEM reprojection and ROI clipping service
│   ├── flow_products.py       # TWI, SPI/STI and hazard product builder
│   ├── presets.py             # Terrain palettes, cartography themes, industry presets
│   ├── qgis_compat.py         # Qt5 / Qt6 & QGIS 3 / 4 dual compatibility
│   ├── smoothing.py           # Chaikin & Douglas–Peucker line smoothing
│   ├── spot_elevations.py     # Peak detection & prominence filtering
│   ├── styles.py              # Automated styling & symbology rules
│   ├── thematic_terrain.py    # TCVN Suitability, landslide, multi-hazard, SPI/STI
│   └── web_3d_viewer.py       # WebGL 3D Interactive WebGIS Studio generator
├── ui/task_controller.py      # Async Processing task lifecycle
├── dock.py                    # Dock widget composition and result presentation
└── plugin.py                  # Plugin entry point & menu registration
```

---

## 📜 License & Citation

Licensed under the **GNU General Public License v2.0 or later (GPLv2+)**.

Developed by **Nguyễn Văn Tín** ([@hulauwa](https://github.com/hulauwa)). Contributions, bug reports, and feature requests are warmly welcomed via GitHub Issues.

Contributor and AI-agent product integration steps are documented in [`docs/EXTENDING_PRODUCTS.md`](docs/EXTENDING_PRODUCTS.md).
