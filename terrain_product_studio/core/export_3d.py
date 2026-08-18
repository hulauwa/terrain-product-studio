"""Binary STL / OBJ mesh export for 3D printing from a DEM.

The mesh is written by hand (numpy + GDAL only) so the plugin stays
dependency-free. Grids wider than ``_MAX_GRID`` cells are downsampled with
bilinear resampling to bound the triangle count and file size. With
``base_thickness_m > 0`` the terrain is extruded into a watertight solid
(top surface + bottom plate + perimeter walls), which makes the model
actually printable.
"""

from __future__ import annotations

import os

import numpy as np
from osgeo import gdal

_MAX_GRID = 1024


def _load_grid(dem_path):
    """Return ``(elevation (gh, gw) float64, geotransform)``.

    NoData / void cells are filled with the lowest valid elevation so the
    printed surface has no holes. Raises ValueError when the DEM cannot be
    opened or is too small to mesh.
    """

    ds = gdal.Open(str(dem_path), gdal.GA_ReadOnly)
    if ds is None:
        raise ValueError("Cannot open the DEM raster")
    band = ds.GetRasterBand(1)
    width, height = band.XSize, band.YSize
    if width < 2 or height < 2:
        ds = None
        raise ValueError("The DEM is too small to build a mesh")
    gw = min(width, _MAX_GRID)
    gh = min(height, _MAX_GRID)
    if gw < width or gh < height:
        data = band.ReadAsArray(
            buf_xsize=gw, buf_ysize=gh, resample_alg=gdal.GRIORA_Bilinear
        ).astype(np.float64)
    else:
        data = band.ReadAsArray().astype(np.float64)
    nodata = band.GetNoDataValue()
    gt = ds.GetGeoTransform()
    ds = None
    if nodata is not None:
        data = np.where(data == float(nodata), np.nan, data)
    if np.isnan(data).any():
        finite = data[np.isfinite(data)]
        fill = float(finite.min()) if finite.size else 0.0
        data = np.where(np.isnan(data), fill, data)
    return data, gt


def _build_mesh(data, gt, z_scale, base_thickness_m):
    """Return ``(vertices (n, 3), faces (m, 3) int64)`` of the closed mesh.

    The top surface is wound so its normal always points up (+z), whether
    the raster is north-up (negative y step, the usual case) or south-up.
    The bottom plate and perimeter walls are then derived from the top's
    own boundary edges, which keeps the whole solid consistently wound.
    """

    gh, gw = data.shape
    row_idx = np.arange(gh)[:, None]
    col_idx = np.arange(gw)[None, :]
    xs = gt[0] + col_idx * gt[1] + row_idx * gt[2]
    ys = gt[3] + row_idx * gt[5] + col_idx * gt[4]
    zs = data * z_scale
    verts = np.stack([xs, ys, zs], axis=-1).reshape(-1, 3)

    # Corners of every cell: a=(i,j), b=(i,j+1), c=(i+1,j+1), d=(i+1,j).
    a = np.arange(gh - 1)[:, None] * gw + np.arange(gw - 1)[None, :]
    b = a + 1
    c = a + gw + 1
    d = a + gw
    if gt[5] >= 0:
        top = np.stack(
            [np.stack([a, b, c], axis=-1), np.stack([a, c, d], axis=-1)], 0
        ).reshape(-1, 3)
    else:
        # North-up rasters: (a, b, c) would wind the wrong way.
        top = np.stack(
            [np.stack([a, c, b], axis=-1), np.stack([a, d, c], axis=-1)], 0
        ).reshape(-1, 3)
    faces = [top]

    if base_thickness_m > 0:
        z0 = float(zs.min()) - base_thickness_m
        base_verts = verts.copy()
        base_verts[:, 2] = z0
        top_count = verts.shape[0]
        verts = np.concatenate([verts, base_verts], axis=0)

        # Bottom plate: the top surface, reversed, dropped to z0.
        faces.append(top[:, ::-1] + top_count)

        # Perimeter walls: extract the top surface's boundary edges (each
        # directed edge appears once) and quad every edge down to the base.
        directed = np.concatenate(
            [top[:, [0, 1]], top[:, [1, 2]], top[:, [2, 0]]], axis=0
        )
        canonical = np.sort(directed, axis=1)
        _, inverse = np.unique(canonical, axis=0, return_inverse=True)
        boundary = directed[np.bincount(inverse)[inverse] == 1]
        u = boundary[:, 0]
        v = boundary[:, 1]
        ub = u + top_count
        vb = v + top_count
        # The wall presents the boundary edge reversed (v -> u) so the top
        # surface and the wall share it in opposite directions.
        walls = np.stack(
            [np.stack([v, u, ub], axis=-1), np.stack([v, ub, vb], axis=-1)], 0
        ).reshape(-1, 3)
        faces.append(walls)

    return verts, np.concatenate(faces)


def _triangle_normals(triangles):
    a = triangles[:, 0]
    ab = triangles[:, 1] - a
    ac = triangles[:, 2] - a
    normals = np.cross(ab, ac)
    lengths = np.linalg.norm(normals, axis=-1, keepdims=True)
    lengths[lengths == 0.0] = 1.0
    return normals / lengths


def export_stl(dem_path, output_path, z_scale=1.0, base_thickness_m=0.0):
    """Write the DEM as a binary STL file. Returns the triangle count."""

    data, gt = _load_grid(dem_path)
    verts, faces = _build_mesh(data, gt, z_scale, base_thickness_m)
    triangles = verts[faces].astype(np.float32)
    count = triangles.shape[0]
    if count <= 0:
        raise ValueError("The mesh has no triangles to write")

    record = np.zeros(count, dtype=np.dtype([("normal", "<f4", (3,)), ("verts", "<f4", (3, 3)), ("attr", "<u2")]))
    record["normal"] = _triangle_normals(triangles)
    record["verts"] = triangles
    with open(output_path, "wb") as handle:
        handle.write(b"Terrain Product Studio binary STL export".ljust(80, b"\x00"))
        handle.write(np.uint32(count).tobytes())
        record.tofile(handle)
    return int(count)


def export_obj(dem_path, output_path, z_scale=1.0, base_thickness_m=0.0):
    """Write the DEM as an OBJ file plus a white/gray MTL material.

    Returns the triangle count. The material file is placed next to the
    OBJ with the same basename (``.mtl``).
    """

    data, gt = _load_grid(dem_path)
    verts, faces = _build_mesh(data, gt, z_scale, base_thickness_m)
    count = faces.shape[0]
    if count <= 0:
        raise ValueError("The mesh has no triangles to write")

    mtl_path = os.path.splitext(output_path)[0] + ".mtl"
    with open(mtl_path, "w", encoding="utf-8") as handle:
        handle.write("newmtl terrain\nKa 0.75 0.75 0.75\nKd 0.82 0.82 0.82\nKs 0.15 0.15 0.15\nNs 8.0\n")
    with open(output_path, "w", encoding="utf-8") as handle:
        handle.write(f"mtllib {os.path.basename(mtl_path)}\n")
        handle.write("usemtl terrain\n")
        for x, y, z in verts:
            handle.write(f"v {x:.6g} {y:.6g} {z:.6g}\n")
        for f0, f1, f2 in faces + 1:
            handle.write(f"f {f0} {f1} {f2}\n")
    return int(count)
