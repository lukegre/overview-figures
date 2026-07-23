# Fig 2 — Decadal SST & 2 m air-temperature trends

Multi-panel figure summarising decadal warming across the GreenFjord domain
(southern Greenland). Panel **(a)** is the **regional mask** — bathymetry-derived
ocean regions (Oceanic, Southwest, Central western, South Eastern) plus the
GreenFjord AOI outline and the ice-sheet box. Panels **(b–d)** show decadal
**Sea Surface Temperature (SST)** as small per-region bar plots, and panels
**(e–g)** show decadal **2 m air temperature** (ERA5 `t2m`) for the land / ocean /
ice subsets.

Each mini-panel plots one bar per decade (1980s → 2010s); the bar height is the
decadal **mean** and the error bar is the **standard deviation**. Bars fade from
light (1980s) to solid (2010s) so the decade progression reads left-to-right while
the hue keeps the region identity, matched to the colours in the regional-mask map
(Oceanic=C0, Southwest=C1, Central western=C2, South Eastern=C3, Ice=C4). Units are
°C throughout.

Run with the project venv so the package and its deps are importable:

```
MPLCONFIGDIR="$TMPDIR/mpl" uv run --project .. python plot_sst_t2m_trends.py
```

It reads the stats workbook and cached mask from `data/` and writes
`fig2-sst_t2m_trends.png` (300 dpi) to this folder. The regional mask is cached to
`data/regions_mask.nc`; delete it to force a rebuild from GEBCO bathymetry (needs
the `greenfjord_trends` package and network/S3 access).

## Layout

```
.
├── plot_sst_t2m_trends.py            # script that builds the figure (entry point)
├── fig2-sst_t2m_trends.png           # output figure
├── data/                             # input datasets
│   ├── decade_distribution_stats.xlsx   # decadal SST & ERA5 stats (sheets SST, ERA5)
│   ├── regions_mask.nc                  # cached regional mask (GEBCO-derived)
│   └── fluxes_overviewpaper_tabulated.csv  # glacier flux table (not used by script)
└── examples/                         # exploratory / superseded material
    ├── region_plots.ipynb               # original region-map + bar-plot notebook
    ├── domains.ipynb                    # domain / SST-gradient exploration
    ├── distributions-figure.png         # earlier distribution figure
    └── regions-mask.pdf                 # earlier regional-mask export
```

The script also reads `<repo>/data/era5-land-ocean-ice.gpkg` (land / ocean / ice
polygons for the map overlay), which lives at the repo root, not in this folder.

## Data

| File | Contents | Units | Notes |
|------|----------|-------|-------|
| `data/decade_distribution_stats.xlsx` | decadal median/mean/std of SST and 2 m air temperature per region | °C | sheets `SST` and `ERA5`; three header rows, decade forward-filled |
| `data/regions_mask.nc` | regional mask (Oceanic / Southwest / Central western / South Eastern / Ice) | class label | cache of `greenfjord_trends.data.other.get_ocean_regions()`; regions from bathymetry + distance to coast (shelf: depth > −500 m & > 4 km offshore; open ocean: depth < −500 m & > 10 km offshore) |
| `data/fluxes_overviewpaper_tabulated.csv` | per-fjord/glacier ice flux, annual & summer freshwater flux, ocean-melt ratio | km³ · yr⁻¹ (ratio for melt) | **not used by the current script**; retained from the overview-paper tabulation |
| `<repo>/data/era5-land-ocean-ice.gpkg` | land / ocean / ice polygons for the map overlay | — | produced by `examples/region_plots.ipynb`; lives at repo root |

### Sources (for citation)

- **SST** (`decade_distribution_stats.xlsx`, sheet `SST`) — derived from a **DMI**
  (Danish Meteorological Institute) SST / sea-ice product, accessed via
  `ocean.get_sst_ice_dmi()` (variable `analysed_st`) in `examples/domains.ipynb`.
  The exact product name/version is **not recorded in the workbook metadata** —
  confirm with the data provider before citing.
- **2 m air temperature** (`decade_distribution_stats.xlsx`, sheet `ERA5`) —
  **ERA5** reanalysis `t2m`, accessed via `era5_load.get_era5()` in
  `examples/region_plots.ipynb`. ERA5: Hersbach et al. (2020), Copernicus Climate
  Change Service (C3S) / ECMWF.
- **Regional mask** (`regions_mask.nc`) — **GEBCO** gridded bathymetry
  (<https://www.gebco.net/data_and_products/gridded_bathymetry_data/>) combined with
  distance-to-coast, via `greenfjord_trends.data.other.get_ocean_regions()`.
- **Glacier fluxes** (`fluxes_overviewpaper_tabulated.csv`) — source **not recorded
  in the file**; these are overview-paper flux values (Sermilik / Narsarsuaq /
  Igaliku fjords). Confirm the underlying reference with the data provider.
- The `domains.ipynb` exploration additionally used CMEMS surface currents
  (`cmems_obs_mob_glo_phy-cur_my_0.25deg_P1M-m`), which do **not** feed the final
  figure.

Part of the GreenFjord overview-figures set.
