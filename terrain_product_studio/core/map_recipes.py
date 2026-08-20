"""Declarative layer recipes for the QGIS canvas and print layouts.

This module intentionally has no QGIS imports, so recipe behavior can be
tested without launching QGIS. Logical roles hide raw/smoothed implementation
details from the UI and layout composer.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping, Tuple


ROLE_VARIANTS: Mapping[str, Tuple[str, ...]] = {
    "spot_elevations": ("SPOT_ELEVATIONS",),
    "streams": ("STREAMS_SMOOTH", "STREAMS"),
    "ridges": ("RIDGES",),
    "contours": ("CONTOURS_SMOOTH", "CONTOURS"),
    "hillshade": ("MULTI_HILLSHADE", "HILLSHADE"),
    "color_relief": ("COLOR_RELIEF",),
}


@dataclass(frozen=True)
class MapRecipe:
    """Logical layer stack for one cartographic treatment."""

    key: str
    canvas_roles: Tuple[str, ...]
    layout_roles: Tuple[str, ...]


DEFAULT_RECIPE = MapRecipe(
    key="default",
    canvas_roles=("spot_elevations", "contours", "hillshade", "color_relief"),
    layout_roles=(
        "spot_elevations",
        "streams",
        "ridges",
        "contours",
        "hillshade",
        "color_relief",
    ),
)


MAP_RECIPES = {
    "engineering_blueprint": MapRecipe(
        key="engineering_blueprint",
        canvas_roles=("spot_elevations", "streams", "contours"),
        layout_roles=("spot_elevations", "streams", "ridges", "contours"),
    ),
    "minimal_contours": MapRecipe(
        key="minimal_contours",
        canvas_roles=("spot_elevations", "streams", "contours"),
        layout_roles=("spot_elevations", "streams", "contours"),
    ),
}


def recipe_for(preset_key: str) -> MapRecipe:
    """Return the special recipe for a preset, or the safe default stack."""

    return MAP_RECIPES.get(preset_key, DEFAULT_RECIPE)


def resolve_role(available: Iterable[str], role: str):
    """Resolve a logical role, preferring smoothed cartographic variants."""

    available_keys = set(available)
    for key in ROLE_VARIANTS.get(role, (role,)):
        if key in available_keys:
            return key
    return None


def resolve_recipe_keys(available: Iterable[str], preset_key: str, target="canvas"):
    """Return a top-to-bottom physical layer stack without duplicates."""

    available_keys = set(available)
    recipe = recipe_for(preset_key)
    roles = recipe.layout_roles if target == "layout" else recipe.canvas_roles
    resolved = []
    for role in roles:
        key = resolve_role(available_keys, role)
        if key is not None and key not in resolved:
            resolved.append(key)
    return tuple(resolved)
