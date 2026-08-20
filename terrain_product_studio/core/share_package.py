"""Write a lightweight, transparent index for sharing a terrain run."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone

from .math_utils import unique_path
from .style_packs import style_pack


def _file_entry(key, value, root):
    path = str(value or "").split("|")[0]
    if not path or not os.path.exists(path):
        return None
    try:
        relative = os.path.relpath(path, root)
    except ValueError:
        relative = path
    return {
        "role": key,
        "path": relative,
        "size_bytes": os.path.getsize(path),
        "is_external": relative.startswith(".."),
    }


def write_share_manifest(output_folder, prefix, outputs, cartography, layout_names=()):
    """Index data, assumptions and presentation choices without copying data."""

    os.makedirs(output_folder, exist_ok=True)
    pack = style_pack(cartography.get("preset", "natural_earth"))
    files = []
    for key, value in sorted(outputs.items()):
        entry = _file_entry(key, value, output_folder)
        if entry:
            files.append(entry)
    manifest = {
        "schema": "terrain-product-studio/share-package/1",
        "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "canonical_dem_role": "WORKING_DEM",
        "rgb_compatibility_role": "COLOR_RELIEF",
        "style_pack": {
            "key": pack.key,
            "label": pack.label,
            "palette": cartography.get("palette_key", pack.palette),
            "style_pack_palette": pack.palette,
            "layout_template": cartography.get(
                "layout_template", pack.layout_template
            ),
            "requested_font": cartography.get("requested_font", pack.preferred_font),
            "resolved_font": cartography.get("font_family", pack.preferred_font),
        },
        "layouts": list(layout_names),
        "files": files,
        "usage": {
            "qgis": "Open the QGZ project when present; layout styles are stored per map item.",
            "web_3d": "Open the HTML preview. Use its Data tab to select a GeoTIFF/COG or GeoJSON directly.",
            "browser_security": "A local HTML page cannot automatically read arbitrary local files; select them explicitly or serve the folder over HTTP.",
        },
    }
    path = unique_path(os.path.join(output_folder, f"{prefix}_share_manifest.json"))
    with open(path, "w", encoding="utf-8") as stream:
        json.dump(manifest, stream, ensure_ascii=False, indent=2)
    return path
