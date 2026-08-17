from __future__ import annotations
import json
import math
import os
import numpy as np
from osgeo import gdal, ogr, osr

def _resample_band(path: str | None, gw: int, gh: int, nodata_fill: float = 0.0) -> list[list[float]] | None:
    if not path or not os.path.exists(path):
        return None
    try:
        ds = gdal.Open(str(path), gdal.GA_ReadOnly)
        if ds is None:
            return None
        band = ds.GetRasterBand(1)
        data = band.ReadAsArray(buf_xsize=gw, buf_ysize=gh, resample_alg=gdal.GRIORA_Bilinear).astype(np.float32, copy=False)
        nodata = band.GetNoDataValue()
        valid = np.isfinite(data)
        if nodata is not None and math.isfinite(float(nodata)):
            valid &= data != float(nodata)
        clean = np.where(valid, data, nodata_fill)
        clean = np.nan_to_num(clean, nan=nodata_fill, posinf=nodata_fill, neginf=nodata_fill)
        ds = None
        return clean.round(2).tolist()
    except Exception:
        return None

def _extract_linestring_pts(geom, bounds_x, bounds_y, dx, dy) -> list[list[list[float]]]:
    if geom is None:
        return []
    count = geom.GetGeometryCount()
    if count > 0:
        res = []
        for i in range(count):
            res.extend(_extract_linestring_pts(geom.GetGeometryRef(i), bounds_x, bounds_y, dx, dy))
        return res
    pts = []
    pcount = geom.GetPointCount()
    for i in range(pcount):
        gx, gy = geom.GetX(i), geom.GetY(i)
        nx = ((gx - bounds_x[0]) / dx - 0.5) * 100.0
        ny = ((gy - bounds_y[0]) / dy - 0.5) * 100.0
        pts.append([round(nx, 2), round(ny, 2)])
    return [pts] if len(pts) >= 2 else []

