# Fig 14 — Tidal Plain

This folder recreates a three-panel figure of tidal-flat exposure in a southern
Greenland fjord near Qaqortoq. Panels **(a)** and **(b)** are two Landsat maps of
the fjord (June 4, 1998 and August 20, 1999) with the exposed tidal flats outlined
in orange; panel **(c)** shows normalised tidal-plain area vs. year, coloured by
tide height, with a bootstrapped linear fit and its 99 % confidence band. The
script is driven by `config.yaml`, which exposes the map dates (snapped to the
nearest available scene), colormaps, and scatter/layout properties.

Panels (a)/(b) fetch real Landsat scenes (RGB + SWIR) via `scripts/stac.py` /
`scripts/fetch_landsat.py` from Microsoft Planetary Computer: each requested date
is snapped to the nearest tidal-plain date (from
`data/landsat-rgb_and_tidal_flats-cleaned-1993-2024.nc`), and fetched scenes are
cached in `data/landsat_scenes_fetched/` for offline reruns. Rendering follows the
`1.2_landsat_data.ipynb` recipe — RGB true-colour land base + `cividis` SWIR over
the ocean (navy water / yellow flats) + an orange tidal-flat contour. Panel (c) is
rebuilt from `data/area_tide_height_fit.csv` (scatter logic from
`2.2_landsat_tide_plains-add_tide_info.ipynb`, cell 21); the OLS fit, two-sided
p-value, and bootstrap band are reimplemented in pure NumPy (R² = 0.033,
P = 0.035).

Two data caveats: fetching real terrain requires network access plus the
`stackstac` NumPy-2/pandas-3 shims (there is a flat-colour fallback when
`fetch.enabled: false` or the network is unavailable, in which case land is drawn
neutral grey), and the `1998-08-20` scene is absent from the cleaned netCDF, so the
nearest exact match `1999-08-20` is used for the right map instead.

## Run

Verified from this folder (uses the project env one level up; scenes are already
cached, so no network is needed to reproduce):

```bash
MPLCONFIGDIR="$TMPDIR/mpl" uv run --project .. python plot_tidal_plain_figure.py
```

Output is `fig14-tidal_plain.png`. Pass an alternate config as the first argument
to override `config.yaml`. The `uv` cache may be sandbox-blocked; disable the
sandbox if the run fails to open it.

## Layout

```
.
├── plot_tidal_plain_figure.py   # entry point — builds the 3-panel figure
├── config.yaml                  # all tweakable dates / colormaps / layout
├── fig14-tidal_plain.png        # output figure
├── scripts/                     # helper modules imported by the entry script
│   ├── fetch_landsat.py         # snap date → fetch RGB+SWIR → cache per scene
│   └── stac.py                  # Planetary Computer STAC search / stackstac loaders
├── data/                        # input datasets
│   ├── landsat-rgb_and_tidal_flats-cleaned-1993-2024.nc
│   ├── area_tide_height_fit.csv
│   └── landsat_scenes_fetched/  # cached fetched scenes (1998-06-04.nc, 1999-08-20.nc)
└── examples/                    # exploratory / reference material (not run)
    ├── 1.2_landsat_data.ipynb                       # map-rendering recipe
    ├── 2.2_landsat_tide_plains-add_tide_info.ipynb  # tide + scatter derivation
    ├── tides.py                                     # downloads DTU Space Qaqortoq tide-gauge data
    └── Screenshot 2026-07-17 at 08.41.22.png        # original figure recreated from
```

## Data

| File | Used by | Content | Units / notes |
|------|---------|---------|---------------|
| `data/landsat-rgb_and_tidal_flats-cleaned-1993-2024.nc` | panels (a)/(b) | Cleaned Landsat cube, 138 scenes 1993-07 → 2024. `rgb` (Landsat 8 OLI true colour, per the variable `description`) and `tidal_flats` (binary mask, "tidal flats where swir16 > 0.03"). Grid: 168×178 on **UTM zone 23N** (EPSG:32623), fjord ≈ 45.3° W, 60.9° N. | reflectance (rgb); 0/1 mask (tidal_flats) |
| `data/area_tide_height_fit.csv` | panel (c) | Per-scene table derived in `2.2_…ipynb`: `tidal_plain_area_km2`, `tide_height`, `year`, the logistic detrend of area-vs-tide (`plain_area_trend_logistic`) and its residual `tidal_plain_area_logistic_norm_to_tide_height` (plotted y), and `time_dt0` (days since first year, plotted x). | area in km²; tide height in m |
| `data/landsat_scenes_fetched/*.nc` | panels (a)/(b) | Cache of the two fetched scenes (RGB + `swir16`), reprojected onto the netCDF grid by `fetch_landsat.py`. Regenerated on demand if deleted. | reflectance |

