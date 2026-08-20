#!/usr/bin/env python3
"""Render lightweight design-preset thumbnails from a small DEM crop.

Run with the Python bundled by QGIS. The source DEM and temporary crop are
never packaged; only compressed JPEG previews are written into the plugin.
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
import tempfile

from osgeo import gdal
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QImage
from qgis.core import QgsApplication, QgsProject, QgsRasterLayer

from terrain_product_studio.core.design_presets import DESIGN_PRESETS
from terrain_product_studio.core.layouts import create_terrain_layout


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_DEM = "/Users/estasnino/Downloads/Lai Chau_DEM.tif"
PREVIEW_DIR = os.path.join(
    ROOT, "terrain_product_studio", "assets", "preset_previews"
)


def _small_central_crop(source_path, destination):
    source = gdal.Open(source_path, gdal.GA_ReadOnly)
    if source is None:
        raise RuntimeError(f"Could not open DEM: {source_path}")
    crop_width = min(1400, source.RasterXSize)
    crop_height = min(1000, source.RasterYSize)
    x_offset = max(0, (source.RasterXSize - crop_width) // 2)
    y_offset = max(0, (source.RasterYSize - crop_height) // 2)
    options = gdal.TranslateOptions(
        format="GTiff",
        srcWin=(x_offset, y_offset, crop_width, crop_height),
        width=560,
        height=400,
        resampleAlg="bilinear",
        creationOptions=("COMPRESS=DEFLATE", "TILED=YES"),
    )
    cropped = gdal.Translate(destination, source, options=options)
    source = None
    if cropped is None:
        raise RuntimeError("Could not create preview DEM crop")
    cropped = None
    return destination


def _save_small_jpeg(source_png, destination):
    image = QImage(source_png)
    if image.isNull():
        raise RuntimeError(f"Could not read rendered preview: {source_png}")
    try:
        aspect = Qt.AspectRatioMode.KeepAspectRatio
        transform = Qt.TransformationMode.SmoothTransformation
    except AttributeError:
        aspect = getattr(Qt, "KeepAspectRatio")
        transform = getattr(Qt, "SmoothTransformation")
    image = image.scaled(420, 300, aspect, transform)
    if not image.save(destination, "JPEG", 68):
        raise RuntimeError(f"Could not write preview: {destination}")


def generate(source_dem):
    os.makedirs(PREVIEW_DIR, exist_ok=True)
    temp_dir = tempfile.mkdtemp(prefix="tps_preset_previews_")
    project = QgsProject.instance()
    try:
        dem_path = _small_central_crop(
            source_dem, os.path.join(temp_dir, "lai_chau_preview_dem.tif")
        )
        hillshade_path = os.path.join(temp_dir, "lai_chau_preview_hillshade.tif")
        result = gdal.DEMProcessing(
            hillshade_path,
            dem_path,
            "hillshade",
            format="GTiff",
            computeEdges=True,
            multiDirectional=True,
            creationOptions=("COMPRESS=DEFLATE", "TILED=YES"),
        )
        if result is None:
            raise RuntimeError("Could not create preview hillshade")
        result = None

        dem_layer = QgsRasterLayer(dem_path, "Elevation")
        hillshade_layer = QgsRasterLayer(hillshade_path, "Multidirectional hillshade")
        if not dem_layer.isValid() or not hillshade_layer.isValid():
            raise RuntimeError("Preview raster layers are invalid")
        project.addMapLayers([dem_layer, hillshade_layer])
        layers = {
            "WORKING_DEM": dem_layer,
            "MULTI_HILLSHADE": hillshade_layer,
        }
        north_arrow = os.path.join(
            ROOT, "terrain_product_studio", "icons", "north_arrow_classic.svg"
        )
        for design in DESIGN_PRESETS.values():
            config = {
                "preset": design.map_style,
                "design_preset": design.key,
                "layout_template": design.layout_template,
                "palette_key": design.palette,
                "font_family": "Arial",
                "layout_name": f"Preview · {design.label}",
                "title": "LAI CHAU TERRAIN",
                "subtitle": design.label,
                "author": "Terrain Product Studio",
                "source": "Lai Chau DEM sample",
                "grid": True,
                "grid_mode": design.grid_mode,
                "show_legend": True,
                "paper_size": "a4",
                "orientation": "landscape",
                "export_png": True,
                "export_pdf": False,
                "dpi": 96,
                "export_prefix": f"preview_{design.key}",
            }
            layout, exported = create_terrain_layout(
                project, layers, temp_dir, config, north_arrow
            )
            if not exported:
                raise RuntimeError(f"No preview rendered for {design.key}")
            destination = os.path.join(PREVIEW_DIR, design.preview)
            _save_small_jpeg(exported[0], destination)
            print(
                f"{design.key}: {os.path.getsize(destination) / 1024:.1f} KiB"
            )
            project.layoutManager().removeLayout(layout)
    finally:
        project.removeAllMapLayers()
        shutil.rmtree(temp_dir, ignore_errors=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("dem", nargs="?", default=DEFAULT_DEM)
    args = parser.parse_args()
    app = QgsApplication([], False)
    app.initQgis()
    try:
        generate(os.path.abspath(args.dem))
    finally:
        app.exitQgis()


if __name__ == "__main__":
    main()