def generate_3d_web_viewer(
    dem_path: str,
    output_html_path: str,
    title: str = "Terrain 3D Interactive WebGIS Studio",
    stream_vector_path: str | None = None,
    contour_vector_path: str | None = None,
    spot_peaks_path: str | None = None,
    slope_path: str | None = None,
    twi_path: str | None = None,
    suitability_path: str | None = None,
    hazard_path: str | None = None,
    grid_size: int = 240,
) -> str:
    """Generate a self-contained 3D WebGIS Studio HTML file with multi-layer overlays and comprehensive analytical tools."""
    clean_path = str(dem_path).split("|")[0].strip('"').strip("'")
    ds = gdal.Open(clean_path, gdal.GA_ReadOnly)
    if ds is None:
        raise RuntimeError(f"Could not open DEM for 3D viewer: {dem_path}")

    band = ds.GetRasterBand(1)
    orig_w, orig_h = ds.RasterXSize, ds.RasterYSize
    gt = ds.GetGeoTransform()
    proj = ds.GetProjection() or "Projected Coordinates"
    nodata = band.GetNoDataValue()

    gw = grid_size
    gh = int(round(grid_size * (orig_h / max(1, orig_w))))
    gh = max(40, min(gh, grid_size * 2))

    dem_data = band.ReadAsArray(buf_xsize=gw, buf_ysize=gh, resample_alg=gdal.GRIORA_Bilinear).astype(np.float32, copy=False)
    valid = np.isfinite(dem_data)
    if nodata is not None and math.isfinite(float(nodata)):
        valid &= dem_data != float(nodata)

    min_z = float(np.min(dem_data[valid])) if np.any(valid) else 0.0
    max_z = float(np.max(dem_data[valid])) if np.any(valid) else 1000.0
    if min_z >= max_z:
        max_z = min_z + 1.0
    mean_z = float(np.mean(dem_data[valid])) if np.any(valid) else 0.0
    std_z = float(np.std(dem_data[valid])) if np.any(valid) else 0.0

    clean_elev = np.where(valid, dem_data, min_z)
    clean_elev = np.nan_to_num(clean_elev, nan=min_z, posinf=max_z, neginf=min_z)
    elev_grid = clean_elev.round(1).tolist()

    slope_grid = _resample_band(slope_path, gw, gh, 0.0)
    twi_grid = _resample_band(twi_path, gw, gh, 0.0)
    suit_grid = _resample_band(suitability_path, gw, gh, 0.0)
    hazard_grid = _resample_band(hazard_path, gw, gh, 0.0)

    slope_mean = float(np.mean(np.array(slope_grid))) if slope_grid else 0.0
    slope_max = float(np.max(np.array(slope_grid))) if slope_grid else 0.0

    min_x = gt[0]
    max_x = gt[0] + orig_w * gt[1] + orig_h * gt[2]
    max_y = gt[3]
    min_y = gt[3] + orig_w * gt[4] + orig_h * gt[5]

    bounds_x = min(min_x, max_x), max(min_x, max_x)
    bounds_y = min(min_y, max_y), max(min_y, max_y)
    dx = max(1e-6, bounds_x[1] - bounds_x[0])
    dy = max(1e-6, bounds_y[1] - bounds_y[0])

    pixel_x_m = abs(gt[1])
    pixel_y_m = abs(gt[5])
    pixel_area_ha = (pixel_x_m * pixel_y_m) / 10000.0
    total_area_ha = pixel_area_ha * orig_w * orig_h

    center_x = (bounds_x[0] + bounds_x[1]) / 2.0
    center_y = (bounds_y[0] + bounds_y[1]) / 2.0
    center_lat, center_lon = 16.0, 108.0
    try:
        if proj:
            src_srs = osr.SpatialReference()
            src_srs.ImportFromWkt(proj)
            wgs84 = osr.SpatialReference()
            wgs84.ImportFromEPSG(4326)
            if hasattr(src_srs, "SetAxisMappingStrategy"):
                src_srs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
                wgs84.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
            transform = osr.CoordinateTransformation(src_srs, wgs84)
            res = transform.TransformPoint(center_x, center_y)
            center_lon, center_lat = float(res[0]), float(res[1])
    except Exception:
        pass

    rivers_3d = []
    total_stream_km = 0.0
    if stream_vector_path and os.path.exists(stream_vector_path):
        try:
            v_ds = ogr.Open(str(stream_vector_path))
            if v_ds is not None:
                layer = v_ds.GetLayer(0)
                for feat in layer:
                    geom = feat.GetGeometryRef()
                    if geom is None: continue
                    multi_pts = _extract_linestring_pts(geom, bounds_x, bounds_y, dx, dy)
                    order_val = feat.GetField("ORDER") if feat.GetFieldIndex("ORDER") >= 0 else 1
                    name_val = feat.GetField("ORDER_NAME") if feat.GetFieldIndex("ORDER_NAME") >= 0 else f"Order {order_val}"
                    length_m = feat.GetField("LENGTH_M") if feat.GetFieldIndex("LENGTH_M") >= 0 else 0.0
                    total_stream_km += float(length_m) / 1000.0
                    for pts in multi_pts:
                        rivers_3d.append({
                            "order": int(order_val or 1),
                            "name": str(name_val or ""),
                            "length_m": round(float(length_m or 0.0), 1),
                            "pts": pts,
                        })
                v_ds = None
        except Exception: pass

    contours_3d = []
    if contour_vector_path and os.path.exists(contour_vector_path):
        try:
            c_ds = ogr.Open(str(contour_vector_path))
            if c_ds is not None:
                c_layer = c_ds.GetLayer(0)
                for feat in c_layer:
                    geom = feat.GetGeometryRef()
                    if geom is None: continue
                    multi_pts = _extract_linestring_pts(geom, bounds_x, bounds_y, dx, dy)
                    elev_val = feat.GetField("ELEV") if feat.GetFieldIndex("ELEV") >= 0 else 0.0
                    is_index = feat.GetField("IS_INDEX") if feat.GetFieldIndex("IS_INDEX") >= 0 else 0
                    for pts in multi_pts:
                        contours_3d.append({
                            "elev": round(float(elev_val or 0.0), 1),
                            "is_index": bool(is_index),
                            "pts": pts,
                        })
                c_ds = None
        except Exception: pass

    peaks_3d = []
    if spot_peaks_path and os.path.exists(spot_peaks_path):
        try:
            p_ds = ogr.Open(str(spot_peaks_path))
            if p_ds is not None:
                p_layer = p_ds.GetLayer(0)
                for feat in p_layer:
                    geom = feat.GetGeometryRef()
                    if geom is None: continue
                    gx, gy = geom.GetX(), geom.GetY()
                    nx = ((gx - bounds_x[0]) / dx - 0.5) * 100.0
                    ny = ((gy - bounds_y[0]) / dy - 0.5) * 100.0
                    elev_val = feat.GetField("ELEV") if feat.GetFieldIndex("ELEV") >= 0 else 0.0
                    label_val = feat.GetField("LABEL") if feat.GetFieldIndex("LABEL") >= 0 else f"{int(elev_val)}m"
                    peaks_3d.append({
                        "x": round(nx, 2),
                        "y": round(ny, 2),
                        "z": round(float(elev_val), 1),
                        "gx": round(gx, 2),
                        "gy": round(gy, 2),
                        "label": str(label_val),
                    })
                p_ds = None
        except Exception: pass

    config_data = {
        "title": title,
        "gw": gw,
        "gh": gh,
        "min_z": float(min_z),
        "max_z": float(max_z),
        "mean_z": float(mean_z),
        "std_z": float(std_z),
        "slope_mean": float(slope_mean),
        "slope_max": float(slope_max),
        "pixel_x_m": float(pixel_x_m),
        "pixel_y_m": float(pixel_y_m),
        "pixel_area_ha": float(pixel_area_ha),
        "total_area_ha": float(total_area_ha),
        "center_lat": float(center_lat),
        "center_lon": float(center_lon),
        "proj_name": str(proj[:50] + "..." if len(proj)>50 else proj),
        "elev_grid": elev_grid,
        "slope_grid": slope_grid,
        "twi_grid": twi_grid,
        "suit_grid": suit_grid,
        "hazard_grid": hazard_grid,
        "rivers_3d": rivers_3d,
        "total_stream_km": round(total_stream_km, 2),
        "stream_count": len(rivers_3d),
        "contours_3d": contours_3d,
        "contour_count": len(contours_3d),
        "peaks_3d": peaks_3d,
        "peak_count": len(peaks_3d),
    }

    # HTML content without any python f-strings in JS code
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title} — 3D WebGIS Studio</title>
  <style>
    :root {{
      --bg: #090b10;
      --panel-bg: rgba(15, 20, 25, 0.85);
      --border: rgba(255, 255, 255, 0.1);
      --accent: hsl(210, 100%, 65%);
      --accent-hover: hsl(210, 100%, 75%);
      --text: #e2e8f0;
      --text-muted: #94a3b8;
      --danger: #ef4444;
      --success: #10b981;
    }}
    * {{ margin: 0; padding: 0; box-sizing: border-box; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }}
    body {{ background: var(--bg); color: var(--text); overflow: hidden; width: 100vw; height: 100vh; }}
    #canvas-container {{ width: 100vw; height: 100vh; position: absolute; top: 0; left: 0; }}
    
    .glass-panel {{
      background: var(--panel-bg);
      backdrop-filter: blur(20px);
      -webkit-backdrop-filter: blur(20px);
      border: 1px solid var(--border);
      border-radius: 12px;
      box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
    }}
    
    /* Top Toolbar */
    #top-toolbar {{
      position: absolute;
      top: 16px;
      left: 50%;
      transform: translateX(-50%);
      height: 44px;
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 0 8px;
      z-index: 100;
    }}
    .tool-btn {{
      background: transparent;
      border: none;
      color: var(--text);
      cursor: pointer;
      padding: 6px 12px;
      border-radius: 6px;
      font-size: 13px;
      font-weight: 500;
      transition: all 0.2s;
      display: flex;
      align-items: center;
      gap: 6px;
    }}
    .tool-btn:hover {{ background: rgba(255,255,255,0.1); color: var(--accent); }}
    .tool-btn.active {{ background: rgba(255,255,255,0.15); color: var(--accent); }}
    
    /* Left Sidebar */
    #sidebar {{
      position: absolute;
      top: 16px;
      left: 16px;
      width: 280px;
      height: calc(100vh - 32px);
      display: flex;
      flex-direction: column;
      z-index: 100;
      overflow: hidden;
    }}
    .sidebar-header {{
      padding: 16px;
      border-bottom: 1px solid var(--border);
    }}
    .brand-title {{
      font-size: 16px;
      font-weight: 600;
      margin-bottom: 4px;
      color: #fff;
      display: flex;
      align-items: center;
      gap: 8px;
    }}
    .live-badge {{
      font-size: 10px;
      background: var(--danger);
      color: #fff;
      padding: 2px 6px;
      border-radius: 4px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }}
    .dem-info {{
      font-size: 12px;
      color: var(--text-muted);
      margin-top: 8px;
      line-height: 1.4;
    }}
    
    /* Tabs */
    .tabs {{
      display: flex;
      border-bottom: 1px solid var(--border);
    }}
    .tab-btn {{
      flex: 1;
      background: transparent;
      border: none;
      color: var(--text-muted);
      padding: 10px 0;
      font-size: 12px;
      font-weight: 600;
      cursor: pointer;
      transition: color 0.2s;
    }}
    .tab-btn.active {{
      color: var(--accent);
      box-shadow: inset 0 -2px 0 var(--accent);
    }}
    
    .tab-content {{
      flex: 1;
      overflow-y: auto;
      padding: 16px;
      display: none;
    }}
    .tab-content.active {{
      display: block;
    }}
    
    /* Controls inside tabs */
    .control-group {{ margin-bottom: 16px; }}
    .control-label {{ font-size: 12px; font-weight: 600; margin-bottom: 8px; display: block; color: var(--text); }}
    
    select.premium-select {{
      width: 100%;
      background: rgba(0,0,0,0.2);
      border: 1px solid var(--border);
      color: var(--text);
      padding: 8px 12px;
      border-radius: 6px;
      font-size: 13px;
      outline: none;
      cursor: pointer;
      appearance: none;
    }}
    select.premium-select:hover {{ border-color: rgba(255,255,255,0.2); }}
    
    .overlay-toggle {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 8px;
      background: rgba(255,255,255,0.03);
      border-radius: 6px;
      margin-bottom: 6px;
      cursor: pointer;
      font-size: 12px;
      transition: background 0.2s;
    }}
    .overlay-toggle:hover {{ background: rgba(255,255,255,0.08); }}
    .overlay-toggle input {{ cursor: pointer; accent-color: var(--accent); }}
    
    .slider-row {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 6px;
      font-size: 12px;
    }}
    .slider-val {{ font-family: monospace; color: var(--accent); }}
    input[type=range] {{
      width: 100%;
      accent-color: var(--accent);
      cursor: pointer;
    }}
    
    .data-table {{ width: 100%; border-collapse: collapse; font-size: 12px; margin-bottom: 12px; }}
    .data-table td {{ padding: 6px 0; border-bottom: 1px solid rgba(255,255,255,0.05); }}
    .data-table td:nth-child(1) {{ color: var(--text-muted); }}
    .data-table td:nth-child(2) {{ text-align: right; font-family: monospace; color: #fff; }}
    
    /* Bottom Cards */
    #inspector-card {{
      position: absolute; bottom: 24px; left: 320px;
      padding: 16px; min-width: 240px;
      pointer-events: none; opacity: 0; transition: opacity 0.2s;
      z-index: 100;
    }}
    #inspector-card.visible {{ opacity: 1; }}
    .insp-title {{ font-size: 11px; font-weight: 700; color: var(--text-muted); text-transform: uppercase; margin-bottom: 8px; letter-spacing: 0.5px; }}
    .insp-elev {{ font-size: 24px; font-weight: 700; color: #fff; margin-bottom: 12px; font-family: monospace; }}
    .insp-row {{ display: flex; justify-content: space-between; font-size: 12px; margin-bottom: 4px; }}
    .insp-lbl {{ color: var(--text-muted); }}
    .insp-val {{ font-weight: 600; color: #fff; }}
    
    #legend-card {{
      position: absolute; bottom: 24px; right: 24px;
      padding: 16px; width: 260px;
      z-index: 100;
    }}
    .legend-title {{ font-size: 12px; font-weight: 600; margin-bottom: 12px; text-align: center; }}
    .legend-bar {{ width: 100%; height: 12px; border-radius: 6px; margin-bottom: 8px; }}
    .legend-labels {{ display: flex; justify-content: space-between; font-size: 11px; color: var(--text-muted); font-family: monospace; }}
    
    #profile-chart {{
      position: absolute; bottom: 24px; right: 300px;
      width: 400px; padding: 16px; display: none; z-index: 100;
    }}
  </style>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
  <!-- JSON Data Block -->
  <script id="terrain-data" type="application/json">{json.dumps(config_data)}</script>
