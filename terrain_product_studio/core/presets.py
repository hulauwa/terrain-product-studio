"""Cartographic presets kept independent from QGIS renderer classes."""

from __future__ import annotations


TERRAIN_PALETTES = {
    "usgs_topo": {
        "label": "USGS classic topo",
        "stops": (
            (0.00, 171, 196, 157),
            (0.16, 193, 207, 164),
            (0.35, 224, 216, 171),
            (0.55, 218, 193, 151),
            (0.74, 187, 157, 126),
            (0.89, 194, 186, 173),
            (1.00, 244, 241, 232),
        ),
    },
    "antique_survey": {
        "label": "Antique American survey",
        "stops": (
            (0.00, 151, 170, 139),
            (0.18, 181, 188, 145),
            (0.39, 216, 201, 155),
            (0.61, 199, 166, 124),
            (0.80, 158, 128, 105),
            (1.00, 226, 218, 201),
        ),
    },
    "natural": {
        "label": "Natural terrain",
        "stops": (
            (0.00, 62, 111, 85),
            (0.12, 103, 143, 98),
            (0.27, 157, 170, 116),
            (0.43, 211, 199, 143),
            (0.58, 193, 161, 112),
            (0.72, 151, 119, 92),
            (0.86, 177, 169, 158),
            (1.00, 239, 239, 235),
        ),
    },
    "muted": {
        "label": "Muted basemap",
        "stops": (
            (0.00, 151, 177, 163),
            (0.18, 178, 194, 169),
            (0.38, 218, 211, 172),
            (0.58, 211, 187, 153),
            (0.78, 184, 166, 153),
            (1.00, 231, 230, 226),
        ),
    },
    "atlas": {
        "label": "Classic atlas",
        "stops": (
            (0.00, 92, 137, 117),
            (0.20, 143, 166, 125),
            (0.40, 211, 192, 132),
            (0.60, 185, 145, 100),
            (0.80, 139, 111, 95),
            (1.00, 236, 232, 222),
        ),
    },
    "grayscale": {
        "label": "Grayscale",
        "stops": (
            (0.00, 244, 244, 242),
            (0.35, 218, 218, 214),
            (0.70, 181, 181, 177),
            (1.00, 238, 238, 236),
        ),
    },
}


