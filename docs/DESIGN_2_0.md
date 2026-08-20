# Terrain Product Studio 2.0.0 — Design Document

> Tài liệu lịch sử. Kể từ v2.2.0, master pipeline chạy hydrology trước các
> sản phẩm phụ thuộc dòng chảy và không còn dùng accumulation cache hoặc slope
> proxy. Xem `AGENTS.md` và `core/pipeline.py` cho contract hiện hành.

> Trạng thái: **đề xuất, chưa code**. Ngày: 2026-08-18.
> Mục tiêu của 2.0.0: **Publication-grade** — đẹp hơn, phân tích sâu hơn, chia sẻ dễ hơn. Mỗi milestone độc lập và ship được.

## 0. Vấn đề phát hiện trong code hiện tại (nên sửa kèm 2.0)

1. **BUG — Landslide hazard dùng sai input accumulation** (`build_package.py:710`):
   `calculate_landslide_hazard(outputs[self.SLOPE], outputs[self.SLOPE], ...)` — tham số `accumulation_path` nhận chính raster **slope** (proxy), trong khi flow accumulation thật đã có sẵn ở `calculate_native_hydrology(...)` (native_hydrology.py:361, output `accumulation_path`).
   → Sửa: thêm input tùy chọn `ACCUMULATION` vào algorithm; dock (đã chạy hydrology trước) truyền thẳng accumulation thật. Giữ fallback proxy cũ khi không có.
2. **Stale version trong JSON report** (`build_package.py:769`): `"version": "0.2.0"` — cứng, không khớp metadata.
   → Sửa: đọc version từ `metadata.txt` khi generate report.

## M0 — Smart Setup Assistant (đề xuất tham số + preview trực quan)

> Giải quyết vấn đề: "mật độ contour chưa đẹp, màu sắc chưa hợp tỉ lệ". Mục tiêu: khi chọn DEM xong, plugin **tự đề xuất** tham số hợp AOI/tỉ lệ, hiển thị **preview trực quan**, nhưng **user vẫn sửa được** mọi thứ.

### M0.1 — Đề xuất khoảng đồng mức theo tỉ lệ & địa hình (tái dùng code có sẵn)
- `math_utils.nice_interval(relief, desired_intervals)` **đã tồn tại** và `inspect_dem_layer()` (dem_info.py:70) **đã tính** `recommended = nice_interval(robust_max − robust_min)` — chỉ đang bị bỏ ở UI.
- Bổ sung hệ số tỉ lệ: ước lượng tỉ lệ bản đồ từ AOI:
  `scale = extent_width_m / (paper_width_m)` (A4 ngang ≈ 0.297 m).
  - AOI nhỏ (thị trấn, ~2 km) → 1:5k–1:10k → interval nhỏ (2–5 m)
  - AOI trung bình (huyện, ~20 km) → 1:50k–1:100k → 10–20 m
  - AOI lớn (tỉnh, ~100 km) → 1:300k+ → 25–50 m
- Công thức gợi ý cuối: `interval = nice_interval(relief, clamp(interval_count_target, 15, 30))` rồi **snap vào bảng chuẩn** `(1, 2, 2.5, 5, 10, 20, 25, 50, 100)` (hàm `snap_interval()` thêm vào math_utils).
- **UI (tab Contours)** — thêm 1 dòng, spin vẫn sửa tay được:
  ```
  Suggested interval (1:50k AOI, relief 540 m):   25 m   [Apply]
  ```
  Nút Apply điền vào spin `contour_interval`. Tự cập nhật khi đổi DEM hoặc bấm "Re-inspect".

### M0.2 — Preview màu palette (gradient thumbnail)
- Mỗi entry `TERRAIN_PALETTES` (presets.py, có sẵn `label` + `stops` %RGB) render thành **QPixmap 96×20** gradient tuyến tính bằng QPainter.
- Combo palette (tab Settings) → `addItem(QIcon(pixmap), label)`. Nhìn màu chọn ngay, không cần chạy thử.
- Code: `_palette_preview(stops, width=96, height=20)` đặt trong dock.py (hoặc `core/previews.py` mới nếu tái dùng ở nhiều nơi).

