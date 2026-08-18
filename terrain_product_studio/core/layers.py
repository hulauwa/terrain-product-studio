"""Load generated products into an ordered and styled QGIS layer tree."""

from __future__ import annotations

import os

from qgis.PyQt.QtGui import QColor
from qgis.core import QgsProject, QgsRasterLayer, QgsVectorLayer

from .presets import CARTOGRAPHY_PRESETS, OUTPUT_LABELS
from .styles import (
    apply_aspect_style,
    apply_basin_style,
    apply_contour_style,
    apply_curvature_style,
    apply_flow_accumulation_style,
    apply_geomorphon_style,
    apply_hillshade_style,
    apply_landslide_style,
    apply_multihazard_style,
    apply_ridge_style,
    apply_ruggedness_style,
    apply_slope_style,
    apply_spot_elevation_style,
    apply_spi_style,
    apply_sti_style,
    apply_stream_style,
    apply_suitability_style,
    apply_tpi_style,
    apply_twi_style,
)


def _source_path(value):
    if hasattr(value, "source"):
        return value.source()
    return str(value or "")


def _add_raster(project, group, key, path, visible=True):
    layer = QgsRasterLayer(path, OUTPUT_LABELS.get(key, key.replace("_", " ").title()))
    if not layer.isValid():
        return None, None
    project.addMapLayer(layer, False)
    node = group.addLayer(layer)
    node.setItemVisibilityChecked(visible)
    # Raster layers never carry text labels — labeling is only ever applied
    # to the vector contour / spot-elevation layers (USGS convention).
    return layer, node


