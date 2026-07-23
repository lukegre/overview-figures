# Fig 5 — Significant-trend pixel fraction per ERA5 variable and season

Heatmap summarising, for each atmospheric variable and season, the **net signed
fraction of pixels with a statistically significant trend** across the GreenFjord
domain (southern Greenland). Each cell is `positive − |negative|` fraction (×100,
so in **%**): the share of grid cells with a significant *increasing* trend minus
the share with a significant *decreasing* trend. Values are rendered on a diverging
`coolwarm` scale centred at zero (blue = net decreasing, red = net increasing),
spanning −100 % to +100 %; cells with |value| < 5 % are hidden to reduce clutter.
Rows are ordered from most-positive to most-negative net fraction.

Six variables are shown: 2 m temperature, dewpoint temperature, total cloud cover,
low cloud cover, cloud base height, and 10 m wind speed. (The CSV holds more
variables than are plotted — see the Data section.)

Two layouts of the **same data and styling** are kept:

- `fig5-era5_pixel_frac.png` — seasons on the Y-axis, variables on the X-axis.
- `fig5-era5_pixel_frac_transposed.png` — variables on the Y-axis, seasons on the
  X-axis (near-zero cells masked to a cream background).

`examples/original.png` is the superseded per-variable bar plot that these heatmaps
replaced.

## Run

Run with the project venv so the deps are importable:

```
MPLCONFIGDIR="$TMPDIR/mpl" uv run --project .. python plot_era5_pixel_frac.py
MPLCONFIGDIR="$TMPDIR/mpl" uv run --project .. python plot_era5_pixel_frac_transposed.py
```

Each reads the CSV from `data/` and writes its PNG (200 dpi) to this folder.

## Layout

```
.
├── plot_era5_pixel_frac.py               # entry point — seasons × variables heatmap
├── plot_era5_pixel_frac_transposed.py    # entry point — variables × seasons heatmap
├── fig5-era5_pixel_frac.png              # output figure (regular)
├── fig5-era5_pixel_frac_transposed.png  # output figure (transposed)
├── data/
│   └── era5-greenfjord-significant_trend_pixel_frac.csv
└── examples/
    └── original.png                      # superseded per-variable bar plot
```

## Data

| File | Contents | Units | Notes |
|------|----------|-------|-------|
| `data/era5-greenfjord-significant_trend_pixel_frac.csv` | fraction of pixels with a significant trend, split by sign (`negative`/`positive`) and season (DJF/MAM/JJA/SON), per variable | fraction 0–1 (scaled to % in the plot) | two-row header (`sign`, `season`); negatives stored as negative values; 15 variables listed, 6 plotted |

Variables present in the CSV but **not** plotted: `ptype`, `High cloud cover`,
`sst`, `msl`, `Total precipitation`, `10m wind gust`, `Surface pressure`,
`Medium cloud cover` (kept in the file for completeness).

### Sources (for citation)

- **ERA5** reanalysis (Hersbach et al. 2020, Copernicus Climate Change Service
  (C3S) / ECMWF; doi:[10.1002/qj.3803](https://doi.org/10.1002/qj.3803)) — **all**
  rows are ERA5 single-level fields, per the `era5-greenfjord-` filename prefix.
  This includes the `sst`, `msl`, `ptype` and `10m wind gust` rows: `sst` is ERA5's
  own sea-surface-temperature parameter — a prescribed boundary field that ERA5
  ingests from external SST analyses (HadISST2 before 2007, OSTIA from 2007 on) and
  redistributes as part of ERA5, so it is cited here as ERA5 rather than as a
  separate product.
- **Trend method & significance test** — the CSV records only the resulting pixel
  fractions (fraction of ERA5 pixels with a significant seasonal trend, split by
  sign); the underlying trend estimator, significance test (e.g. Theil–Sen /
  Mann–Kendall) and the analysis period are **not recorded in the file metadata** —
  confirm with the analysis author before citing.

Part of the GreenFjord overview-figures set.