### M0.3 — Theme "Dark / Night" + swatch preview
- `CARTOGRAPHY_PRESETS` (presets.py) **thêm preset `night_dark`**:
  - `paper: #0e1116` (nền tối), `ink: #e6e1d8`, `muted_ink: #8a8a8a`
  - `contour_minor/index/master`: vàng nhạt `170,150,80,α` / `200,180,90,α` / `235,215,120,255`
  - `water: #4fc3f7` (cyan sáng), `ridge: 140,110,60,200`, `spot_elevation: #ffb74d`
  - `font: Noto Sans`, `orientation: landscape`, `legend_title: "MAP SYMBOLS"`
  - Palette liên kết: `terrain_dark` (thêm 1 bộ stops tối vào TERRAIN_PALETTES) hoặc dùng `grayscale`.
- **UI (tab Layout)**: combo cartography + **swatch preview** — QPixmap nhỏ 120×70 minh họa: nền paper, 2–3 đường contour giả theo màu preset, chữ mẫu tên phông. Cập nhật khi đổi preset.
- `styles.py` và `layouts.py` **đã đọc preset** (`preset["contour_label"]`, `preset["paper"]`, `preset["ink"]`...) → theme mới tự lan tới layer style + layout export, chỉ cần thêm entry.

### M0.4 — Layout export đẹp + đơn giản (giữ nguyên tinh thần hiện tại)
- Layout đã tự động chọn khổ giấy + orientation theo bbox (layouts.py:142 "dynamically select orientation and dimensions based on bounding box") và chọn interval cho grid (layouts.py:247 dùng nice_interval).
- M0 chỉ thêm: combo **khổ giấy** (A4/A3/A1 × portrait/landscape, override tự động) + nút "Create Layout" rõ ràng ở tab Layout — đầu ra = layout QGIS hoàn chỉnh, sẵn sàng Export PDF/PNG.
- Tóm tắt 1 dòng trong tab Layout: "Khổ A3 · 1:50,000 · theme USGS Classic — [Tạo layout]".

### M0 — File đụng tới
| File | Thay đổi |
|---|---|
| `core/math_utils.py` | thêm `snap_interval(value)` + `suggest_contour_interval(relief, extent_width_m, paper_width_m)` |
| `core/dem_info.py` | expose `recommended_interval` + `estimated_scale` trong dict trả về |
| `core/presets.py` | preset `night_dark` + palette `terrain_dark` |
| `dock.py` | dòng Suggested interval [Apply] (tab Contours); gradient thumbnail trong palette combo; swatch preview (tab Layout); combo khổ giấy + nút Create Layout |
| `core/layouts.py` | nhận `paper_size` + `orientation` override |

## M1 — Smoothing Contour & River (cartographic pass)

### Nguyên tắc
- Giữ nguyên bản **raw** (chính xác, dùng để tính toán — triết lý Zero Data Distortion đã có).
- Bản **cartographic** (`_smooth` suffix): chỉ để hiển thị bản đồ. Không đổi attribute, không đổi topology (chỉ làm mượt đỉnh trên polyline hiện có — Chaikin không tạo giao cắt, không gãy thứ tự).

### Thuật toán
- **Chaikin's Corner Cutting** tự viết (numpy, OGR), 1–4 iterations:
  - Với mỗi polyline `[P0..Pn]`: mỗi cặp `Pi, Pi+1` → 2 điểm mới `Q1 = 0.75*Pi + 0.25*Pi+1`, `Q2 = 0.25*Pi + 0.75*Pi+1`.
  - Lặp `iterations` lần. Chaikin nhanh, giữ dạng địa hình thực, không phụ thuộc provider.
- **Simplify trước, smooth sau** (tùy chọn): Douglas–Peucker trên DEM 30m thô giúp bỏ răng cưa pixel; dùng `QgsGeometry.simplify(tolerance)` qua child `native:simplifygeometries` — hoặc tự viết RDP numpy cho khỏi phụ thuộc.
- Làm việc trong **CRS đã chiếu** (working raster luôn UTM sau reproject) → mượt phẳng hợp lệ, không biến dạng.

### File đụng tới
| File | Thay đổi |
|---|---|
| `core/smoothing.py` (mới) | `smooth_chaikin(input_gpkg, output_gpkg, iterations)` + `simplify_dp(input, output, tolerance)` — đọc OGR, xử lý numpy, ghi OGR, giữ field ELEV/STRAHLER |
| `algorithms/build_package.py` | Sau `gdal:contour` và hydrology chain: nếu bật smoothing → tạo `{prefix}_contours_smooth.gpkg`; thêm param `SMOOTHING` (enum Off/Light/Medium/Heavy = 0/1/2/3 iterations) + `SIMPLIFY_TOLERANCE` (double, mặc định 0 = tắt) |
| `algorithms/build_hydrology.py` | Tương tự cho stream vector `{prefix}_rivers_smooth.gpkg` |
| `dock.py` | Tab **Contours**: combo "Smoothness Level" (Off/Light/Medium/Heavy) + spin "Simplify tolerance (m)". Tab **Hydrology**: cùng combo. |

