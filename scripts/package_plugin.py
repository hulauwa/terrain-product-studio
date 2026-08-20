#!/usr/bin/env python3
"""Build clean zip artifact for QGIS Plugin Repository upload."""

import configparser
import os
import zipfile

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLUGIN_DIR = os.path.join(ROOT_DIR, "terrain_product_studio")
DIST_DIR = os.path.join(ROOT_DIR, "dist")

EXCLUDE_DIRS = {"__pycache__", ".git", "temp", "tss", ".idea", ".vscode"}
EXCLUDE_EXTS = {".pyc", ".pyo", ".DS_Store"}
REQUIRED_ARCHIVE_MEMBERS = {
    "terrain_product_studio/__init__.py",
    "terrain_product_studio/metadata.txt",
    "terrain_product_studio/plugin.py",
    "terrain_product_studio/provider.py",
    "terrain_product_studio/core/product_registry.py",
}


def validate_metadata():
    metadata_path = os.path.join(PLUGIN_DIR, "metadata.txt")
    if not os.path.exists(metadata_path):
        raise RuntimeError("metadata.txt is missing!")

    parser = configparser.ConfigParser()
    parser.read(metadata_path, encoding="utf-8")
    gen = parser["general"]

    required_keys = ["name", "description", "about", "version", "author", "email", "repository", "license"]
    for key in required_keys:
        val = gen.get(key, "").strip()
        if not val:
            raise ValueError(f"metadata.txt missing required key: {key}")

    print(f"✅ Metadata validation passed! Version: {gen['version']}, License: {gen['license']}")
    return gen["version"]


def validate_archive(zip_path):
    """Reject source archives and incomplete ZIPs before they reach users."""

    with zipfile.ZipFile(zip_path, "r") as zipf:
        members = set(zipf.namelist())

    missing = sorted(REQUIRED_ARCHIVE_MEMBERS - members)
    if missing:
        raise RuntimeError(
            "Release ZIP is missing mandatory plugin files: " + ", ".join(missing)
        )

    unexpected_roots = sorted(
        {
            member.split("/", 1)[0]
            for member in members
            if member and not member.startswith("terrain_product_studio/")
        }
    )
    if unexpected_roots:
        raise RuntimeError(
            "Release ZIP has an invalid outer folder: " + ", ".join(unexpected_roots)
        )

    print("✅ Archive structure validation passed!")


def build_zip():
    version = validate_metadata()
    tag_name = os.environ.get("GITHUB_REF_NAME", "")
    tag_type = os.environ.get("GITHUB_REF_TYPE", "")
    if tag_type == "tag" and tag_name != f"v{version}":
        raise RuntimeError(
            f"Release tag {tag_name!r} does not match metadata version v{version}."
        )
    os.makedirs(DIST_DIR, exist_ok=True)
    zip_filename = f"terrain_product_studio-{version}.zip"
    zip_path = os.path.join(DIST_DIR, zip_filename)

    if os.path.exists(zip_path):
        os.remove(zip_path)

    added_files = 0
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(PLUGIN_DIR):
            # Prune excluded directories
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]

            for file in files:
                if any(file.endswith(ext) for ext in EXCLUDE_EXTS):
                    continue

                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, ROOT_DIR)
                zipf.write(full_path, rel_path)
                added_files += 1

    validate_archive(zip_path)

    size_mb = os.path.getsize(zip_path) / (1024 * 1024)
    print(f"📦 Created zip: {zip_path}")
    print(f"📊 Added {added_files} files, Total Size: {size_mb:.2f} MB")

    if size_mb > 25.0:
        raise RuntimeError(f"❌ Zip file exceeds 25 MB limit! Current size: {size_mb:.2f} MB")
    else:
        print("✅ Package is well under QGIS 25 MB limit!")
    return zip_path


if __name__ == "__main__":
    build_zip()