### Sources (for citation)

- **Landsat imagery and tidal-flat mask**
  (`landsat-rgb_and_tidal_flats-cleaned-1993-2024.nc`, `landsat_scenes_fetched/`) —
  **Landsat Collection 2 Level-2 surface reflectance** (`landsat-c2-l2`), retrieved
  from the **Microsoft Planetary Computer** STAC catalogue
  (`https://planetarycomputer.microsoft.com/api/stac/v1`) via `scripts/stac.py`. The
  `rgb` variable is recorded as "RGB imagery from Landsat 8 OLI"; the `tidal_flats`
  mask is defined as "tidal flats where swir16 > 0.03". Cite the USGS/NASA Landsat
  program as the underlying data provider.
- **Tide height** (`tide_height` column) — reconstructed from a **UTide** harmonic
  analysis (OLS, `lat = 60.4`) fitted to detrended tide-gauge observations for
  **Qaqortoq, Greenland**, 2005–2024, then evaluated at each Landsat scene time (see
  `2.2_…ipynb`, cells 2–10). The underlying high-frequency gauge record is
  downloaded by `examples/tides.py` from the **DTU Space** (Technical University of
  Denmark, National Space Institute) sea-level FTP archive
  (`ftp.space.dtu.dk/pub/Sealevel/`), station **Qaqortoq** (PSMSL station 980/045).
  DTU Space carries no formal dataset DOI — acknowledge DTU Space as the data
  producer (contact: Ole B. Andersen, DTU Space).

  The same record is archived through the **University of Hawaiʻi Sea Level Center
  (UHSLC)** — the official distribution channel from 2005 onward
  (`uhslc.soest.hawaii.edu/data/`, noted in `examples/tides.py`). If citing the
  UHSLC/Joint Archive holdings, use:

  > Caldwell, P. C., Merrifield, M. A., and Thompson, P. R. (2015): *Sea level
  > measured by tide gauges from global oceans — the Joint Archive for Sea Level
  > holdings (NCEI Accession 0019568)*, Version 5.5, NOAA National Centers for
  > Environmental Information, doi:[10.7289/V5V40S7W](https://doi.org/10.7289/V5V40S7W).

Part of the GreenFjord overview-figures set.

## Log

- **08:42 — User request:** "Recreate the screenshot — most of the data you need is in the CSV. Code to create the scatter plot is in the notebook. The map data is in the netCDF. Create this all in a python script. Log this conversation in a README.md using a sonnet low effort subagent. Put the log data in a level 2 log subheading. Log my requests and your responses with times."
- **08:43 — Assistant:** Explored the folder (screenshot, notebook, CSV, netCDF). Read the screenshot: panel (a) two dated fjord maps with orange-outlined tidal flats, panel (b) scatter of normalised tidal-plain area vs year coloured by tide height with regression line, R²=0.033, P=0.035.
- **08:48 — Assistant:** Inspected the CSV (columns match notebook cell 21) and the netCDF via xarray (needed the `h5netcdf`/`h5py` backend). Found the netCDF RGB footprint is constant over time and covers only the fjord water body; land is NaN. Discovered `1998-08-20` is not in the cleaned file (only `1998-05-19` and `1998-06-04`); nearest exact August-20 match is `1999-08-20`.
- **08:55 — Assistant:** Confirmed panel (b) reproduces exactly from the CSV (R²=0.033, P=0.035). Only matplotlib/numpy/pandas available in the env (no seaborn/scipy/statsmodels), so implemented OLS, the two-sided p-value (regularised incomplete beta), and the bootstrap confidence band in pure numpy. Added `h5py` to project dependencies so the netCDF can be read.
- **09:02 — Assistant:** Wrote `plot_tidal_plain_figure.py` producing the two-panel figure; navy water fill, grey land, yellow/orange tidal flats for panel (a); Spectral_r-coloured scatter with discrete tide-height legend, trend line and 99% bootstrap band for panel (b).
- **09:05 — Assistant:** Rendered and refined the figure (fixed the panel-b label placement and the clipped 1993 x-tick). Final output matches the screenshot; delegated writing this README log to a Sonnet subagent.
- **09:08 — User request:** "Keep the README logger subagent running in the background to keep track of our conversation."
- **09:08 — Assistant:** Kept this logger agent alive as the ongoing session logger; will forward each new exchange for it to append under `## Log`. Noted that a subagent can't autonomously observe the chat — the main assistant relays each turn to it.
- **09:10 — User request:** "Have a look in the landsat data notebook to learn how to plot the maps correctly. Also add a YAML config file to tweak plot elements (map dates using nearest, map cmaps, scatter colormap, scatter properties, etc.). Remove the vertical line between the plots."
- **09:14 — Assistant:** Read `1.2_landsat_data.ipynb` — maps are rendered by colouring the SWIR/ocean field with `cividis` (dark-navy water at low values, yellow tidal flats at high values) plus an orange tidal-flat contour, over an RGB true-colour base. Confirmed the cleaned netCDF stores only `rgb` (fjord-only, land NaN) and `tidal_flats` — no SWIR — so reproduced the same look via `cividis` applied to a field that is 0 over the fjord and `flat_value` on the flats. Added `config.yaml` exposing map dates (nearest scene used), map cmap/vmin/vmax/flat colour/contour, scatter cmap and marker/line/band/legend properties, and layout. Refactored `plot_tidal_plain_figure.py` to read the config, and removed the vertical divider between panels (now a `layout.divider` toggle, default false). Re-rendered successfully.
- **09:16 — User request:** "I've added a stac.py that gives tools to fetch the right data. Fetch only data for which there are tidal-plain dates. Workflow: 1) user requests date, 2) find nearest date in the Landsat RGB, 3) find SWIR data."
- **09:35 — Assistant:** Read `stac.py` (`get_landsat` -> Landsat C2 L2, RGB + swir16, 30 m, EPSG 32623, via Planetary Computer). Added deps `planetary-computer`, `pystac-client`, `stackstac`, `loguru`. The pinned `stackstac` 0.5.0 is incompatible with NumPy 2 / pandas 3, so added two small shims (`np.can_cast` for python scalars; strip `infer_datetime_format` from `pd.to_datetime`). Wrote `fetch_landsat.py`: snaps the requested date to the nearest tidal-plain date in the netCDF, fetches that scene's RGB + SWIR, reprojects onto the netCDF grid, and caches per-scene netCDFs in `landsat_scenes_fetched/` (so later runs are offline). Rewired `draw_map` to the notebook's true recipe — RGB true-colour land base + `cividis` SWIR over ocean (ocean-median subtracted, clipped >=0) + orange tidal-flat contour — with a flat-colour fallback if `fetch.enabled: false` or the network is unavailable. Added a `fetch:` section to `config.yaml` (enabled, bbox, max_cloud_cover, cache_dir) and replaced the old map colour keys with `rgb_vmax` / `swir_cmap` / `swir_vmin` / `swir_vmax`. Result now shows real terrain, dark-navy water, and yellow flats — matching the screenshot; the right panel is 1998-08-20's nearest tidal-plain scene, 1999-08-20.
- **09:53 — Assistant:** Reorganised the folder to the repo-standard layout: data files → `data/` (incl. the `landsat_scenes_fetched/` cache), imported helpers → `scripts/`, notebooks + original screenshot → `examples/`; removed the `__pycache__` bytecode. Updated `config.yaml` data/cache paths, added `scripts/` to the entry script's `sys.path`, and resolved `cache_dir` to an absolute path so `fetch_landsat` still finds the cache under `data/`. Re-ran the script from the new layout — figure regenerated identically from the cached scenes.