### UI
```
Smoothness level:  [Off | Light | Medium | Heavy]
Simplify (m, 0=off): [  5.0 ]
```
Default: Off (không đổi hành vi cũ), Medium = 2 iterations Chaikin.

## M2 — Geomorphon + SPI/STI (thematic module mới)

### Geomorphon (Jasiewicz & Stepinski 2013)
- Phân loại 10 dạng địa hình: peak, ridge, shoulder, spur, slope, hollow, footslope, valley, pit, flat.
- Thuật toán (thuần numpy, theo pattern `_condition_dem`/`_write_raster` trong native_hydrology.py):
  1. Với mỗi ô, quét 8 hướng chính theo bán kính `R` ô (từ tham số `radius_m`, `R = radius_m / cell_size`).
  2. Trên mỗi hướng: so sánh độ dốc giữa ô trung tâm và các ô dọc tia → phân loại dốc lên / dốc xuống / phẳng / yên ngựa (flat vs saddle theo tolerance `t`).
  3. Chuỗi 8 ký hiệu → tra bảng 10 form (lookup table chuẩn của paper, hardcode constant).
- Output: raster `GDT_Byte` 1–10 + bảng style 10 màu (thêm vào `styles.py` + palette).
- Params: `GEOMORPHON_RADIUS_M` (double, default 100), `GEOMORPHON_TOLERANCE` (double, default 1% relief).

### SPI & STI
- **SPI** = `ln(As × tan(slope_rad))`, As = specific catchment area (`acc × cell_size` — công thức đã có sẵn ở `thematic_terrain.py:127`).
- **STI** = `(As/22.13)^0.6 × (sin(slope)/0.0896)^1.3`.
- Dùng **accumulation thật** từ hydrology (giống fix ở mục 0), fallback proxy khi chưa chạy hydrology.
- Output: 2 raster Float32 + style ramp (thêm vào `styles.py`).

### File đụng tới
| File | Thay đổi |
|---|---|
| `core/geomorphon.py` (mới) | `classify_geomorphon(dem_path, output_path, radius_m, tolerance)` + `_GEOMORPHON_TABLE` + label dict |
| `core/thematic_terrain.py` | Thêm `calculate_spi(accumulation_path, slope_path, output_path)` và `calculate_sti(...)` |
| `algorithms/build_package.py` | 3 product mới trong `products` tuple (default: Geomorphon=True, SPI/STI=True), param `ACCUMULATION` (input raster optional), run blocks theo pattern `run_product`/direct call |
| `styles.py` | `apply_geomorphon_style(layer)`, `apply_spi_style(layer)`, `apply_sti_style(layer)` |
| `dock.py` | 3 checkbox mới trong Products grid + note "cần Hydrology chạy trước để có SPI/STI chính xác" |
| `core/intelligence_report.py` | Thêm section: % diện tích theo 10 dạng địa hình + SPI max/mean |

### Styling
- Geomorphon: 10 màu bảng chuẩn (red=peak, green=valley...), dạng categorical.
- SPI/STI: ramp `#2c7bb6 → #ffffbf → #d7191c` (blue→red, log scale).

## M3 — Multi-hazard Composite + GeoPackage Bundle

### Multi-hazard Composite Index
- Đầu vào có sẵn: `landslide_hazard` (1–4), `TWI` (chuẩn hóa 0–1), `slope` (chuẩn hóa 0–1).
- Công thức có trọng số (default, UI cho đổi): `score = 0.5×landslide_norm + 0.3×twi_norm + 0.2×slope_norm`.
- Ngưỡng: <0.33 Low, 0.33–0.66 Moderate, >0.66 High → raster `GDT_Byte` 1–3 + style 3 màu.
- File: `thematic_terrain.py` thêm `calculate_multihazard(landslide_path, twi_path, slope_path, output_path, weights=None)`; `build_package.py` product `CREATE_MULTIHAZARD` (default True, cần inputs Landslide + TWI + Slope); UI 3 spin trọng số trong tab Hydrology hoặc Settings.

