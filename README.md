# 🏔️ Terrain Product Studio

[![QGIS 3 & 4 Compatible](https://img.shields.io/badge/QGIS-3.28%2B%20%7C%204.x%20(Qt6)-brightgreen.svg)](https://qgis.org)
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
- **Continuous Strahler Polyline Network**: Advanced D8 topological tracing extracts smooth, continuous vector streams with rich hydraulic attributes (`ORDER`, `LENGTH_M`, `AREA_HA`).
- **Real-Time 3D WebGIS Studio (`.html`)**: Self-contained WebGL 3D terrain viewer with flood simulation, live profile cross-sections, solar shadow time-lapse, drone flythrough, and AI Q&A assistant.
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

### 2. Hydrology & River Network

- **D8 Flow Direction & Flow Accumulation**: Resolves single-flow direction routing and contributing upslope drainage area ($ha, km^2$).
- **Continuous Strahler Polyline River Network**:
  - *Order 1 (Headwater Stream)*: Thin hairline $0.28\text{ mm}$, light cyan `#6baed6`.
  - *Order 2 (Secondary Tributary)*: Medium $0.52\text{ mm}$, intermediate blue `#3182bd`.
  - *Order 3 (Sub-River Channel)*: Bold $0.85\text{ mm}$, navy `#08519c`.
  - *Order 4+ (Major River Channel)*: Strong $1.30\text{ mm}$, deep oceanic `#08306b`.
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
  - Topographic length-slope factor $(LS)$ combined with slope angles to classify erosion severity and landslide potential.

### 4. Publication-Grade Cartography

- **3-Tier USGS Topographic Contours**:
  - *Minor Contours*: $0.18\text{ mm}$ fine lines at standard interval.
  - *Index Contours*: $0.42\text{ mm}$ bold lines with elevation labels every 5th line.
  - *Master Contours*: $0.65\text{ mm}$ prominent boundary lines.
- **Spot Elevation Peaks**: Morphologically isolated local summits filtered by minimum prominence and col distance, styled with elevation badges.
- **Hypsometric Color Relief & Multidirectional Hillshade**: 4-azimuth blended lighting ($225^\circ, 270^\circ, 315^\circ, 360^\circ$) eliminates directional shadow bias.

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
1. Download the latest `terrain_product_studio-1.0.0.zip` from [Releases](https://github.com/hulauwa/terrain-product-studio/releases).
2. Open QGIS $\rightarrow$ **Plugins** $\rightarrow$ **Manage and Install Plugins...**
3. Select **Install from ZIP** $\rightarrow$ choose the downloaded `.zip` file $\rightarrow$ Click **Install Plugin**.

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
   - **Products**: Check desired analytical rasters, 3D WebGIS Studio, and Intelligence Report.
   - **Contours**: Adjust contour interval and index multiplier.
   - **Hydrology**: Enable drainage extraction and set stream initiation threshold ($ha$).
   - **Layout**: Configure automated print layout generation and PDF/PNG export.
6. Click **Build Product Package**.
7. Once finished, click **🌐 View 3D Web Map** or **📊 View Report** to launch the interactive deliverables in your default browser.

---

## 🛠️ Architecture & Compatibility

```
terrain_product_studio/
├── algorithms/
│   ├── build_package.py       # Main Processing Provider algorithm (Terrain)
│   └── build_hydrology.py     # Hydrology & Drainage Processing algorithm
├── core/
│   ├── dem_info.py            # Inspection heuristics & scale recommendations
│   ├── intelligence_report.py # Topographic Intelligence HTML generator
│   ├── native_hydrology.py    # D8 routing & Continuous Strahler tracing
│   ├── qgis_compat.py         # Qt5 / Qt6 & QGIS 3 / 4 dual compatibility
│   ├── spot_elevations.py     # Peak detection & prominence filtering
│   ├── styles.py              # Automated styling & symbology rules
│   ├── thematic_terrain.py    # TCVN Suitability & Landslide LS algorithms
│   └── web_3d_viewer.py       # WebGL 3D Interactive WebGIS Studio generator
├── dock.py                    # Dock widget UI & reactive signal controller
└── plugin.py                  # Plugin entry point & menu registration
```

---

## 📜 License & Citation

Licensed under the **GNU General Public License v2.0 or later (GPLv2+)**.

Developed by **Nguyễn Văn Tín** ([@hulauwa](https://github.com/hulauwa)). Contributions, bug reports, and feature requests are warmly welcomed via GitHub Issues.
