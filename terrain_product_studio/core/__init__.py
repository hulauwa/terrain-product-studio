"""Reusable helpers for Terrain Product Studio."""

import os


def plugin_version() -> str:
    """Read the plugin version from metadata.txt so reports never hardcode it."""

    metadata_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "metadata.txt"
    )
    try:
        with open(metadata_path, encoding="utf-8") as stream:
            for line in stream:
                if line.strip().startswith("version="):
                    return line.strip().split("=", 1)[1]
    except OSError:
        pass
    return "unknown"
