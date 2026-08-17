#!/usr/bin/env python3
"""Build clean zip artifact for QGIS Plugin Repository upload."""

import configparser
import os
import zipfile

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLUGIN_DIR = os.path.join(ROOT_DIR, "terrain_product_studio")
DIST_DIR = os.path.join(ROOT_DIR, "dist")

EXCLUDE_DIRS = {"__pycache__", ".git", "tss", ".idea", ".vscode"}
EXCLUDE_EXTS = {".pyc", ".pyo", ".DS_Store"}


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


def build_zip():
    version = validate_metadata()
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

    size_mb = os.path.getsize(zip_path) / (1024 * 1024)
    print(f"📦 Created zip: {zip_path}")
    print(f"📊 Added {added_files} files, Total Size: {size_mb:.2f} MB")

    if size_mb > 25.0:
        raise RuntimeError(f"❌ Zip file exceeds 25 MB limit! Current size: {size_mb:.2f} MB")
    else:
        print("✅ Package is well under QGIS 25 MB limit!")


if __name__ == "__main__":
    build_zip()