def add_terrain_results(
    results,
    contour_interval=10.0,
    index_multiplier=5,
    z_unit="m",
    cartography_preset="usgs_classic",
    font_family=None,
    return_layers=False,
):
    """Add algorithm result paths and return ``(loaded_count, failed_paths)``."""

    project = QgsProject.instance()
    root = project.layerTreeRoot()
    package_group = root.insertGroup(0, "Terrain Product Studio")

    # Dark Terrain maps: stronger hillshade and a deep ink canvas background
    # so NoData / background reads as #090B0D instead of white.
    dark = bool(CARTOGRAPHY_PRESETS.get(cartography_preset, {}).get("dark"))
    hillshade_opacity = 0.45 if dark else None
    
    # Order groups so top-most visual layers (vectors) are at the top of the Layer Tree panel
    hydro_group = package_group.addGroup("01 · Hydrology")
    contour_group = package_group.addGroup("02 · Elevation & contours")
    base_group = package_group.addGroup("03 · Terrain basemap")
    analysis_group = package_group.addGroup("04 · Terrain analysis")
    quality_group = package_group.addGroup("05 · Working data")

    loaded = 0
    failed = []
    layers = {}
    nodes = {}

    raster_groups = {
        "COLOR_RELIEF": (base_group, True),
        "HILLSHADE": (base_group, "MULTI_HILLSHADE" not in results),
        "MULTI_HILLSHADE": (base_group, True),
        "SLOPE": (analysis_group, False),
        "ASPECT": (analysis_group, False),
        "TRI": (analysis_group, False),
        "TPI": (analysis_group, False),
        "ROUGHNESS": (analysis_group, False),
        "PROFILE_CURVATURE": (analysis_group, False),
        "PLANFORM_CURVATURE": (analysis_group, False),
        "FLOW_ACCUMULATION": (hydro_group, False),
        "FLOW_DIRECTION": (hydro_group, False),
        "STREAM_RASTER": (hydro_group, False),
        "BASINS": (hydro_group, False),
        "TWI": (hydro_group, False),
        "SUITABILITY": (analysis_group, False),
        "LANDSLIDE_HAZARD": (analysis_group, False),
        "LS_FACTOR": (analysis_group, False),
        "GEOMORPHON": (analysis_group, False),
        "SPI": (hydro_group, False),
        "STI": (hydro_group, False),
        "MULTIHAZARD": (analysis_group, False),
        "FILLED_DEM": (quality_group, False),
        "WORKING_DEM": (quality_group, False),
    }
    for key, (group, visible) in raster_groups.items():
        if key not in results:
            continue
        path = _source_path(results[key])
        if not path or not os.path.exists(path):
            failed.append(path or key)
            continue
        layer, node = _add_raster(project, group, key, path, visible)
        if layer is None:
            failed.append(path)
            continue
        layers[key] = layer
        nodes[key] = node
        loaded += 1

    if "CONTOURS" in results:
        path = _source_path(results["CONTOURS"])
        contour = QgsVectorLayer(path, OUTPUT_LABELS["CONTOURS"], "ogr")
        if contour.isValid():
            project.addMapLayer(contour, False)
            contour_group.addLayer(contour)
            layers["CONTOURS"] = contour
            loaded += 1
        else:
            failed.append(path)

    if "CONTOURS_SMOOTH" in results:
        path = _source_path(results["CONTOURS_SMOOTH"])
        smooth_contour = QgsVectorLayer(path, OUTPUT_LABELS["CONTOURS_SMOOTH"], "ogr")
        if smooth_contour.isValid():
            project.addMapLayer(smooth_contour, False)
            contour_group.addLayer(smooth_contour)
            layers["CONTOURS_SMOOTH"] = smooth_contour
            loaded += 1
        else:
            failed.append(path)

    if "SPOT_ELEVATIONS" in results:
        path = _source_path(results["SPOT_ELEVATIONS"])
        spots = QgsVectorLayer(path, OUTPUT_LABELS["SPOT_ELEVATIONS"], "ogr")
        if spots.isValid():
            project.addMapLayer(spots, False)
            contour_group.insertLayer(0, spots)
            layers["SPOT_ELEVATIONS"] = spots
            loaded += 1
        else:
            failed.append(path)

    if "RIDGES" in results:
        path = _source_path(results["RIDGES"])
        ridges = QgsVectorLayer(path, OUTPUT_LABELS["RIDGES"], "ogr")
        if ridges.isValid():
            project.addMapLayer(ridges, False)
            node = hydro_group.addLayer(ridges)
            # Working-data hydrology: loaded but hidden in the default basemap.
            node.setItemVisibilityChecked(False)
            layers["RIDGES"] = ridges
            loaded += 1
        else:
            failed.append(path)

    if "STREAMS" in results:
        path = _source_path(results["STREAMS"])
        streams = QgsVectorLayer(path, OUTPUT_LABELS["STREAMS"], "ogr")
        if streams.isValid():
            project.addMapLayer(streams, False)
            node = hydro_group.insertLayer(0, streams)
            node.setItemVisibilityChecked(False)
            layers["STREAMS"] = streams
            loaded += 1
        else:
            failed.append(path)

    if "STREAMS_SMOOTH" in results:
        path = _source_path(results["STREAMS_SMOOTH"])
        smooth_streams = QgsVectorLayer(path, OUTPUT_LABELS["STREAMS_SMOOTH"], "ogr")
        if smooth_streams.isValid():
            project.addMapLayer(smooth_streams, False)
            node = hydro_group.insertLayer(1, smooth_streams)
            node.setItemVisibilityChecked(False)
            layers["STREAMS_SMOOTH"] = smooth_streams
            loaded += 1
        else:
            failed.append(path)

    if "COLOR_RELIEF" in nodes:
        base_group.insertChildNode(len(base_group.children()), nodes["COLOR_RELIEF"].clone())
        base_group.removeChildNode(nodes["COLOR_RELIEF"])
    for key in ("HILLSHADE", "MULTI_HILLSHADE"):
        if key in layers:
            if hillshade_opacity is None:
                opacity = 0.32 if key == "MULTI_HILLSHADE" else 0.38
            else:
                opacity = hillshade_opacity
            apply_hillshade_style(layers[key], opacity)
    if "SLOPE" in layers:
        apply_slope_style(layers["SLOPE"])
    if "ASPECT" in layers:
        apply_aspect_style(layers["ASPECT"])
    if "TPI" in layers:
        apply_tpi_style(layers["TPI"])
    for key in ("TRI", "ROUGHNESS"):
        if key in layers:
            apply_ruggedness_style(layers[key])
    for key in ("PROFILE_CURVATURE", "PLANFORM_CURVATURE"):
        if key in layers:
            apply_curvature_style(layers[key])
    if "CONTOURS" in layers:
        apply_contour_style(
            layers["CONTOURS"],
            contour_interval,
            index_multiplier,
            z_unit,
            cartography_preset,
            font_family,
        )
    if "CONTOURS_SMOOTH" in layers:
        apply_contour_style(
            layers["CONTOURS_SMOOTH"],
            contour_interval,
            index_multiplier,
            z_unit,
            cartography_preset,
            font_family,
        )
    if "SPOT_ELEVATIONS" in layers:
        apply_spot_elevation_style(layers["SPOT_ELEVATIONS"], cartography_preset, font_family)
    if "STREAMS" in layers:
        apply_stream_style(layers["STREAMS"], cartography_preset)
    if "STREAMS_SMOOTH" in layers:
        apply_stream_style(layers["STREAMS_SMOOTH"], cartography_preset)
    if "RIDGES" in layers:
        apply_ridge_style(layers["RIDGES"], cartography_preset)
    if "FLOW_ACCUMULATION" in layers:
        apply_flow_accumulation_style(layers["FLOW_ACCUMULATION"], cartography_preset)
    if "BASINS" in layers:
        apply_basin_style(layers["BASINS"], cartography_preset)
    if "TWI" in layers:
        apply_twi_style(layers["TWI"])
    if "SUITABILITY" in layers:
        apply_suitability_style(layers["SUITABILITY"])
    if "LANDSLIDE_HAZARD" in layers:
        apply_landslide_style(layers["LANDSLIDE_HAZARD"])
    if "GEOMORPHON" in layers:
        apply_geomorphon_style(layers["GEOMORPHON"])
    if "SPI" in layers:
        apply_spi_style(layers["SPI"])
    if "STI" in layers:
        apply_sti_style(layers["STI"])
    if "MULTIHAZARD" in layers:
        apply_multihazard_style(layers["MULTIHAZARD"])

    analysis_group.setItemVisibilityChecked(False)
    quality_group.setItemVisibilityChecked(False)
    if dark:
        try:
            project.setBackgroundColor(QColor("#090b0d"))
        except (AttributeError, TypeError):
            pass  # QgsProject.setBackgroundColor is QGIS 3.26+; keep defaults
    if return_layers:
        return loaded, failed, layers
    return loaded, failed

