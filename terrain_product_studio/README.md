# Terrain Product Studio

[![QGIS Version](https://img.shields.io/badge/QGIS-3.34%2B-brightgreen.svg)](https://qgis.org)
[![License](https://img.shields.io/badge/License-GPLv2-blue.svg)](LICENSE)

**Terrain Product Studio** is a QGIS Processing plugin that turns one Digital Elevation Model (DEM/DTM) into a publication-ready terrain map product package. It generates raw analytical rasters alongside a cartographic layer stack formatted with USGS-authentic cartography, 3-tier contours, spot elevation peak markers, hydrology, and automatic print layouts.

## Features & Products

- **Smart Setup Assistant**: contour interval suggested from AOI scale and relief (snapped to the standard `1/2/2.5/5/10/20/25/50/100` table) with one-click Apply; palette combo shows gradient thumbnails; Dark / Night theme with live swatch preview; paper-size combo for the print layout.
- **USGS Topographic Styling**: Brown hypsographic 3-tier contours (minor 0.12mm, index 0.30mm, master 0.48mm), italic curved labels with soft halos, and hydrography blue (`#0070c0`).
- **Elevation Color Relief**: 6 curated cartographic palettes (USGS Classic Topo, Antique American Survey, Natural, Muted, Atlas, Grayscale, Dark Night Terrain).
- **Hillshading**: Standard single-light and multidirectional hillshade with multiply blend mode.
- **Geomorphometry**: Slope, aspect, TRI, TPI, roughness, profile/planform curvature, geomorphon terrain forms, SPI and STI, spot elevation peak markers, ridge/valley networks.
- **Hydrology & Drainage**: Priority-flood depression filling, D8 flow direction, flow accumulation, basin partitioning, and smoothed potential stream networks.
- **Hazard Analysis**: Landslide hazard risk (uses the real flow-accumulation grid) and a weighted **multi-hazard composite index** (landslide × slope × TWI) with adjustable weights.
- **Cartographic Smoothing**: Chaikin corner-cutting and Douglas–Peucker simplification for contours and rivers.
- **Industry Presets**: One click ticks the right product set for Urban, Agriculture, Disaster or Mining workflows.
- **GeoPackage Bundle**: All rasters and vectors merged into one shareable `.gpkg` (lossless PNG tiles for byte rasters, OGC 2D-gridded-coverage for float rasters).
- **3D Web Viewer**: Interactive web scene of the terrain (Z-up orbit controls) saved alongside the products.
- **STL / OBJ Export**: Watertight, 3D-printable mesh of the terrain — auto-downsampling, z exaggeration, optional base plate.
- **Run History**: Journal of the last 20 runs in the QGIS profile; reopen folder and intelligence report from the Inspect tab.
- **Print Layout Composer**: One-click generation of formatted map layouts with grids, scale bar, north arrow, legend, metadata, and PDF/PNG export.
- **Layer Stacking**: Vector layers (hydrology, contours, peaks) automatically render on top of raster hillshades and color relief.
- **Internationalization (i18n)**: Default English interface with automatic Vietnamese translation based on QGIS application locale.

## Requirements

- QGIS 3.34 or newer (compatible with QGIS 4 / Qt 6)
- Built-in GDAL Processing provider enabled
- Standard QGIS Python installation (no extra dependencies required)

## Installation

1. Download `terrain_product_studio-2.3.0.zip` from the GitHub **Releases** page. Do not use GitHub's repository source ZIP.
2. In QGIS, navigate to **Plugins → Manage and Install Plugins… → Install from ZIP**.
3. Select `terrain_product_studio-2.3.0.zip` and click **Install Plugin**.
4. Access the plugin via **Raster → Terrain Product Studio** or the toolbar terrain icon.

## License

This plugin is licensed under the [GNU General Public License v2.0 or later](LICENSE).
