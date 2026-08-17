# Terrain Product Studio

[![QGIS Version](https://img.shields.io/badge/QGIS-3.34%2B-brightgreen.svg)](https://qgis.org)
[![License](https://img.shields.io/badge/License-GPLv2-blue.svg)](LICENSE)

**Terrain Product Studio** is a QGIS Processing plugin that turns one Digital Elevation Model (DEM/DTM) into a publication-ready terrain map product package. It generates raw analytical rasters alongside a cartographic layer stack formatted with USGS-authentic cartography, 3-tier contours, spot elevation peak markers, hydrology, and automatic print layouts.

## Features & Products

- **USGS Topographic Styling**: Brown hypsographic 3-tier contours (minor 0.12mm, index 0.30mm, master 0.48mm), italic curved labels with soft halos, and hydrography blue (`#0070c0`).
- **Elevation Color Relief**: 5 curated cartographic palettes (USGS Classic Topo, Antique American Survey, Natural, Muted, Atlas, Grayscale).
- **Hillshading**: Standard single-light and multidirectional hillshade with multiply blend mode.
- **Spot Elevation Peak Markers**: Automatic local elevation peak detection (triangle markers with elevation labels).
- **Curvature Derivatives**: Profile curvature (flow acceleration/deceleration) and Planform curvature (flow convergence/divergence).
- **Hydrology & Drainage**: Priority-flood depression filling, D8 flow direction, flow accumulation, basin partitioning, ridgeline extraction, and potential stream networks.
- **Print Layout Composer**: One-click generation of formatted map layouts with grids, scale bar, north arrow, legend, metadata, and PDF/PNG export.
- **Layer Stacking**: Vector layers (hydrology, contours, peaks) automatically render on top of raster hillshades and color relief.
- **Internationalization (i18n)**: Default English interface with automatic Vietnamese translation based on QGIS application locale.

## Requirements

- QGIS 3.34 or newer (compatible with QGIS 4 / Qt 6)
- Built-in GDAL Processing provider enabled
- Standard QGIS Python installation (no extra dependencies required)

## Installation

1. Download `dist/terrain_product_studio-1.0.0.zip`.
2. In QGIS, navigate to **Plugins → Manage and Install Plugins… → Install from ZIP**.
3. Select `terrain_product_studio-1.0.0.zip` and click **Install Plugin**.
4. Access the plugin via **Raster → Terrain Product Studio** or the toolbar terrain icon.

## License

This plugin is licensed under the [GNU General Public License v2.0 or later](LICENSE).
