# 🏔️ Hướng Dẫn & Tài Liệu Kỹ Thuật: Terrain Product Studio

[![QGIS 3 & 4 Compatible](https://img.shields.io/badge/QGIS-3.28%2B%20%7C%204.x%20(Qt6)-brightgreen.svg)](https://qgis.org)
[![Tác giả](https://img.shields.io/badge/T%C3%A1c%20gi%E1%BA%A3-Nguy%E1%BB%85n%20V%C4%83n%20T%C3%ADn-blueviolet.svg)](https://github.com/hulauwa)
[![License: GPL v2+](https://img.shields.io/badge/License-GPL%20v2%2B-orange.svg)](https://www.gnu.org/licenses/gpl-2.0.html)

> **Giải pháp tự động hóa toàn diện trong QGIS: Chuyển đổi mô hình số độ cao (DEM) thành bộ sản phẩm bản đồ địa hình chuẩn xuất bản, mạng lưới thủy văn phân cấp, bản đồ đánh giá rủi ro địa kỹ thuật, không gian 3D WebGIS tương tác và báo cáo phân tích thông minh chỉ với 1 cú nhấp chuột.**

[🌐 Read Documentation in English (README.md)](README.md)

---

## 📑 Mục Lục
- [🌟 Điểm Nổi Bật](#-điểm-nổi-bật)
- [📦 Danh Mục & Ý Nghĩa Khoa Học Các Sản Phẩm](#-danh-mục--ý-nghĩa-khoa-học-các-sản-phẩm)
  - [1. Các Dẫn Xuất Địa Mạo Định Lượng](#1-các-dẫn-xuất-địa-mạo-định-lượng)
  - [2. Mạng Lưới Thủy Văn & Dòng Chảy Strahler](#2-mạng-lưới-thủy-văn--dòng-chảy-strahler)
  - [3. Đánh Giá Địa Kỹ Thuật & Môi Trường](#3-đánh-giá-địa-kỹ-thuật--môi-trường)
  - [4. Bản Đồ Địa Hình Chuẩn Xuất Bản (Cartography)](#4-bản-đồ-địa-hình-chuẩn-xuất-bản-cartography)
  - [5. 3D WebGIS Interactive Studio (Bản Đồ 3D Web Tương Tác)](#5-3d-webgis-interactive-studio-bản-đồ-3d-web-tương-tác)
  - [6. Báo Cáo Phân Tích Thông Minh (Topographic Intelligence Dashboard)](#6-báo-cáo-phân-tích-thông-minh-topographic-intelligence-dashboard)
- [🎯 Đề Xuất Theo Tỷ Lệ & Chọn Phạm Vi Xử Lý](#-đề-xuất-theo-tỷ-lệ--chọn-phạm-vi-xử-lý)
- [🚀 Hướng Dẫn Cài Đặt](#-hướng-dẫn-cài-đặt)
- [📖 Hướng Dẫn Sử Dụng Chi Tiết](#-hướng-dẫn-sử-dụng-chi-tiết)
- [🛠️ Cấu Trúc Mã Nguồn & Tính Tương Thích](#️-cấu-trúc-mã-nguồn--tính-tương-thích)
- [📜 Bản Quyền & Liên Hệ](#-bản-quyền--liên-hệ)

---

## 🌟 Điểm Nổi Bật

- **Bảo toàn dữ liệu gốc (Zero Data Distortion)**: Các lớp raster phân tích (Slope, Aspect, TRI, TWI...) lưu giữ nguyên vẹn giá trị vật lý thực tế (độ, radian, mét, chỉ số), phục vụ tính toán không gian chính xác.
- **Trợ lý thiết lập thông minh (Smart Setup)**: Tự đề xuất khoảng cao đều theo tỷ lệ bản đồ và mức chênh cao (snap vào bảng chuẩn `1/2/2.5/5/10/20/25/50/100`), preview gradient màu trực tiếp trên combo, theme **Dark / Night** kèm swatch xem trước.
- **Mạng sông suối đa điểm liên tục (Continuous Polyline)**: Thuật toán dò tuyến thủy văn D8 nối liền các pixel thành các đường sông suối mượt mà với bảng thuộc tính phong phú (`ORDER`, `LENGTH_M`, `AREA_HA`) — hỗ trợ làm trơn Chaikin / đơn giản hóa Douglas–Peucker.
- **Chỉ số đa hiểm họa & Gói GeoPackage**: Chỉ số tổng hợp có trọng số (sạt lở × độ dốc × TWI) và gộp **toàn bộ sản phẩm raster + vector vào một file `.gpkg` duy nhất** để chia sẻ (raster byte nén PNG không mất dữ liệu, raster float theo chuẩn OGC 2D-gridded-coverage).
- **In 3D & Tự động hóa quy trình**: Xuất mesh STL/OBJ (tự giảm độ phân giải, phóng đại độ cao, đế đặc kín nước), preset theo ngành (Đô thị / Nông nghiệp / Thiên tai / Khai khoáng) một chạm, và nhật ký lịch sử 20 lần chạy gần nhất.
- **3D WebGIS Studio độc lập (`.html`)**: Trực quan hóa địa hình 3D mượt mà trên trình duyệt, tích hợp mô phỏng ngập lụt, cắt mặt cắt A $\rightarrow$ B trực tiếp, đổ bóng mặt trời theo giờ thực và trợ lý AI trả lời câu hỏi địa hình.
- **Báo cáo Topographic Intelligence Report (`.html`)**: Dashboard tổng hợp với biểu đồ hoa hướng dốc (Aspect Rose), biểu đồ tần suất cao độ và ma trận đánh giá đất xây dựng theo TCVN.
- **Tương thích kép QGIS 3 (Qt5) & QGIS 4 (Qt6)**: Đã xử lý toàn bộ scoped enums và tương thích hoàn toàn trên môi trường macOS, Windows, Linux.

---

## 📦 Danh Mục & Ý Nghĩa Khoa Học Các Sản Phẩm

### 1. Các Dẫn Xuất Địa Mạo Định Lượng

| Tên Dẫn Xuất | Phương Pháp / Công Thức | Ý Nghĩa Kỹ Thuật & Ứng Dụng |
| :--- | :--- | :--- |
| **Độ dốc (Slope)** | Horn (1981) / Zevenbergen & Thorne (1987) | Góc nghiêng sườn dốc (độ/radian). Ứng dụng trong phân tích ổn định mái dốc, thiết kế tuyến giao thông, tính khối lượng đào đắp. |
| **Hướng dốc (Aspect)** | Góc phương vị $0^\circ - 360^\circ$ | Hướng phơi của sườn núi. Ứng dụng trong nghiên cứu bức xạ mặt trời, vi khí hậu, quy hoạch vườn cây/nông nghiệp, hướng đón gió bão. |
| **Chỉ số gồ ghề (TRI)** | Riley et al. (1999) $\sqrt{\sum (z_{ij} - z_{00})^2}$ | Định lượng độ mấp mô bề mặt địa hình. Phục vụ đánh giá tính cơ động, khả năng tiếp cận và sinh thái cảnh quan. |
| **Vị trí địa hình (TPI)** | Guisan et al. (1999) $z_0 - \bar{z}$ | So sánh cao độ điểm trung tâm với lân cận. Tự động nhận diện đỉnh núi, sống núi, sườn dốc, đồng bằng và đáy thung lũng. |
| **Độ nhám (Roughness)** | $\max(z_{ij}) - \min(z_{ij})$ | Chênh lệch cao độ cực đại trong cửa sổ $3\times3$ pixel. |
| **Độ cong (Curvatures)** | Profile & Planform Curvature | Độ cong dọc sườn dốc (gia tốc dòng chảy) và độ cong ngang (tụ thủy hoặc phân tán dòng chảy). |
| **Geomorphon** | Jasiewicz & Stepinski (2013) | Phân loại 10 dạng địa hình (bằng, đỉnh, sườn, thung lũng, hố trũng...) bằng so sánh góc tầm nhìn. |
| **SPI** | Moore et al. (1991) $A_s \tan \beta$ | Chỉ số năng lượng dòng chảy (Stream Power Index) — sức xói mòn của dòng tập trung. |
| **STI** | Sediment Transport Index | Chỉ số vận chuyển trầm tích tương đối — xác định vùng xói mòn trọng điểm cho quy hoạch bảo vệ đất. |

---

### 2. Mạng Lưới Thủy Văn & Dòng Chảy Strahler

- **Hướng dòng chảy D8 (Flow Direction) & Tích lũy dòng chảy (Flow Accumulation)**: Xác định hướng dồn nước của từng pixel và tính tổng diện tích lưu vực thượng nguồn ($ha, km^2$).
- **Mạng sông suối phân cấp Strahler (Continuous Vector)**:
  - *Cấp 1 (Suối nguồn - Headwater)*: Đường nét mảnh $0.28\text{ mm}$, xanh lam nhạt `#6baed6`.
  - *Cấp 2 (Suối phụ - Tributary)*: Nét vừa $0.52\text{ mm}$, xanh lam trung `#3182bd`.
  - *Cấp 3 (Nhánh sông - Sub-River)*: Nét đậm $0.85\text{ mm}$, xanh dương `#08519c`.
  - *Cấp 4+ (Dòng chính - Major River)*: Nét lớn $1.30\text{ mm}$, xanh thẫm `#08306b`.
- **Ranh giới tiểu lưu vực (Watershed Basins)**: Phân vùng lưu vực tự động dạng polygon kèm bảng màu phân biệt.
- **Chỉ số ẩm ướt địa hình (TWI - Topographic Wetness Index)**:
  $$\text{TWI} = \ln\left(\frac{A}{\tan \beta}\right)$$
  Chỉ số phản ánh mức độ ẩm ướt và tích tụ nước ngầm, xác định vùng đất ngập nước hoặc nguy cơ đọng nước.

---

### 3. Đánh Giá Địa Kỹ Thuật & Môi Trường

- **Thích hợp đất xây dựng theo độ dốc (TCVN 4447:2012 / Quy hoạch xây dựng)**:
  - *Cấp 1 ($< 3^\circ$)*: Rất thuận lợi xây dựng công trình, chi phí san nền thấp (`#2ca25f`).
  - *Cấp 2 ($3^\circ - 8^\circ$)*: Thuận lợi xây dựng (`#99d8c9`).
  - *Cấp 3 ($8^\circ - 15^\circ$)*: Hạn chế, cần san gạt và kè chắn nền (`#fed976`).
  - *Cấp 4 ($15^\circ - 25^\circ$)*: Khó khăn, hạn chế xây dựng kiên cố (`#fd8d3c`).
  - *Cấp 5 ($> 25^\circ$)*: Cấm xây dựng công trình kiên cố, vùng bảo tồn rừng/sinh thái (`#e31a1c`).
- **Nguy cơ sạt lở đất & Hệ số chiều dài sườn dốc RUSLE (LS-factor)**:
  - Kết hợp độ dốc và chiều dài sườn dốc để phân 4 cấp cảnh báo nguy cơ sạt trượt và xói mòn đất (sử dụng lưới tích lũy dòng chảy thực tế).
- **Chỉ số đa hiểm họa tổng hợp (Multi-Hazard Composite)**:
  - Tổ hợp có trọng số: sạt lở × độ dốc × TWI (người dùng chỉnh được trọng số) thành một raster rủi ro tổng hợp phân 4 cấp độ.
- **Gói GeoPackage (Bundle)**:
  - Gộp mọi sản phẩm raster và vector vào **một file `.gpkg`** sẵn sàng chia sẻ (raster byte nén PNG lossless, raster float theo chuẩn OGC 2D-gridded-coverage).

---

### 4. Bản Đồ Địa Hình Chuẩn Xuất Bản (Cartography)

- **Hệ thống đường đồng mức 3 cấp chuẩn USGS**:
  - *Đường đồng mức phụ (Minor)*: $0.18\text{ mm}$, nét mảnh thể hiện chi tiết vi địa hình.
  - *Đường đồng mức chính (Index)*: $0.42\text{ mm}$, nét đậm, kèm nhãn số độ cao dọc đường mức (mỗi 5 đường).
  - *Đường đồng mức cái (Master)*: $0.65\text{ mm}$, phân ranh giới các khoảng cao đều lớn.
- **Điểm độ cao đỉnh núi (Spot Elevation Peaks)**: Lọc tự động các đỉnh núi nổi bật theo độ nhô địa hình (prominence) và khoảng cách yên ngựa (col separation).
- **Phân tầng màu cao độ (Color Relief) & Bóng đổ đa hướng (Multi-directional Hillshade)**: Kết hợp 4 hướng chiếu sáng ($225^\circ, 270^\circ, 315^\circ, 360^\circ$) giúp địa hình nổi khối 3D rõ nét, không bị khuất bóng.
- **Làm trơn bản đồ (Cartographic Smoothing)**: Chaikin (bo góc mềm) và Douglas–Peucker (đơn giản hóa) áp dụng cho cả đường đồng mức lẫn mạng sông — chọn ngay trên tab Products.

---

### 5. 3D WebGIS Interactive Studio (Bản Đồ 3D Web Tương Tác)

Xuất ra file HTML duy nhất (`<prefix>_interactive_3d_terrain.html`), mở trực tiếp trên mọi trình duyệt:

1. **🎨 Base Texture Draping**: Chuyển đổi lớp phủ bề mặt 3D tức thì giữa: Cao độ Hypsometric, Độ dốc, Chỉ số TWI, Đất xây dựng TCVN, Nguy cơ sạt lở và Bóng đổ đơn sắc.
2. **🌊 Mô phỏng ngập lụt real-time (Flood Simulation)**: Kéo thanh trượt mực nước dâng $\rightarrow$ bề mặt nước 3D dâng theo cao trình thực và tự động tính diện tích ngập ($ha, km^2$, % diện tích).
3. **✂️ Cắt mặt cắt địa hình A $\rightarrow$ B (Cross-Section Profile)**: Click 2 điểm trên bề mặt 3D $\rightarrow$ chiếu tia laser đỏ và vẽ ngay biểu đồ mặt cắt 2D vector SVG (chiều dài, chênh cao, độ dốc trung bình).
4. **☀️ Mô phỏng đổ bóng mặt trời theo giờ (Solar Shadow SPA)**: Thanh trượt từ 05:30 đến 18:30 tính toán vị trí mặt trời thực tế theo tọa độ và nút chạy **Time-Lapse Bình Minh $\rightarrow$ Hoàng Hôn**.
5. **🤖 Trợ lý trí tuệ địa hình AI (Terrain Q&A)**: Cửa sổ hỏi đáp thông minh phân tích nhanh đỉnh cao nhất, vùng sạt lở nguy hiểm và phân bố đất xây dựng.
6. **🚁 Chế độ bay Drone/Flycam**: Camera tự động lướt trên không gian 3D khảo sát địa hình.
7. **🔍 Thám sát bề mặt (Live Inspector)**: Rê chuột để xem tức thời: Cao độ $Z$, Độ dốc (°), TWI, Cấp xây dựng và Nguy cơ trượt lở.

---

### 6. Báo Cáo Phân Tích Thông Minh (Topographic Intelligence Dashboard)

Xuất ra file HTML tổng hợp (`<prefix>_topographic_intelligence_report.html`):
- **🧭 Hoa hướng dốc (Aspect Rose)**: Biểu đồ radar SVG phân bố diện tích sườn núi theo 8 hướng địa lý.
- **📈 Phân bố cao độ (Hypsometric Distribution)**: Biểu đồ tần suất diện tích qua 10 phân dải cao độ.
- **🌊 Cơ cấu mạng sông suối**: Thống kê chiều dài ($km$) và tỷ trọng suối cấp 1, 2, 3 và dòng chính cấp 4+.
- **🏛️ & ⚠️ Bảng ma trận chuyên đề**: Thống kê diện tích ($ha$) và tỷ lệ (%) theo cấp đất xây dựng và nguy cơ sạt lở.
- **🖨️ Nút in ấn / Xuất PDF**: Chuẩn hóa CSS phục vụ in báo cáo kỹ thuật.

---

### 7. In 3D & Tự Động Hóa Quy Trình

- **Xuất mesh STL / OBJ**: File STL nhị phân hoặc OBJ+MTL của bề mặt địa hình, sẵn sàng đưa vào máy in 3D — tự giảm độ phân giải khi quá $1024^2$ ô, hệ số phóng đại độ cao (z-exaggeration), và tùy chọn **đế đặc** làm mesh kín nước (watertight) để in thực tế.
- **Preset theo ngành**: Một chạm tick đúng bộ sản phẩm — *Đô thị / xây dựng*, *Nông nghiệp*, *Phòng chống thiên tai*, *Khai khoáng / cơ sở hạ tầng* — hoặc giữ *Chọn theo nhu cầu* (Custom selection).
- **Lịch sử chạy (Run History)**: 20 lần chạy gần nhất được lưu trong profile QGIS; mở lại thư mục kết quả và báo cáo ngay từ tab Inspect.

---

## 🎯 Đề Xuất Theo Tỷ Lệ & Chọn Phạm Vi Xử Lý

1. **Phạm vi xử lý (Processing Extent)**:
   - `Full DEM Layer Extent`: Xử lý toàn bộ diện tích của file DEM đầu vào.
   - `Current Map Canvas Extent`: Cắt và xử lý theo khung nhìn bản đồ đang hiển thị trên QGIS.
   - `Calculate from Another Layer Extent`: Cắt theo ranh giới hành chính hoặc ranh giới dự án từ một lớp vector/raster khác.
2. **Đề xuất thông minh theo tỷ lệ bản đồ**:
   - Tự động nhận diện độ phân giải pixel $\rightarrow$ gợi ý tỷ lệ bản đồ phù hợp ($1:5,000$ đến $1:250,000$), khoảng cao đều đường đồng mức tối ưu ($2.5\text{ m}, 5\text{ m}, 10\text{ m}, 20\text{ m}$) và mật độ điểm độ cao đỉnh núi.

---

## 🚀 Hướng Dẫn Cài Đặt

### Cách 1: Cài đặt qua file ZIP (Khuyến nghị)
1. Tải file `terrain_product_studio-2.0.0.zip` tại mục [Releases](https://github.com/hulauwa/terrain-product-studio/releases).
2. Trong QGIS, vào menu **Plugins (Tiện ích)** $\rightarrow$ **Manage and Install Plugins... (Quản lý và Cài đặt Tiện ích...)**.
3. Chọn tab **Install from ZIP (Cài đặt từ ZIP)** $\rightarrow$ Chọn file `.zip` vừa tải $\rightarrow$ Nhấn **Install Plugin**.

> **v2.0.0**: bản phát hành chuẩn xuất bản — trợ lý thiết lập thông minh (đề xuất khoảng cao đều, preview màu, theme Dark/Night), làm trơn Chaikin/Douglas–Peucker cho đồng mức & sông, sản phẩm geomorphon/SPI/STI, chỉ số đa hiểm họa có trọng số, gói GeoPackage duy nhất, xuất STL/OBJ in 3D, preset theo ngành và lịch sử chạy. (bản 1.2.0 trước đó đã sửa toàn bộ lỗi từ quét bảo mật QGIS Plugin Repository.)

### Cách 2: Sao chép thủ công vào thư mục Plugins của QGIS
Sao chép thư mục `terrain_product_studio` vào đường dẫn tương ứng với hệ điều hành:
- **macOS**: `~/Library/Application Support/QGIS/QGIS4/profiles/default/python/plugins/`
- **Windows**: `%APPDATA%\QGIS\QGIS3\profiles\default\python\plugins\`
- **Linux**: `~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/`

---

## 📖 Hướng Dẫn Sử Dụng Chi Tiết

1. Mở plugin từ menu **Raster** $\rightarrow$ **Terrain Product Studio** $\rightarrow$ **Terrain Product Studio Panel** (hoặc click icon trên thanh công cụ).
2. **1 · Input Data**: Chọn lớp DEM và band độ cao. Nhấn **Inspect DEM** để xem thông số độ phân giải và đề xuất tỷ lệ/khoảng cao đều.
3. **2 · Processing Extent**: Chọn phạm vi xử lý (*Toàn bộ DEM*, *Khung nhìn hiện tại*, hoặc *Theo lớp ranh giới*).
4. **3 · Output**: Chọn thư mục lưu kết quả (mặc định lưu tại thư mục `temp/` nội bộ của plugin) và tiền tố đặt tên file (`prefix`).
5. **Cấu hình các tab**:
   - Tab **Products**: Chọn **preset theo ngành** (Đô thị / Nông nghiệp / Thiên tai / Khai khoáng) hoặc tự tick sản phẩm; cài làm trơn và trọng số chỉ số đa hiểm họa.
   - Tab **Contours**: Tinh chỉnh khoảng cao đều và bội số đường đồng mức cái.
   - Tab **Hydrology**: Bật trích xuất thủy văn và ngưỡng diện tích tụ thủy sinh dòng ($ha$).
   - Tab **Layout**: Cấu hình tự động tạo bản in trang in chuẩn xuất bản và xuất file PDF/PNG.
   - Tab **Settings**: Phóng đại độ cao và độ dày đế cho **xuất STL/OBJ in 3D**.
   - Tab **Inspect**: Mở lại thư mục kết quả / báo cáo của bất kỳ lần chạy nào trong 20 lần gần nhất.
6. Nhấn **Build Product Package** để bắt đầu xử lý.
7. Khi hoàn thành, các lớp dữ liệu sẽ tự động nạp vào QGIS. Bạn có thể nhấn ngay nút **🌐 View 3D Web Map** hoặc **📊 View Report** để khám phá sản phẩm 3D và báo cáo trên trình duyệt.

---

## 🛠️ Cấu Trúc Mã Nguồn & Tính Tương Thích

```
terrain_product_studio/
├── algorithms/
│   ├── build_package.py       # Thuật toán Processing chính: gói sản phẩm đầy đủ
│   ├── build_hydrology.py     # Thuật toán Processing trích xuất thủy văn & lưu vực
│   └── inspect_dem.py         # Thuật toán kiểm tra DEM
├── core/
│   ├── bundle.py              # Gộp toàn bộ raster + vector vào một GeoPackage
│   ├── dem_info.py            # Kiểm tra DEM & đề xuất thông minh theo tỷ lệ
│   ├── export_3d.py           # Xuất mesh STL nhị phân / OBJ (kín nước)
│   ├── geomorphon.py          # Phân loại địa hình Jasiewicz & Stepinski
│   ├── history.py             # Nhật ký lịch sử chạy (20 lần gần nhất)
│   ├── intelligence_report.py # Trình tạo Báo cáo Phân tích Thông minh (HTML)
│   ├── layers.py              # Xếp lớp & nhóm lớp trong QGIS
│   ├── layouts.py             # Trình tạo bản in (khổ giấy, theme)
│   ├── math_utils.py          # nice_interval, snap khoảng cao đều, vệ sinh prefix
│   ├── native_hydrology.py    # Dò tuyến D8 & nối polyline sông suối Strahler
│   ├── presets.py             # Palette địa hình, theme cartography, preset ngành
│   ├── qgis_compat.py         # Lớp tương thích kép Qt5/Qt6 & QGIS 3/4
│   ├── smoothing.py           # Làm trơn Chaikin & đơn giản hóa Douglas–Peucker
│   ├── spot_elevations.py     # Nhận diện đỉnh núi & lọc độ nổi địa hình
│   ├── styles.py              # Bộ phong cách hiển thị & nhãn bản đồ tự động
│   ├── thematic_terrain.py    # TCVN, sạt lở, đa hiểm họa, SPI/STI
│   └── web_3d_viewer.py       # Trình tạo 3D WebGIS Studio tương tác (WebGL)
├── dock.py                    # Giao diện điều khiển Dock widget
└── plugin.py                  # Điểm khởi động và đăng ký plugin trong QGIS
```

---

## 📜 Bản Quyền & Liên Hệ

Phát triển bởi **Nguyễn Văn Tín** ([@hulauwa](https://github.com/hulauwa)).

Phát hành theo giấy phép **GNU General Public License v2.0 or later (GPLv2+)**.
Mọi ý kiến đóng góp, báo lỗi hoặc đề xuất tính năng mới xin vui lòng tạo [Issue trên GitHub](https://github.com/hulauwa/terrain-product-studio/issues).