</head>
<body>
  <div id="canvas-container"></div>
  
  <div id="top-toolbar" class="glass-panel">
    <button class="tool-btn" id="btn-reset">🎯 Reset Camera</button>
    <button class="tool-btn" id="btn-autorotate">🔄 Auto-Rotate</button>
    <button class="tool-btn" id="btn-wireframe">🕸️ Wireframe</button>
    <button class="tool-btn" id="btn-ortho">📐 Orthographic</button>
    <button class="tool-btn" id="btn-snap">📷 Snapshot</button>
  </div>
  
  <div id="sidebar" class="glass-panel">
    <div class="sidebar-header">
      <div class="brand-title">Terrain 3D Studio <span class="live-badge">Live</span></div>
      <div class="dem-info" id="sidebar-dem-info">Loading...</div>
    </div>
    
    <div class="tabs">
      <button class="tab-btn active" data-tab="layers">Layers</button>
      <button class="tab-btn" data-tab="tools">Tools</button>
      <button class="tab-btn" data-tab="scene">Scene</button>
      <button class="tab-btn" data-tab="data">Data</button>
    </div>
    
    <!-- Layers Tab -->
    <div class="tab-content active" id="tab-layers">
      <div class="control-group">
        <label class="control-label">Base Surface Layer</label>
        <select id="layer-select" class="premium-select">
          <option value="topo">Elevation (Hypsometric)</option>
          <option value="slope">Slope Gradient</option>
          <option value="twi">Topographic Wetness (TWI)</option>
          <option value="suitability">Construction Suitability</option>
          <option value="hazard">Landslide Hazard</option>
          <option value="shaded">Shaded Relief</option>
        </select>
      </div>
      
      <div class="control-group">
        <label class="control-label">Overlays</label>
        <label class="overlay-toggle">
          <span>Drainage Network <span id="lbl-riv-cnt" style="color:var(--text-muted);font-size:10px;"></span></span>
          <input type="checkbox" id="chk-rivers" checked />
        </label>
        <label class="overlay-toggle">
          <span>Topographic Contours <span id="lbl-cnt-cnt" style="color:var(--text-muted);font-size:10px;"></span></span>
          <input type="checkbox" id="chk-contours" checked />
        </label>
        <label class="overlay-toggle">
          <span>Spot Elevation Peaks <span id="lbl-pk-cnt" style="color:var(--text-muted);font-size:10px;"></span></span>
          <input type="checkbox" id="chk-peaks" checked />
        </label>
        <label class="overlay-toggle">
          <span>Coordinate Grid</span>
          <input type="checkbox" id="chk-grid" checked />
        </label>
      </div>
    </div>
    
    <!-- Tools Tab -->
    <div class="tab-content" id="tab-tools">
      <div class="control-group">
        <label class="control-label">Vertical Exaggeration</label>
        <div class="slider-row">
          <span>Scale</span>
          <span class="slider-val" id="lbl-exag">1.5x</span>
        </div>
        <input type="range" id="slider-exag" min="0.2" max="5.0" step="0.1" value="1.5" />
      </div>
      
      <div class="control-group">
        <label class="control-label">Cross-Section Profile</label>
        <button class="tool-btn" id="btn-profile" style="width:100%; justify-content:center; background:rgba(0,0,0,0.2); border:1px solid var(--border);">📏 Draw Profile Line</button>
      </div>
      
      <div class="control-group">
        <label class="control-label">Flood Simulation</label>
        <div class="slider-row">
          <span>Water Level</span>
          <span class="slider-val" id="lbl-flood">--</span>
        </div>
        <input type="range" id="slider-flood" value="0" />
        <div id="flood-stats" style="font-size:11px; color:var(--accent); margin-top:8px;">Inactive</div>
      </div>
      
      <div class="control-group">
        <label class="control-label">Solar Shadow Analysis</label>
        <div class="slider-row">
          <span>Time of Day</span>
          <span class="slider-val" id="lbl-hour">12:00</span>
        </div>
        <input type="range" id="slider-hour" min="5.5" max="18.5" step="0.1" value="12.0" />
      </div>
    </div>
    
    <!-- Scene Tab -->
    <div class="tab-content" id="tab-scene">
      <div class="control-group">
        <label class="control-label">Sky Background</label>
        <select id="bg-select" class="premium-select">
          <option value="night">Night Sky (Dark)</option>
          <option value="twilight">Twilight Blue</option>
          <option value="day">Bright Day</option>
        </select>
      </div>
      <div class="control-group">
        <label class="control-label">Atmospheric Fog</label>
        <div class="slider-row">
          <span>Density</span>
          <span class="slider-val" id="lbl-fog">Medium</span>
        </div>
        <input type="range" id="slider-fog" min="0" max="0.01" step="0.001" value="0.003" />
      </div>
      <div class="control-group">
        <label class="overlay-toggle">
          <span>Anti-Aliasing (FXAA/MSAA)</span>
          <input type="checkbox" id="chk-aa" checked disabled />
        </label>
      </div>
    </div>
    
    <!-- Data Tab -->
    <div class="tab-content" id="tab-data">
      <div class="control-group">
        <label class="control-label">Terrain Statistics</label>
        <table class="data-table" id="data-stats"></table>
      </div>
      <div class="control-group">
        <label class="control-label">Spatial Reference</label>
        <div style="font-size:11px; color:var(--text-muted); word-break:break-all; background:rgba(0,0,0,0.3); padding:8px; border-radius:6px;" id="data-crs"></div>
      </div>
    </div>
  </div>
  
  <div id="inspector-card" class="glass-panel">
    <div class="insp-title">Live Inspector</div>
    <div class="insp-elev" id="insp-z">-- m</div>
    <div class="insp-row"><span class="insp-lbl">Slope</span><span class="insp-val" id="insp-slope">--</span></div>
    <div class="insp-row"><span class="insp-lbl">TWI</span><span class="insp-val" id="insp-twi">--</span></div>
    <div class="insp-row"><span class="insp-lbl">Suitability</span><span class="insp-val" id="insp-suit">--</span></div>
    <div class="insp-row"><span class="insp-lbl">Hazard</span><span class="insp-val" id="insp-hazard">--</span></div>
    <div style="margin-top:8px; padding-top:8px; border-top:1px solid rgba(255,255,255,0.1); font-size:10px; color:var(--text-muted); text-align:right;" id="insp-coords">X: -- Y: --</div>
  </div>
  
  <div id="legend-card" class="glass-panel">
    <div class="legend-title" id="legend-title">Elevation (m)</div>
    <div class="legend-bar" id="legend-bar" style="background: linear-gradient(to right, #2b83ba, #abdda4, #ffffbf, #fdae61, #d7191c);"></div>
    <div class="legend-labels">
      <span id="leg-min">0</span>
      <span id="leg-mid">500</span>
      <span id="leg-max">1000</span>
    </div>
  </div>
  
  <div id="profile-chart" class="glass-panel">
    <div style="display:flex; justify-content:space-between; margin-bottom:12px;">
      <span style="font-size:13px; font-weight:600;">Cross-Section Profile</span>
      <button class="tool-btn" id="btn-close-profile" style="padding:2px 6px; font-size:10px;">✕</button>
    </div>
    <div id="profile-svg" style="width:100%; height:120px; background:rgba(0,0,0,0.3); border-radius:6px; overflow:hidden; position:relative;">
       <div id="profile-msg" style="position:absolute; top:50%; left:50%; transform:translate(-50%,-50%); font-size:12px; color:var(--text-muted);">Click two points on terrain</div>
    </div>
  </div>
  
  <script>
    // Minimal OrbitControls Implementation
    class MinimalOrbitControls {{
      constructor(camera, domElement) {{
        this.camera = camera;
        this.domElement = domElement;
        this.target = new THREE.Vector3(0, 0, 0);
        this.rotateSpeed = 0.6;
        this.zoomSpeed = 1.15;
        this.autoRotate = false;
        this.autoRotateSpeed = 1.0;

        // Terrain lies on XY plane, Z is up.
        // We orbit using azimuth (horizontal) and elevation (vertical tilt).
        // Derive initial angles from the camera position.
        const dx = camera.position.x - this.target.x;
        const dy = camera.position.y - this.target.y;
        const dz = camera.position.z - this.target.z;
        this.radius = Math.sqrt(dx*dx + dy*dy + dz*dz);
        this.azimuth = Math.atan2(dy, dx);          // horizontal rotation
        this.elevation = Math.asin(dz / this.radius); // vertical tilt (0=horizon, PI/2=top)
        this.elevation = Math.max(0.05, Math.min(Math.PI / 2 - 0.01, this.elevation));

        this._isDragging = false;
        this._prevMouse = {{ x: 0, y: 0 }};

        domElement.addEventListener('mousedown', e => {{
          this._isDragging = true;
          this._prevMouse = {{ x: e.clientX, y: e.clientY }};
          e.preventDefault();
        }});
        window.addEventListener('mousemove', e => {{
          if (!this._isDragging) return;
          const dx = e.clientX - this._prevMouse.x;
          const dy = e.clientY - this._prevMouse.y;
          // Horizontal drag → rotate around Z (azimuth)
          this.azimuth -= dx * 0.008 * this.rotateSpeed;
          // Vertical drag → change elevation angle
          this.elevation += dy * 0.008 * this.rotateSpeed;
          this.elevation = Math.max(0.05, Math.min(Math.PI / 2 - 0.01, this.elevation));
          this._prevMouse = {{ x: e.clientX, y: e.clientY }};
          this._applyCamera();
        }});
        window.addEventListener('mouseup', () => {{ this._isDragging = false; }});
        domElement.addEventListener('wheel', e => {{
          e.preventDefault();
          this.radius *= e.deltaY > 0 ? this.zoomSpeed : (1 / this.zoomSpeed);
          this.radius = Math.max(10, Math.min(2000, this.radius));
          this._applyCamera();
        }}, {{ passive: false }});

        // Touch support
        let _t0 = null, _t1 = null, _tDist = 0;
        domElement.addEventListener('touchstart', e => {{
          if (e.touches.length === 1) {{
            this._isDragging = true;
            this._prevMouse = {{ x: e.touches[0].clientX, y: e.touches[0].clientY }};
          }} else if (e.touches.length === 2) {{
            _t0 = e.touches[0]; _t1 = e.touches[1];
            _tDist = Math.hypot(_t1.clientX-_t0.clientX, _t1.clientY-_t0.clientY);
          }}
          e.preventDefault();
        }}, {{ passive: false }});
        domElement.addEventListener('touchmove', e => {{
          if (e.touches.length === 1 && this._isDragging) {{
            const dx2 = e.touches[0].clientX - this._prevMouse.x;
            const dy2 = e.touches[0].clientY - this._prevMouse.y;
            this.azimuth -= dx2 * 0.008 * this.rotateSpeed;
            this.elevation += dy2 * 0.008 * this.rotateSpeed;
            this.elevation = Math.max(0.05, Math.min(Math.PI / 2 - 0.01, this.elevation));
            this._prevMouse = {{ x: e.touches[0].clientX, y: e.touches[0].clientY }};
            this._applyCamera();
          }} else if (e.touches.length === 2) {{
            const newDist = Math.hypot(e.touches[1].clientX-e.touches[0].clientX, e.touches[1].clientY-e.touches[0].clientY);
            this.radius *= (_tDist / newDist);
            this.radius = Math.max(10, Math.min(2000, this.radius));
            _tDist = newDist;
            this._applyCamera();
          }}
          e.preventDefault();
        }}, {{ passive: false }});
        domElement.addEventListener('touchend', () => {{ this._isDragging = false; }});

        this._applyCamera();
      }}

      _applyCamera() {{
        // Convert spherical (azimuth, elevation) with Z-up into Cartesian
        const cosEl = Math.cos(this.elevation);
        this.camera.position.set(
          this.target.x + this.radius * cosEl * Math.cos(this.azimuth),
          this.target.y + this.radius * cosEl * Math.sin(this.azimuth),
          this.target.z + this.radius * Math.sin(this.elevation)
        );
        this.camera.up.set(0, 0, 1);
        this.camera.lookAt(this.target);
      }}

      update() {{
        if (this.autoRotate) {{
          this.azimuth -= 0.004 * this.autoRotateSpeed;
          this._applyCamera();
        }}
      }}
    }}

    // App Initialization
    const CFG = JSON.parse(document.getElementById('terrain-data').textContent);
    
    // UI Setup
    document.getElementById('sidebar-dem-info').innerHTML = `Resolution: ${{CFG.pixel_x_m.toFixed(1)}}m × ${{CFG.pixel_y_m.toFixed(1)}}m<br>Area: ${{CFG.total_area_ha.toFixed(1)}} ha | Grid: ${{CFG.gw}}×${{CFG.gh}}`;
    document.getElementById('lbl-riv-cnt').textContent = `(${{CFG.stream_count}})`;
    document.getElementById('lbl-cnt-cnt').textContent = `(${{CFG.contour_count}})`;
    document.getElementById('lbl-pk-cnt').textContent = `(${{CFG.peak_count}})`;
    
    document.getElementById('slider-flood').min = CFG.min_z;
    document.getElementById('slider-flood').max = CFG.max_z;
    document.getElementById('slider-flood').step = (CFG.max_z - CFG.min_z) / 100;
    document.getElementById('slider-flood').value = CFG.min_z;
    document.getElementById('lbl-flood').textContent = CFG.min_z.toFixed(1) + 'm';
    
    document.getElementById('data-stats').innerHTML = `
      <tr><td>Min Elevation</td><td>${{CFG.min_z.toFixed(1)}} m</td></tr>
      <tr><td>Max Elevation</td><td>${{CFG.max_z.toFixed(1)}} m</td></tr>
      <tr><td>Mean Elevation</td><td>${{CFG.mean_z.toFixed(1)}} m</td></tr>
      <tr><td>Elevation StdDev</td><td>${{CFG.std_z.toFixed(1)}} m</td></tr>
      <tr><td>Mean Slope</td><td>${{CFG.slope_mean.toFixed(1)}}°</td></tr>
      <tr><td>Total Stream Length</td><td>${{CFG.total_stream_km.toFixed(1)}} km</td></tr>
      <tr><td>Center Lat/Lon</td><td>${{CFG.center_lat.toFixed(4)}}°, ${{CFG.center_lon.toFixed(4)}}°</td></tr>
    `;
    document.getElementById('data-crs').textContent = CFG.proj_name;
    
    // Tabs Logic
    document.querySelectorAll('.tab-btn').forEach(btn => {{
      btn.addEventListener('click', () => {{
        document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
        document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
        btn.classList.add('active');
        document.getElementById(`tab-${{btn.dataset.tab}}`).classList.add('active');
      }});
    }});
    
    // Three.js Setup
    const container = document.getElementById("canvas-container");
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x090b10);
    scene.fog = new THREE.FogExp2(0x090b10, 0.003);
    
    let isOrthographic = false;
    let persCamera = new THREE.PerspectiveCamera(45, window.innerWidth / window.innerHeight, 0.1, 4000);
    persCamera.position.set(0, -120, 100);
    
    const aspect = window.innerWidth / window.innerHeight;
    const frustumSize = 150;
    let orthoCamera = new THREE.OrthographicCamera(frustumSize * aspect / -2, frustumSize * aspect / 2, frustumSize / 2, frustumSize / -2, 0.1, 4000);
    orthoCamera.position.set(0, 0, 150);
    
    let camera = persCamera;
    
    const renderer = new THREE.WebGLRenderer({{ antialias: true, preserveDrawingBuffer: true, alpha: false }});
    renderer.setSize(window.innerWidth, window.innerHeight);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    container.appendChild(renderer.domElement);
    
    let controls = new MinimalOrbitControls(camera, renderer.domElement);
    
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.5);
    scene.add(ambientLight);
    
    const hemiLight = new THREE.HemisphereLight(0xebf4fa, 0x2b2b2b, 0.4);
    scene.add(hemiLight);
    
    const sunLight = new THREE.DirectionalLight(0xfffaed, 1.2);
    sunLight.castShadow = true;
    sunLight.shadow.mapSize.width = 2048;
    sunLight.shadow.mapSize.height = 2048;
    scene.add(sunLight);
    
    function updateSunPosition(hour) {{
      const t = (hour - 6) / 12; // 0 at 6am, 1 at 6pm
      const angle = t * Math.PI;
      const x = Math.cos(angle) * -150;
      const z = Math.sin(angle) * 150;
      sunLight.position.set(x, 50, z);
    }}
    updateSunPosition(12.0);
    
    // Palettes
    const PALETTES = {{
      topo: ['#2b83ba', '#abdda4', '#ffffbf', '#fdae61', '#d7191c'],
      slope: ['#1a9850', '#a6d96a', '#ffffbf', '#fdae61', '#d73027'],
      twi: ['#d7191c', '#fdae61', '#ffffbf', '#abd9e9', '#2c7bb6'],
      suitability: ['#1a9850', '#91cf60', '#d9ef8b', '#fee08b', '#fc8d59'],
      hazard: ['#2b83ba', '#ffffbf', '#fdae61', '#d7191c'],
      shaded: ['#d9d9d9', '#f2f2f2']
    }};
    
    function getPaletteColor(palKey, norm) {{
      const hexes = PALETTES[palKey] || PALETTES.topo;
      const cStops = hexes.map(h => new THREE.Color(h));
      const idx = Math.max(0, Math.min(1, norm)) * (cStops.length - 1);
      const i = Math.floor(idx);
      if (i >= cStops.length - 1) return cStops[cStops.length - 1];
      return cStops[i].clone().lerp(cStops[i+1], idx - i);
    }}
    
    // Mesh
    const GW = CFG.gw, GH = CFG.gh;
    const Z_SPAN = Math.max(1.0, CFG.max_z - CFG.min_z);
    const planeGeom = new THREE.PlaneGeometry(100, 100 * (GH / GW), GW - 1, GH - 1);
    let currentExag = 1.5;
    let currentLayer = "topo";
    
    function updateMeshColors() {{
      const cols = [];
      for (let r = 0; r < GH; r++) {{
        for (let c = 0; c < GW; c++) {{
          let valNorm = 0.5;
          if (currentLayer === "topo") valNorm = (CFG.elev_grid[r][c] - CFG.min_z) / Z_SPAN;
          else if (currentLayer === "slope" && CFG.slope_grid) valNorm = Math.min(1, CFG.slope_grid[r][c] / 45.0);
          else if (currentLayer === "twi" && CFG.twi_grid) valNorm = Math.min(1, CFG.twi_grid[r][c] / 20.0);
          else if (currentLayer === "suitability" && CFG.suit_grid) valNorm = Math.max(0, Math.min(1, (CFG.suit_grid[r][c] - 1) / 4.0));
          else if (currentLayer === "hazard" && CFG.hazard_grid) valNorm = Math.max(0, Math.min(1, (CFG.hazard_grid[r][c] - 1) / 3.0));
          else valNorm = (CFG.elev_grid[r][c] - CFG.min_z) / Z_SPAN;
          const color = getPaletteColor(currentLayer, valNorm);
          cols.push(color.r, color.g, color.b);
        }}
      }}
      planeGeom.setAttribute("color", new THREE.Float32BufferAttribute(cols, 3));
    }}
    
    function updateMeshHeights() {{
      const pos = planeGeom.attributes.position;
      for (let r = 0; r < GH; r++) {{
        for (let c = 0; c < GW; c++) {{
          const normZ = (CFG.elev_grid[r][c] - CFG.min_z) / Z_SPAN;
          pos.setZ(r * GW + c, normZ * 25.0 * currentExag);
        }}
      }}
      pos.needsUpdate = true;
      planeGeom.computeVertexNormals();
    }}
    
    updateMeshColors();
    updateMeshHeights();
    
    const terrainMat = new THREE.MeshStandardMaterial({{ vertexColors: true, roughness: 0.7, metalness: 0.1, side: THREE.DoubleSide }});
    const terrainMesh = new THREE.Mesh(planeGeom, terrainMat);
    terrainMesh.receiveShadow = true;
    terrainMesh.castShadow = true;
    scene.add(terrainMesh);
    
    // Flood
    const floodGeom = new THREE.PlaneGeometry(100, 100 * (GH / GW), 32, 32);
    const floodMat = new THREE.MeshStandardMaterial({{ color: 0x0ea5e9, transparent: true, opacity: 0.7, roughness: 0.1, metalness: 0.5 }});
    const floodMesh = new THREE.Mesh(floodGeom, floodMat);
    floodMesh.visible = false;
    scene.add(floodMesh);
    
    // Overlays
    const riverGroup = new THREE.Group();
    CFG.rivers_3d.forEach(riv => {{
      const pts = [];
      const col = riv.order >= 4 ? 0x1e3a8a : (riv.order === 3 ? 0x1d4ed8 : (riv.order === 2 ? 0x2563eb : 0x60a5fa));
      riv.pts.forEach(p => {{
        const cu = Math.max(0, Math.min(GW - 1, Math.round((p[0]/100+0.5)*(GW-1))));
        const cv = Math.max(0, Math.min(GH - 1, Math.round((p[1]/(100*(GH/GW))+0.5)*(GH-1))));
        const zNorm = (CFG.elev_grid[cv][cu] - CFG.min_z) / Z_SPAN;
        pts.push(new THREE.Vector3(p[0], p[1], zNorm * 25.0 * currentExag + 0.3));
      }});
      if (pts.length > 1) riverGroup.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts), new THREE.LineBasicMaterial({{color: col}})));
    }});
    scene.add(riverGroup);
    
    const contourGroup = new THREE.Group();
    CFG.contours_3d.forEach(c => {{
      const pts = [];
      c.pts.forEach(p => pts.push(new THREE.Vector3(p[0], p[1], ((c.elev - CFG.min_z) / Z_SPAN) * 25.0 * currentExag + 0.15)));
      if (pts.length > 1) contourGroup.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts), new THREE.LineBasicMaterial({{color: c.is_index ? 0x854d0e : 0xa16207, transparent: true, opacity: c.is_index ? 0.9 : 0.5}})));
    }});
    scene.add(contourGroup);
    
    const peakGroup = new THREE.Group();
    CFG.peaks_3d.forEach(pk => {{
      const cone = new THREE.Mesh(new THREE.ConeGeometry(0.8, 2, 4), new THREE.MeshBasicMaterial({{color: 0xef4444}}));
      cone.rotateX(Math.PI/2);
      cone.position.set(pk.x, pk.y, ((pk.z - CFG.min_z) / Z_SPAN) * 25.0 * currentExag + 1.2);
      peakGroup.add(cone);
    }});
    scene.add(peakGroup);
    
    const gridHelper = new THREE.GridHelper(100, 10, 0x334155, 0x1e293b);
    gridHelper.rotation.x = Math.PI/2;
    gridHelper.position.z = -0.5;
    scene.add(gridHelper);
    
    // Interactions
    document.getElementById('slider-exag').addEventListener('input', e => {{
      currentExag = parseFloat(e.target.value);
      document.getElementById('lbl-exag').textContent = currentExag.toFixed(1) + 'x';
      updateMeshHeights();
      
      // Update overlays heights
      riverGroup.children.forEach((l, i) => {{
        const pts = l.geometry.attributes.position;
        const riv = CFG.rivers_3d[i];
        riv.pts.forEach((p, pi) => {{
          const cu = Math.max(0, Math.min(GW-1, Math.round((p[0]/100+0.5)*(GW-1))));
          const cv = Math.max(0, Math.min(GH-1, Math.round((p[1]/(100*(GH/GW))+0.5)*(GH-1))));
          pts.setZ(pi, ((CFG.elev_grid[cv][cu]-CFG.min_z)/Z_SPAN) * 25.0 * currentExag + 0.3);
        }});
        pts.needsUpdate = true;
      }});
      contourGroup.children.forEach((l, i) => {{
        const pts = l.geometry.attributes.position;
        const c = CFG.contours_3d[i];
        c.pts.forEach((p, pi) => pts.setZ(pi, ((c.elev-CFG.min_z)/Z_SPAN) * 25.0 * currentExag + 0.15));
        pts.needsUpdate = true;
      }});
      peakGroup.children.forEach((m, i) => {{
        m.position.z = ((CFG.peaks_3d[i].z-CFG.min_z)/Z_SPAN) * 25.0 * currentExag + 1.2;
      }});
    }});
    
    document.getElementById('layer-select').addEventListener('change', e => {{
      currentLayer = e.target.value;
      updateMeshColors();
      
      const pal = PALETTES[currentLayer] || PALETTES.topo;
      document.getElementById('legend-bar').style.background = `linear-gradient(to right, ${{pal.join(', ')}})`;
      
      const legMin = document.getElementById('leg-min');
      const legMid = document.getElementById('leg-mid');
      const legMax = document.getElementById('leg-max');
      const title = document.getElementById('legend-title');
      
      if (currentLayer === 'topo') {{ title.textContent = 'Elevation (m)'; legMin.textContent = CFG.min_z.toFixed(0); legMid.textContent = ((CFG.min_z+CFG.max_z)/2).toFixed(0); legMax.textContent = CFG.max_z.toFixed(0); }}
      else if (currentLayer === 'slope') {{ title.textContent = 'Slope (°)'; legMin.textContent = '0'; legMid.textContent = '22'; legMax.textContent = '45+'; }}
      else if (currentLayer === 'twi') {{ title.textContent = 'TWI'; legMin.textContent = '0'; legMid.textContent = '10'; legMax.textContent = '20+'; }}
      else if (currentLayer === 'suitability') {{ title.textContent = 'Suitability Class'; legMin.textContent = '1'; legMid.textContent = '3'; legMax.textContent = '5'; }}
      else if (currentLayer === 'hazard') {{ title.textContent = 'Hazard Class'; legMin.textContent = '1'; legMid.textContent = '2'; legMax.textContent = '4'; }}
      else {{ title.textContent = 'Shaded Relief'; legMin.textContent = 'Shadow'; legMid.textContent = ''; legMax.textContent = 'Light'; }}
    }});
    
    document.getElementById('chk-rivers').addEventListener('change', e => riverGroup.visible = e.target.checked);
    document.getElementById('chk-contours').addEventListener('change', e => contourGroup.visible = e.target.checked);
    document.getElementById('chk-peaks').addEventListener('change', e => peakGroup.visible = e.target.checked);
    document.getElementById('chk-grid').addEventListener('change', e => gridHelper.visible = e.target.checked);
    
    document.getElementById('slider-flood').addEventListener('input', e => {{
      const val = parseFloat(e.target.value);
      document.getElementById('lbl-flood').textContent = val.toFixed(1) + 'm';
      if (val <= CFG.min_z) {{
        floodMesh.visible = false;
        document.getElementById('flood-stats').textContent = 'Inactive';
        return;
      }}
      floodMesh.visible = true;
      floodMesh.position.z = ((val - CFG.min_z) / Z_SPAN) * 25.0 * currentExag;
      
      let fCount = 0;
      for (let r=0; r<GH; r++) for (let c=0; c<GW; c++) if (CFG.elev_grid[r][c] <= val) fCount++;
      const fArea = fCount * CFG.pixel_area_ha;
      document.getElementById('flood-stats').textContent = `Inundated: ${{fArea.toFixed(1)}} ha (${{(fCount/(GW*GH)*100).toFixed(1)}}%)`;
    }});
    
    document.getElementById('slider-hour').addEventListener('input', e => {{
      const h = parseFloat(e.target.value);
      const hrs = Math.floor(h);
      const mns = Math.floor((h - hrs) * 60).toString().padStart(2, '0');
      document.getElementById('lbl-hour').textContent = `${{hrs}}:${{mns}}`;
      updateSunPosition(h);
    }});
    
    document.getElementById('bg-select').addEventListener('change', e => {{
      const v = e.target.value;
      let col = 0x090b10;
      if (v === 'twilight') col = 0x1e1b4b;
      if (v === 'day') col = 0x38bdf8;
      scene.background = new THREE.Color(col);
      scene.fog.color = new THREE.Color(col);
    }});
    
    document.getElementById('slider-fog').addEventListener('input', e => scene.fog.density = parseFloat(e.target.value));
    document.getElementById('lbl-fog').textContent = document.getElementById('slider-fog').value;
    
    // Top Toolbar Buttons
    document.getElementById('btn-reset').addEventListener('click', () => {{
      controls.spherical.set(150, Math.PI/3, 0);
      controls.target.set(0,0,0);
      controls.updateCamera();
    }});
    document.getElementById('btn-autorotate').addEventListener('click', e => {{
      controls.autoRotate = !controls.autoRotate;
      e.target.classList.toggle('active', controls.autoRotate);
    }});
    document.getElementById('btn-wireframe').addEventListener('click', e => {{
      terrainMat.wireframe = !terrainMat.wireframe;
      e.target.classList.toggle('active', terrainMat.wireframe);
    }});
    document.getElementById('btn-ortho').addEventListener('click', e => {{
      isOrthographic = !isOrthographic;
      if (isOrthographic) {{
        orthoCamera.position.copy(camera.position);
        orthoCamera.quaternion.copy(camera.quaternion);
        camera = orthoCamera;
      }} else {{
        persCamera.position.copy(camera.position);
        persCamera.quaternion.copy(camera.quaternion);
        camera = persCamera;
      }}
      controls.camera = camera;
      controls.spherical.setFromVector3(camera.position.clone().sub(controls.target));
      e.target.classList.toggle('active', isOrthographic);
    }});
    document.getElementById('btn-snap').addEventListener('click', () => {{
      renderer.render(scene, camera);
      const a = document.createElement('a');
      a.href = renderer.domElement.toDataURL('image/png');
      a.download = 'terrain_3d_snapshot.png';
      a.click();
    }});
    
    // Raycaster for Inspector and Profile
    const raycaster = new THREE.Raycaster();
    const mouse = new THREE.Vector2();
    const inspCard = document.getElementById('inspector-card');
    let profileMode = false;
    let ptA = null;
    let ptB = null;
    
    document.getElementById('btn-profile').addEventListener('click', e => {{
      profileMode = true; ptA = null; ptB = null;
      document.getElementById('profile-chart').style.display = 'block';
      document.getElementById('profile-msg').textContent = 'Click Point A on terrain...';
      e.target.classList.add('active');
    }});
    document.getElementById('btn-close-profile').addEventListener('click', () => {{
      profileMode = false; ptA = null; ptB = null;
      document.getElementById('profile-chart').style.display = 'none';
      document.getElementById('btn-profile').classList.remove('active');
    }});
    
    window.addEventListener('mousemove', e => {{
      if (e.target.tagName !== 'CANVAS') {{ inspCard.classList.remove('visible'); return; }}
      mouse.x = (e.clientX / window.innerWidth) * 2 - 1;
      mouse.y = -(e.clientY / window.innerHeight) * 2 + 1;
      raycaster.setFromCamera(mouse, camera);
      const intersects = raycaster.intersectObject(terrainMesh);
      if (intersects.length > 0) {{
        inspCard.classList.add('visible');
        const pt = intersects[0].point;
        const u = (pt.x/100+0.5)*(GW-1), v = (pt.y/(100*(GH/GW))+0.5)*(GH-1);
        const cu = Math.max(0, Math.min(GW-1, Math.round(u))), cv = Math.max(0, Math.min(GH-1, Math.round(v)));
        
        document.getElementById('insp-z').textContent = CFG.elev_grid[cv][cu].toFixed(1) + ' m';
        document.getElementById('insp-slope').textContent = CFG.slope_grid ? CFG.slope_grid[cv][cu].toFixed(1) + '°' : '--';
        document.getElementById('insp-twi').textContent = CFG.twi_grid ? CFG.twi_grid[cv][cu].toFixed(1) : '--';
        document.getElementById('insp-suit').textContent = CFG.suit_grid ? CFG.suit_grid[cv][cu] : '--';
        document.getElementById('insp-hazard').textContent = CFG.hazard_grid ? CFG.hazard_grid[cv][cu] : '--';
        document.getElementById('insp-coords').textContent = `X: ${{(CFG.center_lon + (cu-GW/2)*0.0001).toFixed(4)}} Y: ${{(CFG.center_lat - (cv-GH/2)*0.0001).toFixed(4)}}`;
      }} else {{
        inspCard.classList.remove('visible');
      }}
    }});
    
    window.addEventListener('click', e => {{
      if (!profileMode || e.target.tagName !== 'CANVAS') return;
      raycaster.setFromCamera(mouse, camera);
      const intersects = raycaster.intersectObject(terrainMesh);
      if (intersects.length > 0) {{
        const pt = intersects[0].point;
        const u = (pt.x/100+0.5)*(GW-1), v = (pt.y/(100*(GH/GW))+0.5)*(GH-1);
        const cu = Math.max(0, Math.min(GW-1, Math.round(u))), cv = Math.max(0, Math.min(GH-1, Math.round(v)));
        
        if (!ptA) {{
          ptA = {{cu, cv}};
          document.getElementById('profile-msg').textContent = 'Click Point B on terrain...';
        }} else if (!ptB) {{
          ptB = {{cu, cv}};
          document.getElementById('profile-msg').style.display = 'none';
          
          // Draw simple SVG profile
          const steps = 50;
          let maxZ = -9999, minZ = 9999;
          const profElevs = [];
          for(let i=0; i<=steps; i++) {{
            const t = i/steps;
            const ru = Math.round(ptA.cu + t*(ptB.cu - ptA.cu));
            const rv = Math.round(ptA.cv + t*(ptB.cv - ptA.cv));
            const ccu = Math.max(0, Math.min(GW-1, ru));
            const ccv = Math.max(0, Math.min(GH-1, rv));
            const z = CFG.elev_grid[ccv][ccu];
            profElevs.push(z);
            if(z>maxZ) maxZ=z; if(z<minZ) minZ=z;
          }}
          
          let svg = `<svg width="100%" height="100%" viewBox="0 0 100 100" preserveAspectRatio="none">`;
          const pts = profElevs.map((z, i) => {{
            const x = (i/steps)*100;
            const y = 100 - ((z-minZ)/(maxZ-minZ || 1))*80 - 10;
            return `${{x}},${{y}}`;
          }});
          svg += `<polyline points="${{pts.join(' ')}}" fill="none" stroke="var(--accent)" stroke-width="2" />`;
          svg += `</svg><div style="position:absolute;top:4px;left:8px;font-size:10px;">Max: ${{maxZ.toFixed(1)}}m</div><div style="position:absolute;bottom:4px;left:8px;font-size:10px;">Min: ${{minZ.toFixed(1)}}m</div>`;
          document.getElementById('profile-svg').innerHTML = svg;
          
          profileMode = false;
          document.getElementById('btn-profile').classList.remove('active');
        }}
      }}
    }});
    
    window.addEventListener('resize', () => {{
      const aspect = window.innerWidth / window.innerHeight;
      persCamera.aspect = aspect; persCamera.updateProjectionMatrix();
      orthoCamera.left = frustumSize * aspect / -2; orthoCamera.right = frustumSize * aspect / -2;
      orthoCamera.updateProjectionMatrix();
      renderer.setSize(window.innerWidth, window.innerHeight);
    }});
    
    function animate() {{
      requestAnimationFrame(animate);
      controls.update();
      renderer.render(scene, camera);
    }}
    animate();
  </script>
</body>
</html>"""
    
    with open(output_html_path, "w", encoding="utf-8") as f:
        f.write(html)
        
    return output_html_path