### GeoPackage Bundle
- Gom toàn bộ output đã chọn vào **1 file** `{prefix}_bundle.gpkg`:
  - Raster: `gdal_translate -of GPKG` (GDAL hỗ trợ nhúng raster tile vào GPKG) — giữ compression.
  - Vector (contours, spot, rivers): OGR CopyLayer vào cùng GPKG.
- File: `core/bundle.py` (mới): `create_bundle(output_paths: dict, bundle_path, feedback)` — duyệt outputs, skip html/json, ghi log từng layer.
- UI: checkbox "Export all products to a single GeoPackage bundle" (tab Settings, default True).

## M4 — STL/OBJ Export + Presets + Run History

### STL/OBJ (in 3D vật lý)
- `core/export_3d.py` (mới): `export_stl(dem_path, output_path, z_scale=1.0, base_thickness_m=0.0)`:
  - Đọc DEM (pattern `_resample_band` trong web_3d_viewer.py:8 đã có sẵn), giới hạn kích thước mesh (max ~1024², downsample nếu lớn hơn — cấu hình đã có pattern).
  - Binary STL: 2 triangle/ô, tọa độ thực (m), ghi nhị phân — ~80 dòng, không phụ thuộc thư viện.
  - `export_obj(...)` tương tự, thêm MTL trắng/xám.
- UI: nút trong tab Settings — "Export 3D print model (STL)" + spin z_scale + nút OBJ.
- Wow factor: ít plugin QGIS nào có.

### Preset theo ngành
- `core/presets.py` (đã có `TERRAIN_PALETTES`) thêm `INDUSTRY_PRESETS`:
  - **Đô thị**: suitability, contours, color relief, slope, landslide → tick sẵn.
  - **Nông nghiệp**: slope, TWI, SPI, STI, color relief.
  - **Phòng chống thiên tai**: landslide, TWI, multi-hazard, hydrology, 3D viewer.
  - **Khai khoáng / cơ sở hạ tầng**: slope, aspect, hillshade, contours, spot elevations.
- UI: combo "Ngành" đầu tab Products → tự tick/uncheck; user vẫn chỉnh tay sau.

### Run History
- Đã có JSON report (`{prefix}_report.json`) → chỉ cần lưu danh sách chạy:
  - `core/history.py` (mới): `append_history(entry)`, `load_history()` — file `~/.local/share/QGIS/QGIS3/profiles/default/terrain_product_studio_history.json` (dùng `QgsApplication.qgisSettingsDirPath()`).
  - UI: tab **Inspect** thêm QListWidget "Recent runs" — click → mở thư mục output + JSON report.
- Tránh chạy lại từ đầu khi output folder còn giữ các file cũ (có thể nhận diện qua `unique_path` naming).

## 2.0.0 — Thứ tự triển khai & ước lượng

| Milestone | Nội dung | Ước lượng |
|---|---|---|
| M0 | **Smart Setup Assistant**: gợi ý interval theo AOI/tỉ lệ + [Apply], preview gradient palette, theme Dark/Night + swatch preview, khổ giấy + nút Create Layout | ~1 ngày |
| M1 | Smoothing contour + river, fix report version | ~1 ngày |
| M2 | Geomorphon + SPI/STI, fix landslide accumulation, styles, report section | ~1.5 ngày |
| M3 | Multi-hazard + gpkg bundle | ~1 ngày |
| M4 | STL/OBJ + presets + history | ~1 ngày |

- **M0 là bản vá thẩm mỹ nhanh nhất** — nên làm đầu vì giải quyết đúng than phiền hiện tại (contour dày/màu chưa hợp) mà không đụng pipeline tính toán.
- Release 2.0.0 sau M0+M1 (đã đủ đẹp + mượt). M2–M4 theo sau trong 2.0.x hoặc 2.1.0.
- Version trong `metadata.txt` → 2.0.0, cập nhật CHANGELOG + README, build zip qua `scripts/package_plugin.py`.
- Tất cả code mới phải pass: bandit + pyflakes + unittest + smoke test + render check (chuẩn scan QGIS repo đã thiết lập).

## Ngoài scope 2.0.0 (để dành 2.1/2.2)
MFD flow routing, flood simulation, MCDA site suitability, QgsLayoutAtlas đa trang, batch queue, DXF export, solar radiation 2D (shadow engine hiện ở JS — cần viết lại numpy), basin morphometry (cần watershed polygon — `basin_path` đã có output trong native_hydrology, nên thực ra **có thể làm sớm hơn dự kiến**), multi-temporal difference.