# These presets drive both map-layer symbology and print-layout decoration.  The
# font names are preferences only; Qt substitutes an installed font when needed.
CARTOGRAPHY_PRESETS = {
    "usgs_classic": {
        "label": "USGS Classic Topo",
        "description": "Authentic USGS specification: brown hypsography, blue hydrography, ivory paper and classic typography.",
        "palette": "usgs_topo",
        "font": "Noto Serif",
        "paper": "#f7f2e5",
        "ink": "#292722",
        "muted_ink": "#625d51",
        "contour_minor": "166,116,66,170",
        "contour_index": "145,88,40,240",
        "contour_master": "115,68,30,255",
        "contour_label": "#833e25",
        "water": "#0070c0",
        "water_light": "#a0d0ea",
        "accent": "#9b3d30",
        "ridge": "130,85,50,200",
        "spot_elevation": "#753218",
        "grid": "#776f5f",
        "orientation": "landscape",
        "legend_title": "MAP SYMBOLS",
    },
    "antique_survey": {
        "label": "Antique American Survey",
        "description": "Warm parchment paper, umber ink and copper boundaries styled like 19th century survey maps.",
        "palette": "antique_survey",
        "font": "Baskerville",
        "paper": "#eee2c5",
        "ink": "#3b2d20",
        "muted_ink": "#77634c",
        "contour_minor": "128,91,58,165",
        "contour_index": "88,58,37,235",
        "contour_master": "65,40,22,255",
        "contour_label": "#563922",
        "water": "#3f7890",
        "water_light": "#abc4c6",
        "accent": "#9a5a37",
        "ridge": "100,68,42,200",
        "spot_elevation": "#563922",
        "grid": "#8b7659",
        "orientation": "landscape",
        "legend_title": "EXPLANATION",
    },
    "modern_atlas": {
        "label": "Modern Terrain Atlas",
        "description": "Restrained terrain colors, sans-serif typography and clean contemporary atlas layout.",
        "palette": "muted",
        "font": "Noto Sans",
        "paper": "#f4f3ee",
        "ink": "#20282b",
        "muted_ink": "#697275",
        "contour_minor": "102,87,75,145",
        "contour_index": "71,59,51,220",
        "contour_master": "45,37,32,255",
        "contour_label": "#4f433b",
        "water": "#277da1",
        "water_light": "#a7d5e5",
        "accent": "#c4623b",
        "ridge": "90,75,65,200",
        "spot_elevation": "#4f433b",
        "grid": "#6f7c7f",
        "orientation": "portrait",
        "legend_title": "LEGEND",
    },
    "field_grayscale": {
        "label": "Grayscale Field Map",
        "description": "High contrast monochrome cartography designed for field use and crisp black-and-white printing.",
        "palette": "grayscale",
        "font": "DejaVu Sans",
        "paper": "#f5f5f2",
        "ink": "#1c1c1c",
        "muted_ink": "#5c5c5c",
        "contour_minor": "80,80,80,145",
        "contour_index": "32,32,32,230",
        "contour_master": "10,10,10,255",
        "contour_label": "#282828",
        "water": "#363636",
        "water_light": "#bdbdbd",
        "accent": "#111111",
        "ridge": "60,60,60,200",
        "spot_elevation": "#1c1c1c",
        "grid": "#696969",
        "orientation": "landscape",
        "legend_title": "LEGEND",
    },
}


SLOPE_CLASSES = (
    (0.0, "#eef5df", "0–3° · Flat"),
    (3.0, "#d8e9ad", "3–8° · Gentle"),
    (8.0, "#f2df91", "8–15° · Moderate"),
    (15.0, "#eab56b", "15–25° · Steep"),
    (25.0, "#d87a4a", "25–35° · Very steep"),
    (35.0, "#9e3d36", ">35° · Extreme"),
    (90.0, "#662b33", "90°"),
)


ASPECT_CLASSES = (
    (0.0, "#5d83b3", "North"),
    (22.5, "#6ba8a9", "North-east"),
    (67.5, "#9bc58d", "East"),
    (112.5, "#d8d17a", "South-east"),
    (157.5, "#d89b62", "South"),
    (202.5, "#bd6d71", "South-west"),
    (247.5, "#8c6e9e", "West"),
    (292.5, "#687caa", "North-west"),
    (337.5, "#5d83b3", "North"),
    (360.0, "#5d83b3", "North"),
)


OUTPUT_LABELS = {
    "WORKING_DEM": "Working DEM",
    "COLOR_RELIEF": "Elevation color relief",
    "HILLSHADE": "Hillshade",
    "MULTI_HILLSHADE": "Multidirectional hillshade",
    "SLOPE": "Slope (degrees)",
    "ASPECT": "Aspect",
    "TRI": "Terrain Ruggedness Index",
    "TPI": "Topographic Position Index",
    "ROUGHNESS": "Roughness",
    "PROFILE_CURVATURE": "Profile curvature",
    "PLANFORM_CURVATURE": "Planform curvature",
    "CONTOURS": "Contours",
    "SPOT_ELEVATIONS": "Spot elevation peaks",
    "FLOW_ACCUMULATION": "Flow accumulation",
    "FILLED_DEM": "Hydrologically filled DEM",
    "FLOW_DIRECTION": "Flow direction",
    "STREAM_RASTER": "Potential stream raster",
    "STREAMS": "Potential drainage network",
    "RIDGES": "Potential ridgelines",
    "BASINS": "Watershed basins",
}

