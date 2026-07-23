# Fig 9 & 10 — Fjord ice cover and freshwater fluxes

This folder builds two figures for three southern Greenland fjord systems —
**Sermilik–Ikersuaq**, **Tunulliarfik**, and **Igalikup Kangerlua** — using the
GreenFjord fjord palette (glacier blue `#2C7FB8`, mulberry `#9E3D88`, terracotta
`#D55E4B`).

**Fig 9 — `fig9-ice_cover_fluxes.png`** (`plot_ice_cover_fluxes.py`). A 2×3 grid,
one column per fjord. The **top row** shows boxplots of monthly sea-ice
concentration (% cover) split into **Inner / Mid / Outer** fjord zones; the dashed
grey line is the mean coastal-ocean ice cover for reference. The **bottom row**
shows three annual water-budget bars per fjord (km³ yr⁻¹): **ice flux**,
**annual freshwater flux**, and **ocean melt** (ice flux × its tabulated
ratio-to-ice-flux), each summed over the glaciers in that fjord.

**Fig 10 — `fig10-ice_cover_timeseries.png` / `.pdf`**
(`plot_ice_cover_time_series.py`). Three stacked time-series panels (**Inner / Mid
/ Outer**), each plotting monthly ice cover (%) for all three fjords over
2014-10 → 2024-10, with the coastal-ocean series overlaid on the Outer panel and
horizontal reference lines at 50 % and 100 %.

## Run

From the repo root (both scripts read from `data/` and write into this folder):

```bash
uv run --project . python fig9_10-ice_cover_fluxes/plot_ice_cover_fluxes.py
uv run --project . python fig9_10-ice_cover_fluxes/plot_ice_cover_time_series.py
```

Reading the `.xlsx` requires **openpyxl** (added to the project `pyproject.toml`).
Set `MPLCONFIGDIR="$TMPDIR/mpl"` if matplotlib complains about its cache.

## Layout

```
.
├── plot_ice_cover_fluxes.py          # builds Fig 9 (boxplots + flux bars)
├── plot_ice_cover_time_series.py     # builds Fig 10 (ice-cover time series)
├── fig9-ice_cover_fluxes.png         # output — Fig 9
├── fig10-ice_cover_timeseries.png    # output — Fig 10
├── fig10-ice_cover_timeseries.pdf    # output — Fig 10 (vector)
├── data/                             # input datasets
│   ├── fjord_ice_regions-time_series.xlsx
│   ├── fluxes_overviewpaper_tabulated.csv
│   └── fjord_mask.nc
└── examples/
    └── Screenshot 2026-07-14 at 16.36.18.png   # reference screenshot Fig 9 was recreated from
```

## Data

| File | Used by | Content | Units / notes |
|------|---------|---------|---------------|
| `data/fjord_ice_regions-time_series.xlsx` | Fig 9 & 10 | Sheet `seaice_conc`: monthly sea-ice concentration, 2014-10 → 2024-10 (121 months), columns nested by fjord × zone (Inner/Mid/Outer) plus an `Oceanic → Coastal ocean` reference series. Other sheets present but unused: `region_area_num_pixels`, `seaice_area_weighted`, `sod_count`. | ice cover in % |
| `data/fluxes_overviewpaper_tabulated.csv` | Fig 9 | Per-glacier water-budget table: ice flux `qice`, annual freshwater flux `qfwann` (+ uncertainty `dqfwsa`), summer freshwater discharge `qfwsumm`, and ocean melt `qoceanmelt` as a ratio to ice flux. Aggregated to fjord totals in the script. | fluxes in km³ yr⁻¹; ocean melt is a dimensionless ratio |
| `data/fjord_mask.nc` | neither script | Raster fjord-region mask, integer region IDs (1–15), 325×479 grid on **WGS 84 / UTM zone 24N** (EPSG:32624). Retained for reference; not read by the current figures. | — |

### Sources (for citation)

- **Sea-ice concentration** (`fjord_ice_regions-time_series.xlsx`) — monthly
  per-fjord-region sea-ice concentration (sheet `seaice_conc`) plus
  stage-of-development counts (sheet `sod_count`), Oct 2014 onward. The
  "concentration" and "stage of development" fields follow **WMO SIGRID-3 ice-chart
  nomenclature**, indicating the data are derived from operational sea-ice charts
  (for Greenland waters, most plausibly the **DMI — Danish Meteorological Institute
  — Greenland ice charts**). The specific product / provider is **not recorded in
  the workbook** — confirm with the data provider before citing.
- **Fjord flux table** (`fluxes_overviewpaper_tabulated.csv`) — per-fjord/glacier
  ice flux and freshwater discharge; column headers (`qice`, `qfwann`, `qfwsumm`,
  `qoceanmelt`) match the GreenFjord overview-paper tabulation. The underlying
  references are **not recorded in the file** — confirm with the overview-paper
  authors before citing. (Same table as `fig2-sst_t2m_trends/`.)
- **Fjord mask** (`fjord_mask.nc`) — a GreenFjord-derived region mask on **UTM zone
  24N** (EPSG:32624); no `source` attribute is recorded. Project-internal product —
  confirm provenance with the data provider before citing.

The top-boxplot values in Fig 9 were originally estimated from the reference
screenshot in `examples/`; the current script reads **every plotted value** from
the workbook and CSV instead (no hard-coded measurements remain).

Part of the GreenFjord overview-figures set.
