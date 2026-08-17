# Terrain Product Studio

QGIS Processing Plugin by **Nguyễn Văn Tín** ([@hulauwa](https://github.com/hulauwa))

Turns a single Digital Elevation Model (DEM) into a complete, publication-ready cartographic and analytical terrain package styled with authentic USGS topographic map conventions.

## Repository Structure

- [`terrain_product_studio`](terrain_product_studio): Plugin source code
- [`scripts/package_plugin.py`](scripts/package_plugin.py): Packaging script for QGIS Repository uploads
- [`tests`](tests): Unit test suite
- [`dist`](dist): Build zip artifacts (< 25 MB)

## Quick Build & Package

To build a clean QGIS-compliant ZIP package:

```bash
python3 scripts/package_plugin.py
```

ZIP output: `dist/terrain_product_studio-1.0.0.zip`

## License

GNU General Public License v2.0 or later (GPLv2+)
