"""Cartographic presets kept independent from QGIS renderer classes."""

from __future__ import annotations

from .math_utils import interpolate_color_stops

# Each palette entry carries:
#   label    – display name in the dock combo and Processing enum
#   group    – "classic" / "artistic" / "environment" / "scientific" / "dark"
#   stops    – relative (0..1) color stops for a stretched color table
#   elev_stops – absolute elevation-anchored color stops (used verbatim)
#   dark     – True for the Dark Terrain family (drives dark map styling)
TERRAIN_PALETTES = {
    # ── Classic (light) ────────────────────────────────────────────────────
    "usgs_topo": {
        "label": "USGS Classic",
        "group": "classic",
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
    "natural": {
        "label": "Natural Earth",
        "group": "classic",
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
    "swiss_topo": {
        "label": "Swiss Topo",
        "group": "classic",
        "stops": (
            (0.00, 150, 176, 142),
            (0.18, 193, 204, 158),
            (0.40, 228, 218, 168),
            (0.60, 206, 176, 128),
            (0.78, 156, 120, 96),
            (0.92, 188, 184, 172),
            (1.00, 242, 240, 234),
        ),
    },
    # ── Artistic ──────────────────────────────────────────────────────────
    "imhof": {
        "label": "Imhof Relief",
        "group": "artistic",
        "stops": (
            (0.00, 32, 86, 58),
            (0.15, 88, 132, 82),
            (0.32, 160, 168, 108),
            (0.50, 205, 188, 128),
            (0.68, 172, 132, 88),
            (0.85, 214, 208, 192),
            (1.00, 248, 247, 242),
        ),
    },
    "atlas": {
        "label": "Vintage Atlas",
        "group": "artistic",
        "stops": (
            (0.00, 92, 137, 117),
            (0.20, 143, 166, 125),
            (0.40, 211, 192, 132),
            (0.60, 185, 145, 100),
            (0.80, 139, 111, 95),
            (1.00, 236, 232, 222),
        ),
    },
    "copper_relief": {
        "label": "Copper Relief",
        "group": "artistic",
        "stops": (
            (0.00, 52, 30, 22),
            (0.20, 102, 58, 34),
            (0.45, 166, 102, 55),
            (0.70, 211, 160, 102),
            (0.88, 236, 210, 172),
            (1.00, 250, 244, 230),
        ),
    },
    # ── Environment ───────────────────────────────────────────────────────
    "alpine": {
        "label": "Alpine",
        "group": "environment",
        "stops": (
            (0.00, 48, 92, 62),
            (0.18, 118, 142, 92),
            (0.40, 178, 162, 112),
            (0.62, 196, 186, 162),
            (0.82, 224, 226, 222),
            (1.00, 252, 253, 253),
        ),
    },
    "desert": {
        "label": "Desert",
        "group": "environment",
        "stops": (
            (0.00, 138, 94, 48),
            (0.25, 178, 128, 70),
            (0.50, 212, 166, 102),
            (0.75, 236, 206, 148),
            (1.00, 250, 242, 218),
        ),
    },
    "tropical": {
        "label": "Tropical",
        "group": "environment",
        "stops": (
            (0.00, 18, 78, 48),
            (0.20, 56, 122, 74),
            (0.45, 112, 158, 84),
            (0.70, 178, 192, 108),
            (0.88, 228, 222, 162),
            (1.00, 246, 242, 214),
        ),
    },
    "arctic": {
        "label": "Arctic",
        "group": "environment",
        "stops": (
            (0.00, 118, 148, 172),
            (0.25, 168, 188, 202),
            (0.50, 204, 218, 226),
            (0.75, 232, 242, 248),
            (1.00, 252, 253, 255),
        ),
    },
    # ── Scientific ────────────────────────────────────────────────────────
    "viridis": {
        "label": "Viridis",
        "group": "scientific",
        "stops": (
            (0.00, 68, 1, 84),
            (0.15, 72, 41, 134),
            (0.30, 58, 85, 166),
            (0.45, 34, 128, 178),
            (0.60, 32, 166, 165),
            (0.75, 96, 202, 122),
            (0.90, 192, 224, 66),
            (1.00, 253, 231, 37),
        ),
    },
    "turbo": {
        "label": "Turbo",
        "group": "scientific",
        "stops": (
            (0.00, 48, 18, 59),
            (0.15, 49, 98, 210),
            (0.30, 34, 181, 230),
            (0.45, 39, 221, 164),
            (0.60, 111, 235, 86),
            (0.75, 208, 218, 35),
            (0.90, 250, 150, 33),
            (1.00, 250, 70, 20),
        ),
    },
    "grayscale": {
        "label": "Grayscale",
        "group": "scientific",
        "stops": (
            (0.00, 244, 244, 242),
            (0.35, 218, 218, 214),
            (0.70, 181, 181, 177),
            (1.00, 238, 238, 236),
        ),
    },
    "spectral": {
        "label": "Spectral",
        "group": "scientific",
        "stops": (
            (0.00, 213, 62, 79),
            (0.15, 244, 109, 67),
            (0.30, 253, 174, 97),
            (0.45, 254, 224, 139),
            (0.60, 255, 255, 191),
            (0.75, 230, 245, 152),
            (0.88, 171, 221, 164),
            (1.00, 50, 136, 189),
        ),
    },
    # ── Dark Terrain (dark background + high-contrast ramps) ─────────────
    "terrain_dark": {
        "label": "Midnight Terrain",
        "group": "dark",
        "dark": True,
        "elev_stops": (
            (0.0, 8, 19, 24),
            (250.0, 18, 51, 46),
            (500.0, 37, 76, 59),
            (1000.0, 66, 99, 74),
            (2000.0, 146, 122, 80),
            (3500.0, 182, 166, 130),
            (5000.0, 216, 205, 187),
        ),
    },
    "dark_forest": {
        "label": "Dark Forest",
        "group": "dark",
        "dark": True,
        "elev_stops": (
            (0.0, 7, 19, 15),
            (250.0, 21, 56, 43),
            (500.0, 53, 98, 71),
            (1000.0, 126, 136, 90),
            (2000.0, 200, 198, 167),
        ),
    },
    "dark_alpine": {
        "label": "Dark Alpine",
        "group": "dark",
        "dark": True,
        "elev_stops": (
            (0.0, 8, 20, 29),
            (250.0, 22, 55, 70),
            (500.0, 72, 99, 107),
            (1000.0, 144, 147, 148),
            (2000.0, 224, 227, 227),
        ),
    },
    "dark_copper": {
        "label": "Dark Copper",
        "group": "dark",
        "dark": True,
        "elev_stops": (
            (0.0, 19, 15, 12),
            (250.0, 56, 37, 26),
            (500.0, 116, 69, 46),
            (1000.0, 182, 117, 78),
            (2000.0, 229, 199, 168),
        ),
    },
    "dark_volcano": {
        "label": "Dark Volcano",
        "group": "dark",
        "dark": True,
        "elev_stops": (
            (0.0, 11, 11, 13),
            (250.0, 41, 38, 42),
            (500.0, 89, 66, 60),
            (1000.0, 164, 90, 63),
            (2000.0, 229, 183, 125),
        ),
    },
    "dark_oceanic": {
        "label": "Dark Oceanic",
        "group": "dark",
        "dark": True,
        "elev_stops": (
            (0.0, 7, 21, 27),
            (250.0, 17, 56, 64),
            (500.0, 39, 97, 106),
            (1000.0, 109, 140, 122),
            (2000.0, 188, 194, 165),
        ),
    },
}

# Internal palette referenced by the Modern Atlas cartography theme but not
# offered in the dock combo (kept out of PALETTE_ORDER below).
TERRAIN_PALETTES["muted"] = {
    "label": "Muted basemap",
    "group": None,
    "stops": (
        (0.00, 151, 177, 163),
        (0.18, 178, 194, 169),
        (0.38, 218, 211, 172),
        (0.58, 211, 187, 153),
        (0.78, 184, 166, 153),
        (1.00, 231, 230, 226),
    ),
}

# Dock / Processing combo order: grouped with separators, exactly 20 entries.
# The Processing enum MUST use the same order — the dock passes the combo
# index straight through as the PALETTE parameter.
PALETTE_GROUPS = (
    ("classic", "Classic", ("usgs_topo", "natural", "swiss_topo")),
    ("artistic", "Artistic", ("imhof", "atlas", "copper_relief")),
    ("environment", "Environment", ("alpine", "desert", "tropical", "arctic")),
    ("scientific", "Scientific", ("viridis", "turbo", "grayscale", "spectral")),
    ("dark", "Dark Terrain", ("terrain_dark", "dark_forest", "dark_alpine", "dark_copper", "dark_volcano", "dark_oceanic")),
)
PALETTE_ORDER = tuple(key for _, _, keys in PALETTE_GROUPS for key in keys)

DEFAULT_PALETTE = "natural"
DEFAULT_CARTOGRAPHY = "natural_earth"


def resolve_palette_stops(palette, minimum, maximum):
    """Return ``(value, r, g, b)`` gdaldem color-table stops for a palette.

    Palettes with absolute elevation-anchored stops (``elev_stops``) are used
    verbatim; relative ``stops`` are stretched across the display range.
    """
    if "elev_stops" in palette:
        return [
            (float(value), int(red), int(green), int(blue))
            for value, red, green, blue in palette["elev_stops"]
        ]
    return interpolate_color_stops(minimum, maximum, palette["stops"])


def is_dark_palette(palette):
    """True when the palette belongs to the Dark Terrain family."""
    return bool(palette.get("dark"))


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
    "natural_earth": {
        "label": "Natural Earth Light",
        "description": "Default light cartography: natural green-brown terrain, clean blue hydrography and balanced contrast.",
        "palette": "natural",
        "font": "Noto Sans",
        "paper": "#f6f4ec",
        "ink": "#2a2f26",
        "muted_ink": "#6b7263",
        "contour_minor": "112,94,60,150",
        "contour_index": "78,62,38,235",
        "contour_master": "48,38,22,255",
        "contour_label": "#4f3d22",
        "water": "#1f6fb5",
        "water_light": "#b8d9ea",
        "accent": "#b5532f",
        "ridge": "96,76,50,200",
        "spot_elevation": "#4f3d22",
        "grid": "#7a7d6f",
        "orientation": "landscape",
        "legend_title": "MAP SYMBOLS",
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
    "night_dark": {
        "label": "Dark / Night Map",
        "description": "Night-time cartography: deep ink paper, light gray-cyan contour lines and luminous water — built for dark screens and presentations.",
        "palette": "terrain_dark",
        "font": "Noto Sans",
        "paper": "#0e1116",
        "ink": "#e6e1d8",
        "muted_ink": "#8a8a8a",
        "dark": True,
        "contour_minor": "170,186,200,150",
        "contour_index": "200,216,228,230",
        "contour_master": "226,238,244,255",
        "contour_label": "#d3e2ec",
        "water": "#5fc9f7",
        "water_light": "#1b3a4d",
        "accent": "#ff9d6b",
        "ridge": "150,176,192,200",
        "spot_elevation": "#ffb74d",
        "grid": "#4c5561",
        "orientation": "landscape",
        "legend_title": "MAP SYMBOLS",
    },
    "engineering_blueprint": {
        "label": "Engineering Blueprint",
        "description": "Navy drafting paper with precise cyan linework for engineering reviews and technical presentations.",
        "palette": "dark_oceanic",
        "font": "DejaVu Sans Mono",
        "paper": "#071d2b",
        "ink": "#e4f8ff",
        "muted_ink": "#82b8c8",
        "dark": True,
        "contour_minor": "94,190,211,150",
        "contour_index": "151,229,242,235",
        "contour_master": "226,249,255,255",
        "contour_label": "#c6f2fa",
        "water": "#52d7ff",
        "water_light": "#174c61",
        "accent": "#ffca68",
        "ridge": "126,196,208,210",
        "spot_elevation": "#ffd37a",
        "grid": "#5790a0",
        "orientation": "landscape",
        "legend_title": "ENGINEERING LEGEND",
    },
    "minimal_contours": {
        "label": "Minimal Contour Poster",
        "description": "Quiet paper, charcoal contours and restrained water for clean editorial maps and wall prints.",
        "palette": "grayscale",
        "font": "Noto Sans",
        "paper": "#faf9f5",
        "ink": "#242627",
        "muted_ink": "#777a78",
        "contour_minor": "95,96,92,125",
        "contour_index": "50,51,49,220",
        "contour_master": "25,26,25,255",
        "contour_label": "#303230",
        "water": "#557c8d",
        "water_light": "#dce7e9",
        "accent": "#a55c47",
        "ridge": "82,82,77,180",
        "spot_elevation": "#303230",
        "grid": "#a1a29d",
        "orientation": "portrait",
        "legend_title": "CONTOURS",
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
    "CONTOURS_SMOOTH": "Contours (smoothed)",
    "SPOT_ELEVATIONS": "Spot elevation peaks",
    "FLOW_ACCUMULATION": "Flow accumulation",
    "FILLED_DEM": "Hydrologically filled DEM",
    "FLOW_DIRECTION": "Flow direction",
    "STREAM_RASTER": "Potential stream raster",
    "STREAMS": "Potential drainage network",
    "STREAMS_SMOOTH": "Rivers (smoothed)",
    "RIDGES": "Potential ridgelines",
    "BASINS": "Watershed basins",
    "TWI": "Topographic Wetness Index (TWI)",
    "SUITABILITY": "Slope construction suitability",
    "LANDSLIDE_HAZARD": "Landslide hazard risk",
    "LS_FACTOR": "RUSLE LS slope-length factor",
    "GEOMORPHON": "Geomorphon terrain forms",
    "SPI": "Stream Power Index (SPI)",
    "STI": "Sediment Transport Index (STI)",
    "MULTIHAZARD": "Multi-hazard composite index",
}


# One-click product selections per industry, shown in a combo at the top of
# the Products tab. Keys are the dock's CREATE_* checkbox keys; the special
# "CREATE_HYDROLOGY" key ticks the Hydrology tab checkbox as well.
INDUSTRY_PRESETS = {
    "urban": (
        "Urban / Construction",
        (
            "CREATE_SUITABILITY",
            "CREATE_CONTOURS",
            "CREATE_COLOR_RELIEF",
            "CREATE_SLOPE",
            "CREATE_LANDSLIDE",
        ),
    ),
    "agriculture": (
        "Agriculture",
        (
            "CREATE_SLOPE",
            "CREATE_TWI",
            "CREATE_SPI",
            "CREATE_STI",
            "CREATE_COLOR_RELIEF",
        ),
    ),
    "disaster": (
        "Disaster management",
        (
            "CREATE_LANDSLIDE",
            "CREATE_MULTIHAZARD",
            "CREATE_HYDROLOGY",
            "CREATE_3D_VIEWER",
        ),
    ),
    "mining": (
        "Mining / Infrastructure",
        (
            "CREATE_SLOPE",
            "CREATE_ASPECT",
            "CREATE_HILLSHADE",
            "CREATE_CONTOURS",
            "CREATE_SPOT_ELEVATIONS",
        ),
    ),
}
