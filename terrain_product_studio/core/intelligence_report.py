"""Topographic Intelligence Summary Report Generator.

Computes comprehensive spatial terrain metrics, hypsometric curves, aspect rose breakdowns,
drainage density, construction suitability, and landslide risk distribution, exporting a
publication-quality HTML intelligence dashboard.
"""

from __future__ import annotations

import collections
import math
import os
from datetime import datetime
import numpy as np
from osgeo import gdal, ogr


def generate_intelligence_report(
    dem_path: str,
    output_html_path: str,
    title: str = "Topographic Intelligence Report",
    slope_path: str | None = None,
    aspect_path: str | None = None,
    stream_vector_path: str | None = None,
    suitability_path: str | None = None,
    hazard_path: str | None = None,
    twi_path: str | None = None,
    geomorphon_path: str | None = None,
    spi_path: str | None = None,
    sti_path: str | None = None,
) -> str:
    """Generate an executive HTML topographic intelligence report with interactive SVG charts and spatial KPIs."""
    ds = gdal.Open(dem_path, gdal.GA_ReadOnly)
    if ds is None:
        raise RuntimeError(f"Could not open DEM for intelligence report: {dem_path}")

    band = ds.GetRasterBand(1)
    elev = band.ReadAsArray().astype(np.float32, copy=False)
    nodata = band.GetNoDataValue()

    valid = np.isfinite(elev)
    if nodata is not None and math.isfinite(float(nodata)):
        valid &= elev != float(nodata)

    total_cells = int(np.count_nonzero(valid))
    gt = ds.GetGeoTransform()
    proj = ds.GetProjection() or "Projected Coordinates"
    
    # Calculate pixel size in meters if projected
    dx_m = abs(gt[1])
    dy_m = abs(gt[5])
    pixel_area_km2 = (dx_m * dy_m) / 1_000_000.0
    total_area_km2 = total_cells * pixel_area_km2
    total_area_ha = total_area_km2 * 100.0

    min_elev = float(np.min(elev[valid])) if total_cells > 0 else 0.0
    max_elev = float(np.max(elev[valid])) if total_cells > 0 else 0.0
    mean_elev = float(np.mean(elev[valid])) if total_cells > 0 else 0.0
    std_elev = float(np.std(elev[valid])) if total_cells > 0 else 0.0
    relief_m = max_elev - min_elev

    # Slope statistics if available
    mean_slope = 0.0
    max_slope = 0.0
    if slope_path and os.path.exists(slope_path):
        try:
            sl_ds = gdal.Open(slope_path, gdal.GA_ReadOnly)
            if sl_ds is not None:
                sl_arr = sl_ds.GetRasterBand(1).ReadAsArray().astype(np.float32, copy=False)
                sl_valid = valid & np.isfinite(sl_arr) & (sl_arr >= 0)
                if np.any(sl_valid):
                    mean_slope = float(np.mean(sl_arr[sl_valid]))
                    max_slope = float(np.max(sl_arr[sl_valid]))
                sl_ds = None
        except Exception:
            sl_ds = None

    # Hypsometric 10-bin histogram
    bins = 10
    counts, bin_edges = np.histogram(elev[valid], bins=bins)
    hypso_bars = []
    max_count = max(1, int(np.max(counts)))
    for i in range(bins):
        low_z = int(bin_edges[i])
        high_z = int(bin_edges[i + 1])
        pct = round(float(counts[i]) / max(1, total_cells) * 100.0, 1)
        h_pct = round(float(counts[i]) / max_count * 100.0, 1)
        area_bin_ha = round(float(counts[i]) * pixel_area_km2 * 100.0, 1)
        hypso_bars.append({
            "range": f"{low_z}–{high_z} m",
            "pct": pct,
            "height": h_pct,
            "ha": area_bin_ha,
            "count": int(counts[i]),
        })

    # Aspect Breakdown (8 cardinal directions)
    aspect_stats = {"N": 0.0, "NE": 0.0, "E": 0.0, "SE": 0.0, "S": 0.0, "SW": 0.0, "W": 0.0, "NW": 0.0}
    if aspect_path and os.path.exists(aspect_path):
        try:
            a_ds = gdal.Open(aspect_path, gdal.GA_ReadOnly)
            if a_ds is not None:
                asp = a_ds.GetRasterBand(1).ReadAsArray().astype(np.float32, copy=False)
                asp_valid = valid & np.isfinite(asp) & (asp >= 0.0) & (asp <= 360.0)
                tot_asp = max(1, int(np.count_nonzero(asp_valid)))
                dirs = [
                    ("N", ((asp >= 337.5) | (asp < 22.5))),
                    ("NE", (asp >= 22.5) & (asp < 67.5)),
                    ("E", (asp >= 67.5) & (asp < 112.5)),
                    ("SE", (asp >= 112.5) & (asp < 157.5)),
                    ("S", (asp >= 157.5) & (asp < 202.5)),
                    ("SW", (asp >= 202.5) & (asp < 247.5)),
                    ("W", (asp >= 247.5) & (asp < 292.5)),
                    ("NW", (asp >= 292.5) & (asp < 337.5)),
                ]
                for name, mask in dirs:
                    aspect_stats[name] = round(float(np.count_nonzero(asp_valid & mask)) / tot_asp * 100.0, 1)
                a_ds = None
        except Exception:
            a_ds = None

    # Build SVG Aspect Rose Polar Chart
    # Radar polygon coordinates
    max_asp_pct = max(1.0, max(aspect_stats.values()))
    angles = [0, 45, 90, 135, 180, 225, 270, 315]  # N, NE, E, SE, S, SW, W, NW
    rose_cx, rose_cy, rose_r = 130, 130, 95
    poly_pts = []
    text_labels_svg = []
    
    dir_order = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
    for i, d in enumerate(dir_order):
        ang_rad = math.radians(angles[i] - 90)  # 0 at top (N)
        val = aspect_stats[d]
        norm_r = (val / max_asp_pct) * rose_r
        px = rose_cx + norm_r * math.cos(ang_rad)
        py = rose_cy + norm_r * math.sin(ang_rad)
        poly_pts.append(f"{px:.1f},{py:.1f}")

        # Text position outside
        tx = rose_cx + (rose_r + 18) * math.cos(ang_rad)
        ty = rose_cy + (rose_r + 18) * math.sin(ang_rad)
        text_labels_svg.append(f'<text x="{tx:.1f}" y="{ty+4:.1f}" fill="#8b949e" font-size="11" font-weight="600" text-anchor="middle">{d} ({val}%)</text>')

    rose_poly_str = " ".join(poly_pts)

    # Stream network metrics
    total_stream_km = 0.0
    stream_orders = collections.defaultdict(float)
    if stream_vector_path and os.path.exists(stream_vector_path):
        try:
            v_ds = ogr.Open(stream_vector_path)
            if v_ds is not None:
                layer = v_ds.GetLayer(0)
                for feat in layer:
                    length_m = feat.GetField("LENGTH_M") if feat.GetFieldIndex("LENGTH_M") >= 0 else 0.0
                    order_val = feat.GetField("ORDER") if feat.GetFieldIndex("ORDER") >= 0 else 1
                    total_stream_km += float(length_m or 0.0) / 1000.0
                    stream_orders[int(order_val or 1)] += float(length_m or 0.0) / 1000.0
                v_ds = None
        except Exception:
            v_ds = None

    drainage_density = round(total_stream_km / max(1e-4, total_area_km2), 2)

    # Suitability Stats
    suit_rows = []
    if suitability_path and os.path.exists(suitability_path):
        try:
            s_ds = gdal.Open(suitability_path, gdal.GA_ReadOnly)
            if s_ds is not None:
                s_arr = s_ds.GetRasterBand(1).ReadAsArray()
                s_valid = s_arr > 0
                tot_s = max(1, int(np.count_nonzero(s_valid)))
                labels = [
                    ("Class 1 (< 3°)", "Highly Suitable for Construction (Very High)", "#2ca25f"),
                    ("Class 2 (3°–8°)", "Suitable for Construction (High)", "#99d8c9"),
                    ("Class 3 (8°–15°)", "Moderate / Site Grading Required (Moderate)", "#fed976"),
                    ("Class 4 (15°–25°)", "Difficult / Slope Restricted (Restricted)", "#fd8d3c"),
                    ("Class 5 (> 25°)", "Unsuitable / Conservation Zone (Protected)", "#e31a1c"),
                ]
                for idx, (code_label, desc, color) in enumerate(labels, start=1):
                    cnt = int(np.count_nonzero(s_arr == idx))
                    p = round(cnt / tot_s * 100.0, 1)
                    ha = round(cnt * pixel_area_km2 * 100.0, 1)
                    suit_rows.append({"code": code_label, "desc": desc, "color": color, "pct": p, "ha": ha})
                s_ds = None
        except Exception:
            s_ds = None

    # Landslide Hazard Stats
    hazard_rows = []
    if hazard_path and os.path.exists(hazard_path):
        try:
            h_ds = gdal.Open(hazard_path, gdal.GA_ReadOnly)
            if h_ds is not None:
                h_arr = h_ds.GetRasterBand(1).ReadAsArray()
                h_valid = h_arr > 0
                tot_h = max(1, int(np.count_nonzero(h_valid)))
                h_labels = [
                    ("Class 1", "Low Hazard / Stable Slope", "#2b83ba"),
                    ("Class 2", "Moderate Hazard", "#ffffbf"),
                    ("Class 3", "High Hazard", "#fdae61"),
                    ("Class 4", "Very High Hazard / Critical Landslide Risk", "#d7191c"),
                ]
                for idx, (code_label, desc, color) in enumerate(h_labels, start=1):
                    cnt = int(np.count_nonzero(h_arr == idx))
                    p = round(cnt / tot_h * 100.0, 1)
                    ha = round(cnt * pixel_area_km2 * 100.0, 1)
                    hazard_rows.append({"code": code_label, "desc": desc, "color": color, "pct": p, "ha": ha})
                h_ds = None
        except Exception:
            h_ds = None

    # TWI stats
    twi_mean = 0.0
    twi_max = 0.0
    if twi_path and os.path.exists(twi_path):
        try:
            t_ds = gdal.Open(twi_path, gdal.GA_ReadOnly)
            if t_ds is not None:
                t_arr = t_ds.GetRasterBand(1).ReadAsArray().astype(np.float32, copy=False)
                t_valid = valid & np.isfinite(t_arr)
                if np.any(t_valid):
                    twi_mean = float(np.mean(t_arr[t_valid]))
                    twi_max = float(np.max(t_arr[t_valid]))
                t_ds = None
        except Exception:
            t_ds = None

    # Geomorphon landform stats (10 forms)
    from .geomorphon import GEOMORPHON_COLORS, GEOMORPHON_FORMS

    geomorphon_rows = []
    if geomorphon_path and os.path.exists(geomorphon_path):
        try:
            g_ds = gdal.Open(geomorphon_path, gdal.GA_ReadOnly)
            if g_ds is not None:
                g_arr = g_ds.GetRasterBand(1).ReadAsArray()
                g_valid = g_arr > 0
                tot_g = max(1, int(np.count_nonzero(g_valid)))
                for idx, (name, color) in enumerate(
                    zip(GEOMORPHON_FORMS, GEOMORPHON_COLORS), start=1
                ):
                    cnt = int(np.count_nonzero(g_arr == idx))
                    p = round(cnt / tot_g * 100.0, 1)
                    ha = round(cnt * pixel_area_km2 * 100.0, 1)
                    geomorphon_rows.append(
                        {"code": name, "color": color, "pct": p, "ha": ha}
                    )
                g_ds = None
        except Exception:
            g_ds = None

    # SPI / STI hydro-energy stats
    spi_mean = spi_max = 0.0
    sti_mean = sti_max = 0.0
    if spi_path and os.path.exists(spi_path):
        try:
            s_ds = gdal.Open(spi_path, gdal.GA_ReadOnly)
            if s_ds is not None:
                s_arr = s_ds.GetRasterBand(1).ReadAsArray().astype(np.float32, copy=False)
                s_valid = valid & np.isfinite(s_arr)
                if np.any(s_valid):
                    spi_mean = float(np.mean(s_arr[s_valid]))
                    spi_max = float(np.max(s_arr[s_valid]))
                s_ds = None
        except Exception:
            s_ds = None
    if sti_path and os.path.exists(sti_path):
        try:
            t_ds = gdal.Open(sti_path, gdal.GA_ReadOnly)
            if t_ds is not None:
                t_arr = t_ds.GetRasterBand(1).ReadAsArray().astype(np.float32, copy=False)
                t_valid = valid & np.isfinite(t_arr)
                if np.any(t_valid):
                    sti_mean = float(np.mean(t_arr[t_valid]))
                    sti_max = float(np.max(t_arr[t_valid]))
                t_ds = None
        except Exception:
            t_ds = None

    suit_html_section = ""
    if suit_rows:
        suit_tbody = "".join(
            f"<tr><td><span class=\"badge\" style=\"background:{r['color']}\">{r['code']}</span></td>"
            f"<td>{r['desc']}</td><td><strong>{r['ha']:,.1f} ha</strong></td>"
            f"<td><strong style=\"color:#58a6ff;\">{r['pct']}%</strong></td></tr>"
            for r in suit_rows
        )
        suit_html_section = f"""
    <div class="section-title">🏛️ 4. Urban Construction & Foundation Suitability</div>
    <div class="card">
      <table>
        <thead>
          <tr>
            <th>Slope Class</th>
            <th>Geotechnical Characteristics & Recommendations</th>
            <th>Area (ha)</th>
            <th>Proportion (%)</th>
          </tr>
        </thead>
        <tbody>
          {suit_tbody}
        </tbody>
      </table>
    </div>"""

    hazard_html_section = ""
    if hazard_rows:
        hazard_tbody = "".join(
            f"<tr><td><span class=\"badge\" style=\"background:{r['color']}; color:{'#fff' if 'Class 4' in r['code'] or 'Class 1' in r['code'] else '#000'}\">{r['code']}</span></td>"
            f"<td>{r['desc']}</td><td><strong>{r['ha']:,.1f} ha</strong></td>"
            f"<td><strong style=\"color:#f85149;\">{r['pct']}%</strong></td></tr>"
            for r in hazard_rows
        )
        hazard_html_section = f"""
    <div class="section-title">⚠️ 5. Landslide Hazard & Erosion Risk Evaluation (RUSLE LS)</div>
    <div class="card">
      <table>
        <thead>
          <tr>
            <th>Risk Tier</th>
            <th>Landslide Hazard Severity Level</th>
            <th>Area (ha)</th>
            <th>Proportion (%)</th>
          </tr>
        </thead>
        <tbody>
          {hazard_tbody}
        </tbody>
      </table>
    </div>"""

    geomorphon_html_section = ""
    if geomorphon_rows:
        geo_tbody = "".join(
            f"<tr><td><span class=\"badge\" style=\"background:{r['color']}\">{r['code']}</span></td>"
            f"<td><strong>{r['ha']:,.1f} ha</strong></td>"
            f"<td><strong style=\"color:#58a6ff;\">{r['pct']}%</strong></td></tr>"
            for r in geomorphon_rows
        )
        geomorphon_html_section = f"""
    <div class="section-title">⛰️ 6. Geomorphon Landform Classification</div>
    <div class="card">
      <div style="font-size:12px; color:var(--text-muted); margin-bottom:10px;">
        Machine-vision terrain forms (Jasiewicz & Stepinski 2013) — percentage of the survey area in each of the 10 canonical landforms:
      </div>
      <table>
        <thead>
          <tr>
            <th>Landform</th>
            <th>Area (ha)</th>
            <th>Proportion (%)</th>
          </tr>
        </thead>
        <tbody>
          {geo_tbody}
        </tbody>
      </table>
    </div>"""

    hydro_energy_html_section = ""
    if spi_path or sti_path:
        spi_cell = (
            f"<div class=\"kpi-card\"><div class=\"kpi-label\">Stream Power Index (SPI)</div>"
            f"<div class=\"kpi-val\">{spi_mean:.1f} <span class=\"kpi-unit\">mean</span></div>"
            f"<div class=\"kpi-sub\">Peak erosion energy: <b>{spi_max:.1f}</b></div></div>"
            if spi_path
            else ""
        )
        sti_cell = (
            f"<div class=\"kpi-card\"><div class=\"kpi-label\">Sediment Transport Index (STI)</div>"
            f"<div class=\"kpi-val\">{sti_mean:.1f} <span class=\"kpi-unit\">mean</span></div>"
            f"<div class=\"kpi-sub\">Peak sediment flux: <b>{sti_max:.1f}</b></div></div>"
            if sti_path
            else ""
        )
        hydro_energy_html_section = f"""
    <div class="section-title">💧 7. Hydro-Energy Indices (SPI / STI)</div>
    <div class="card">
      <div style="font-size:12px; color:var(--text-muted); margin-bottom:14px;">
        Drainage-driven erosion power and sediment transport capacity derived from flow accumulation and slope:
      </div>
      <div class="grid-kpi">
        {spi_cell}
        {sti_cell}
      </div>
    </div>"""

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M UTC")

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{title}</title>
  <style>
    :root {{
      --bg: #0d1117; --card-bg: #161b22; --card-hover: #1c2128; --border: #30363d;
      --text: #c9d1d9; --text-muted: #8b949e; --accent: #58a6ff;
      --success: #3fb950; --warning: #d29922; --danger: #f85149;
    }}
    * {{ margin: 0; padding: 0; box-sizing: border-box; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }}
    body {{ background: var(--bg); color: var(--text); padding: 32px 20px; line-height: 1.6; }}
    .container {{ max-width: 1160px; margin: 0 auto; }}
    
    header {{ display: flex; justify-content: space-between; align-items: flex-start; border-bottom: 1px solid var(--border); padding-bottom: 20px; margin-bottom: 28px; flex-wrap: wrap; gap: 16px; }}
    .header-left h1 {{ font-size: 26px; color: #fff; font-weight: 700; display: flex; align-items: center; gap: 10px; }}
    .header-left .subtitle {{ color: var(--text-muted); font-size: 13px; margin-top: 6px; }}
    
    .actions {{ display: flex; gap: 10px; }}
    .btn {{
      padding: 8px 16px; background: #21262d; color: var(--text); border: 1px solid var(--border);
      border-radius: 6px; font-size: 12px; font-weight: 600; cursor: pointer; transition: 0.2s;
      text-decoration: none; display: inline-flex; align-items: center; gap: 6px;
    }}
    .btn:hover {{ background: #30363d; color: #fff; border-color: var(--accent); }}
    .btn-primary {{ background: #238636; color: #fff; border-color: rgba(255,255,255,0.1); }}
    .btn-primary:hover {{ background: #2ea043; }}

    /* KPI Grid */
    .grid-kpi {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-bottom: 28px; }}
    .kpi-card {{ background: var(--card-bg); border: 1px solid var(--border); border-radius: 12px; padding: 18px 20px; transition: 0.2s; }}
    .kpi-card:hover {{ border-color: var(--accent); background: var(--card-hover); transform: translateY(-2px); }}
    .kpi-label {{ font-size: 11px; font-weight: 700; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.5px; }}
    .kpi-val {{ font-size: 24px; font-weight: 700; color: #fff; margin-top: 6px; font-family: monospace; }}
    .kpi-unit {{ font-size: 13px; font-weight: 400; color: var(--text-muted); }}
    .kpi-sub {{ font-size: 11px; color: var(--text-muted); margin-top: 4px; }}

    /* Section Cards */
    .section-title {{ font-size: 16px; font-weight: 700; color: #fff; margin: 28px 0 14px; border-left: 4px solid var(--accent); padding-left: 10px; display: flex; align-items: center; gap: 8px; }}
    .card {{ background: var(--card-bg); border: 1px solid var(--border); border-radius: 12px; padding: 22px; margin-bottom: 20px; }}

    .two-cols {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }}
    @media (max-width: 860px) {{ .two-cols {{ grid-template-columns: 1fr; }} }}

    /* Interactive Hypsometric Bar Chart */
    .bar-chart {{ display: flex; align-items: flex-end; height: 170px; gap: 10px; padding-top: 25px; border-bottom: 1px solid var(--border); }}
    .bar-col {{ flex: 1; display: flex; flex-direction: column; align-items: center; height: 100%; justify-content: flex-end; position: relative; cursor: pointer; }}
    .bar {{ width: 100%; background: linear-gradient(to top, #1f6feb, #58a6ff); border-radius: 4px 4px 0 0; transition: 0.3s; min-height: 2px; }}
    .bar-col:hover .bar {{ background: linear-gradient(to top, #388bfd, #79c0ff); filter: brightness(1.2); }}
    .bar-lbl {{ font-size: 10px; color: var(--text-muted); margin-top: 8px; white-space: nowrap; transform: rotate(-25deg); transform-origin: left top; }}
    .bar-pct {{ font-size: 11px; font-weight: 700; color: #fff; margin-bottom: 4px; }}
    
    .tooltip {{
      position: absolute; bottom: 100%; left: 50%; transform: translateX(-50%);
      background: #000; color: #fff; font-size: 10px; padding: 4px 8px; border-radius: 4px;
      white-space: nowrap; opacity: 0; pointer-events: none; transition: 0.2s; z-index: 10;
      border: 1px solid var(--border);
    }}
    .bar-col:hover .tooltip {{ opacity: 1; bottom: calc(100% + 5px); }}

    /* Tables */
    table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
    th, td {{ padding: 10px 14px; text-align: left; border-bottom: 1px solid var(--border); font-size: 12px; }}
    th {{ color: var(--text-muted); font-weight: 600; text-transform: uppercase; font-size: 11px; }}
    tr:hover td {{ background: rgba(255,255,255,0.02); }}
    .badge {{ display: inline-block; padding: 3px 8px; border-radius: 6px; font-size: 11px; font-weight: 700; color: #000; }}

    /* Stream Breakdown Bars */
    .stream-row {{ display: flex; align-items: center; gap: 12px; margin-bottom: 10px; font-size: 12px; }}
    .stream-name {{ width: 180px; font-weight: 600; color: #fff; }}
    .stream-bar-bg {{ flex: 1; height: 12px; background: rgba(255,255,255,0.06); border-radius: 6px; overflow: hidden; }}
    .stream-bar-fill {{ height: 100%; border-radius: 6px; }}
    .stream-val {{ width: 80px; text-align: right; font-family: monospace; font-weight: 700; color: var(--accent); }}

    footer {{ text-align: center; margin-top: 40px; font-size: 11px; color: var(--text-muted); border-top: 1px solid var(--border); padding-top: 20px; }}

    @media print {{
      body {{ background: #fff; color: #000; padding: 0; }}
      .card, .kpi-card {{ background: #fff; border: 1px solid #ccc; color: #000; }}
      .kpi-val, .section-title, th, td, h1 {{ color: #000 !important; }}
      .actions {{ display: none; }}
      .bar {{ background: #4a90e2 !important; }}
    }}
  </style>
</head>
<body>
  <div class="container">
    <header>
      <div class="header-left">
        <h1>📊 {title}</h1>
        <div class="subtitle">Comprehensive Geomorphometry, Hydrology & Environmental Risk Intelligence • Generated: {now_str}</div>
      </div>
      <div class="actions">
        <button class="btn" onclick="window.print()">🖨️ Print / Export PDF</button>
      </div>
    </header>

    <!-- Key Performance Indicators -->
    <div class="grid-kpi">
      <div class="kpi-card">
        <div class="kpi-label">Total Survey Area</div>
        <div class="kpi-val">{total_area_km2:,.2f} <span class="kpi-unit">km²</span></div>
        <div class="kpi-sub">{total_area_ha:,.0f} ha ({total_cells:,d} grid cells)</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Topographic Relief</div>
        <div class="kpi-val">{int(relief_m):,d} <span class="kpi-unit">m</span></div>
        <div class="kpi-sub">{int(min_elev):,d} m → {int(max_elev):,d} m (Mean: {mean_elev:.1f} m)</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Mean Slope</div>
        <div class="kpi-val">{mean_slope:.1f}° <span class="kpi-unit">/ max {max_slope:.1f}°</span></div>
        <div class="kpi-sub">Elevation Std Dev: ±{std_elev:.1f} m</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Total Drainage Network</div>
        <div class="kpi-val">{total_stream_km:,.1f} <span class="kpi-unit">km</span></div>
        <div class="kpi-sub">Drainage Density: <b>{drainage_density:.2f} km/km²</b></div>
      </div>
    </div>

    <!-- 1. Hypsometric Distribution -->
    <div class="section-title">📈 1. Hypsometric Elevation Distribution</div>
    <div class="card">
      <div style="font-size:12px; color:var(--text-muted); margin-bottom:16px;">Area distribution frequency across 10 elevation intervals (m):</div>
      <div class="bar-chart">
        {"".join(f'''
        <div class="bar-col">
          <div class="tooltip">{b["range"]}: {b["ha"]:,.1f} ha ({b["pct"]}%)</div>
          <div class="bar-pct">{b["pct"]}%</div>
          <div class="bar" style="height: {b["height"]}%;"></div>
          <div class="bar-lbl">{b["range"]}</div>
        </div>
        ''' for b in hypso_bars)}
      </div>
      <div style="height: 24px;"></div>
    </div>

    <div class="two-cols">
      <!-- 2. Aspect Rose Polar Chart -->
      <div>
        <div class="section-title">🧭 2. Aspect Orientation Rose</div>
        <div class="card" style="text-align: center;">
          <div style="font-size:12px; color:var(--text-muted); margin-bottom:10px;">Slope orientation distribution across 8 cardinal directions:</div>
          <svg viewBox="0 0 260 260" style="max-width: 240px; margin: 0 auto; display: block;">
            <!-- Radar background circles -->
            <circle cx="130" cy="130" r="30" fill="none" stroke="rgba(255,255,255,0.06)" />
            <circle cx="130" cy="130" r="60" fill="none" stroke="rgba(255,255,255,0.06)" />
            <circle cx="130" cy="130" r="95" fill="none" stroke="rgba(255,255,255,0.12)" />
            <!-- Axis lines -->
            <line x1="130" y1="35" x2="130" y2="225" stroke="rgba(255,255,255,0.08)" />
            <line x1="35" y1="130" x2="225" y2="130" stroke="rgba(255,255,255,0.08)" />
            <line x1="63" y1="63" x2="197" y2="197" stroke="rgba(255,255,255,0.05)" />
            <line x1="197" y1="63" x2="63" y2="197" stroke="rgba(255,255,255,0.05)" />
            <!-- Radar filled polygon -->
            <polygon points="{rose_poly_str}" fill="rgba(88,166,255,0.35)" stroke="#58a6ff" stroke-width="2" />
            <!-- Text labels -->
            {"".join(text_labels_svg)}
          </svg>
        </div>
      </div>

      <!-- 3. Stream Network Strahler Hierarchy -->
      <div>
        <div class="section-title">🌊 3. Strahler Drainage Network Hierarchy</div>
        <div class="card">
          <div style="font-size:12px; color:var(--text-muted); margin-bottom:14px;">Drainage length and hierarchical structure:</div>
          <div class="stream-row">
            <span class="stream-name">🔹 Order 1 (Headwater)</span>
            <div class="stream-bar-bg"><div class="stream-bar-fill" style="width:{min(100, (stream_orders[1]/max(1e-3, total_stream_km))*100):.1f}%; background:#6baed6;"></div></div>
            <span class="stream-val">{stream_orders[1]:,.1f} km</span>
          </div>
          <div class="stream-row">
            <span class="stream-name">🔹 Order 2 (Secondary Tributary)</span>
            <div class="stream-bar-bg"><div class="stream-bar-fill" style="width:{min(100, (stream_orders[2]/max(1e-3, total_stream_km))*100):.1f}%; background:#3182bd;"></div></div>
            <span class="stream-val">{stream_orders[2]:,.1f} km</span>
          </div>
          <div class="stream-row">
            <span class="stream-name">🔹 Order 3 (Sub-River Channel)</span>
            <div class="stream-bar-bg"><div class="stream-bar-fill" style="width:{min(100, (stream_orders[3]/max(1e-3, total_stream_km))*100):.1f}%; background:#08519c;"></div></div>
            <span class="stream-val">{stream_orders[3]:,.1f} km</span>
          </div>
          <div class="stream-row">
            <span class="stream-name">🔹 Order 4+ (Major River Channel)</span>
            <div class="stream-bar-bg"><div class="stream-bar-fill" style="width:{min(100, (sum(v for k,v in stream_orders.items() if k>=4)/max(1e-3, total_stream_km))*100):.1f}%; background:#08306b;"></div></div>
            <span class="stream-val">{sum(v for k,v in stream_orders.items() if k>=4):,.1f} km</span>
          </div>
          <div style="font-size:11px; color:var(--text-muted); margin-top:14px; padding-top:10px; border-top:1px solid var(--border);">
            💧 <b>Mean Topographic Wetness Index (TWI):</b> {twi_mean:.1f} (Max: {twi_max:.1f})
          </div>
        </div>
      </div>
    </div>

    <!-- 4. Construction Suitability Evaluation -->
    {suit_html_section}

    <!-- 5. Landslide Hazard Risk -->
    {hazard_html_section}

    <!-- 6. Geomorphon Landform Classification -->
    {geomorphon_html_section}

    <!-- 7. Hydro-Energy Indices -->
    {hydro_energy_html_section}

    <footer>
      Automatically generated by <b>Terrain Product Studio</b> • QGIS Automated Terrain Cartography & Geomorphometry Framework • Coordinate System: {proj[:40]}
    </footer>
  </div>
</body>
</html>
"""
    with open(output_html_path, "w", encoding="utf-8") as stream:
        stream.write(html_content)

    ds = None
    return output_html_path

