"""Headless verification for the 2.1 feature batch (palettes, peaks, defaults)."""

import sys

from qgis.core import QgsApplication, QgsProcessingAlgorithm
from qgis.PyQt.QtWidgets import QApplication

from terrain_product_studio.algorithms.build_package import BuildTerrainPackageAlgorithm
from terrain_product_studio.core.presets import (
    PALETTE_ORDER,
    TERRAIN_PALETTES,
    resolve_palette_stops,
    is_dark_palette,
)

failures = []


def check(name, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    print(f"{status} {name}" + (f" — {detail}" if detail and not condition else ""))
    if not condition:
        failures.append(name)


# ── 1. Palette registry ───────────────────────────────────────────────────
check("PALETTE_ORDER has 20 entries", len(PALETTE_ORDER) == 20, str(len(PALETTE_ORDER)))
check("every ordered key exists in TERRAIN_PALETTES", all(k in TERRAIN_PALETTES for k in PALETTE_ORDER))
dark_keys = [k for k in PALETTE_ORDER if TERRAIN_PALETTES[k].get("dark")]
check("6 dark ramps", len(dark_keys) == 6, str(dark_keys))
groups = {TERRAIN_PALETTES[k]["group"] for k in PALETTE_ORDER}
check("groups cover classic/artistic/environment/scientific/dark", groups == {"classic", "artistic", "environment", "scientific", "dark"}, str(groups))

# Midnight Terrain uses elevation-anchored stops
midnight = TERRAIN_PALETTES["terrain_dark"]
check("Midnight Terrain has elev_stops", "elev_stops" in midnight)
check("Midnight first stop == #081318", midnight["elev_stops"][0][1:] == (8, 19, 24), str(midnight["elev_stops"][0]))
check("Midnight last stop == #D8CDBB", midnight["elev_stops"][-1][1:] == (216, 205, 187), str(midnight["elev_stops"][-1]))

# ── 2. resolve_palette_stops ──────────────────────────────────────────────
rel = resolve_palette_stops(TERRAIN_PALETTES["natural"], 100.0, 2000.0)
check("relative palette stretches over range", abs(rel[0][0] - 100.0) < 1e-6 and abs(rel[-1][0] - 2000.0) < 1e-6, str(rel[0]))
elev = resolve_palette_stops(midnight, 0.0, 100.0)  # display range must NOT be used
check("elev_stops used verbatim", [s[0] for s in elev] == [0.0, 250.0, 500.0, 1000.0, 2000.0, 3500.0, 5000.0], str([s[0] for s in elev]))

# ── 3. Algorithm enum alignment ───────────────────────────────────────────
algo = BuildTerrainPackageAlgorithm()
algo.initAlgorithm()
palette_param = next(p for p in algo.parameterDefinitions() if p.name() == "PALETTE")
options = palette_param.options()
check("PALETTE enum matches PALETTE_ORDER exactly", options == [TERRAIN_PALETTES[k]["label"] for k in PALETTE_ORDER], str(options[:3]))
default_index = palette_param.defaultValue()
check("PALETTE default is Natural Earth", options[default_index] == "Natural Earth", options[default_index])
spot_param = next(p for p in algo.parameterDefinitions() if p.name() == "SPOT_PCT")
check("SPOT_PCT default 80", spot_param.defaultValue() == 80, str(spot_param.defaultValue()))
check("SPOT_PCT min 0 max 100", spot_param.minimum() == 0 and spot_param.maximum() == 100)
smoothing_param = next(p for p in algo.parameterDefinitions() if p.name() == "SMOOTHING")
check("SMOOTHING default is Medium", smoothing_param.defaultValue() == 2, str(smoothing_param.defaultValue()))

# ── 4. Dock semantics (needs QApplication) ────────────────────────────────
app = QgsApplication([], False)
app.initQgis()
from terrain_product_studio.dock import TerrainStudioDock


class FakeIface:
    def mapCanvas(self):
        return None

    def openLayoutDesigner(self, layout):
        pass


dock = TerrainStudioDock(FakeIface())
dock.show()
app.processEvents()

check("design default = Standard Topographic", dock.design_preset_combo.currentData() == "standard_topo", str(dock.design_preset_combo.currentData()))
check("advanced design overrides collapsed", not dock.advanced_design_group.isChecked())
check("advanced design body hidden", not dock.advanced_design_body.isVisible())
check("six curated design presets plus Custom", dock.design_preset_combo.count() == 7, str(dock.design_preset_combo.count()))
arctic_index = dock.design_preset_combo.findData("arctic_survey")
dock.design_preset_combo.setCurrentIndex(arctic_index)
app.processEvents()
check("design preset applies map style", dock.cartography_combo.currentData() == "modern_atlas", str(dock.cartography_combo.currentData()))
check("design preset applies layout", dock.layout_template_combo.currentData() == "modern_atlas", str(dock.layout_template_combo.currentData()))
check("design preset applies DEM palette", dock.palette_combo.currentData() == "arctic", str(dock.palette_combo.currentData()))
check("design preset applies WGS84 grid", dock.grid_mode_combo.currentData() == "wgs84", str(dock.grid_mode_combo.currentData()))
dock.palette_combo.setCurrentIndex(dock.palette_combo.findData("natural"))
app.processEvents()
check("manual override marks design Custom", dock.design_preset_combo.currentData() == "", str(dock.design_preset_combo.currentData()))
dock.design_preset_combo.setCurrentIndex(
    dock.design_preset_combo.findData("standard_topo")
)
app.processEvents()

check("cartography default = Natural Earth Light", dock.cartography_combo.currentData() == "natural_earth", str(dock.cartography_combo.currentData()))
check("palette default = natural", dock.palette_combo.currentData() == "natural", str(dock.palette_combo.currentData()))
check("combo count = 20 + 4 separators", dock.palette_combo.count() == 24, str(dock.palette_combo.count()))

# index mapping: select each palette by data, verify algorithm index
for alg_index, key in enumerate(PALETTE_ORDER):
    combo_index = dock.palette_combo.findData(key)
    dock.palette_combo.setCurrentIndex(combo_index)
    app.processEvents()
    if dock._palette_algorithm_index() != alg_index:
        check(f"index map {key}", False, f"expected {alg_index} got {dock._palette_algorithm_index()}")
        break
else:
    check("palette combo index maps to PALETTE_ORDER", True)

# Palette, map style and layout template are independent controls.
dark_combo = dock.palette_combo.findData("terrain_dark")
dock.palette_combo.setCurrentIndex(dark_combo)
app.processEvents()
check("dark palette does not change map style", dock.cartography_combo.currentData() == "natural_earth", str(dock.cartography_combo.currentData()))
light_combo = dock.palette_combo.findData("natural")
dock.palette_combo.setCurrentIndex(light_combo)
app.processEvents()
check("palette is always enabled", dock.palette_combo.isEnabled())

# Manual map style and layout choices survive palette changes.
dock.cartography_combo.setCurrentIndex(dock.cartography_combo.findData("usgs_classic"))
app.processEvents()
dark_combo = dock.palette_combo.findData("dark_forest")
dock.palette_combo.setCurrentIndex(dark_combo)
app.processEvents()
check("manual map style survives dark palette", dock.cartography_combo.currentData() == "usgs_classic")
dock.layout_template_combo.setCurrentIndex(
    dock.layout_template_combo.findData("engineering_titleblock")
)
dock.palette_combo.setCurrentIndex(dock.palette_combo.findData("natural"))
app.processEvents()
check("layout template survives palette change", dock.layout_template_combo.currentData() == "engineering_titleblock")
check("A/B comparison removed", not hasattr(dock, "compare_style_combo"))
dock.layout_template_combo.setCurrentIndex(
    dock.layout_template_combo.findData("classic_topo")
)

# defaults
check("open_layout default unchecked", not dock.open_layout_check.isChecked())
check("create_project default checked", dock.create_project_check.isChecked())
check("peak spin default 80", dock.spot_pct_spin.value() == 80, str(dock.spot_pct_spin.value()))
check("contour smoothing default Medium", dock.smoothing_combo.currentIndex() == 2, str(dock.smoothing_combo.currentIndex()))
check("hydrology default unchecked", not dock.hydrology_check.isChecked())
check("twi default unchecked", not dock.twi_check.isChecked())
check("basins default unchecked", not dock.basins_check.isChecked())
base_map = {"CREATE_MULTI_HILLSHADE", "CREATE_SPOT_ELEVATIONS"}
checked = {key for key, cb in dock.products.items() if cb.isChecked()}
check("products default = minimal basemap", checked == base_map, str(checked))
check("layout default = classic topo", dock.layout_template_combo.currentData() == "classic_topo", str(dock.layout_template_combo.currentData()))

# parameters plumbing
params = dock._parameters()
check("parameters carry SPOT_PCT", params.get("SPOT_PCT") == 80)
check("parameters carry PALETTE index of natural", params.get("PALETTE") == PALETTE_ORDER.index("natural"), str(params.get("PALETTE")))
config = dock._cartography_config()
check("config carries create_project", config.get("create_project") is True)
check("config preset follows cartography combo", config.get("preset") == dock.cartography_combo.currentData(), config.get("preset"))
check("config carries independent layout template", config.get("layout_template") == dock.layout_template_combo.currentData(), config.get("layout_template"))
check("config carries grid mode", config.get("grid_mode") == dock.grid_mode_combo.currentData(), config.get("grid_mode"))
check("config carries design state", config.get("design_preset") in {"standard_topo", "custom"}, config.get("design_preset"))
dock.cartography_combo.setCurrentIndex(dock.cartography_combo.findData("natural_earth"))
app.processEvents()
config = dock._cartography_config()
check("config preset = natural_earth (default)", config.get("preset") == "natural_earth")

print()
if failures:
    print(f"FAILURES: {failures}")
    sys.exit(1)
print("🎉 ALL FEATURE-BATCH PROBES PASSED 🎉")
