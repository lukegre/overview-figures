# Fig 4 — Sea ice & chlorophyll bloom phenology trends

Two-panel map of long-term phenology change around southern Greenland (≈58–63°N,
52–40°W): panel **(a)** the trend in annual **sea ice duration** and panel **(b)**
the trend in **chlorophyll bloom duration**, both in days · yr⁻¹ on diverging
colour scales centred on zero (blue/red for sea ice, brown/green for chlorophyll).
Trends are per-pixel **Theil–Sen slopes** with **Mann–Kendall** significance
testing (as recorded in the sea ice netCDF attributes). Small isolated chlorophyll
patches (< 20 connected pixels) are masked out before plotting to suppress speckle.

Run with `uv run python plot_ice_chla_phenology.py` — it reads the two trend files
from `data/` and writes `fig4-ice_chla_phenology.png` (300 dpi, transparent) to
this folder.

## Layout

```
.
├── plot_ice_chla_phenology.py     # script that builds the figure
├── fig4-ice_chla_phenology.png    # output figure
├── data/                          # input datasets
│   ├── seaice_duration_trend.nc
│   ├── chlorophyll_bloom_duration_trend.nc
│   └── seaice_seasonal.nc
└── examples/
    └── figure4.ipynb              # original exploratory notebook (6-panel version)
```

## Data

| File | Variable | Units | Grid | Notes |
|------|----------|-------|------|-------|
| `data/seaice_duration_trend.nc` | sea ice duration trend | days · yr⁻¹ | `y`, `x` (lat/lon) | Theil–Sen + Mann–Kendall (`method: theilsen_mannkendall`); panel (a) |
| `data/chlorophyll_bloom_duration_trend.nc` | bloom duration trend | days · yr⁻¹ | `lat`, `lon` | panel (b) |
| `data/seaice_seasonal.nc` | seasonal sea ice area fraction (DJF/MAM/JJA/SON) | % | `y`, `x` | not used by the current script; retained from the notebook's 6-panel version |

### Sources (for citation)

- **Sea ice** (`seaice_duration_trend.nc`, `seaice_seasonal.nc`) — derived from sea
  ice concentration recorded as: **OSI SAF, ESA CCI, CMEMS Baltic and SMHI** sea
  ice concentration products (per the `source` attribute in `seaice_seasonal.nc`).
- **Chlorophyll** (`chlorophyll_bloom_duration_trend.nc`) — bloom phenology
  (`duration`) derived from **OC-CCI v6.0** ocean-colour chlorophyll-*a* at 4 km
  resolution, from the *Global Phytoplankton Phenological Indices* dataset:

  > Nicholson, S., Ryan-Keogh, T., Thomalla, S., Chang, N., & Smith, M. (2023).
  > *Global Phytoplankton Phenological Indices – 4 km resolution* (Version 1.0)
  > [Dataset]. Zenodo. https://doi.org/10.5281/zenodo.8402932 (CC-BY-4.0)

  The download/preprocessing code is in
  [`examples/chl_phenology_nicholson.py`](examples/chl_phenology_nicholson.py):
  it fetches the Zenodo file (4/9/25 km variants), subsets to bbox
  `(-60, 55, -35, 65)` W/S/E/N, and stacks the three bloom-detection methods
  (`cs`, `rc`, `ts`). Panel (b) uses the `duration` variable; the trend shown is
  its per-pixel Theil–Sen slope over time.

Part of the GreenFjord overview-figures set.
