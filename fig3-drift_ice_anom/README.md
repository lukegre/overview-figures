# Fig 3 — Sea-ice cover duration anomaly

Small-multiples map of the **annual sea-ice cover duration anomaly** around
southern Greenland (≈58.6–63°N, 52–40°W), one panel per year over 2014–2025.
For each grid cell the script counts the number of days per year with sea-ice
fraction > 5 %, then subtracts the per-cell 2014–2025 mean to give an anomaly in
**days**. Cells that are ice-covered on fewer than 50 days across the whole record
are masked out. Panels are drawn as filled contours (`contourf`, 11 levels, robust
colour limits) with a shared colourbar.

The data are fetched **live from Copernicus Marine** (no local input file), so a
run requires the `copernicusmarine` client with valid CMEMS credentials and
network access.

Run with the project venv:

```
MPLCONFIGDIR="$TMPDIR/mpl" uv run --project .. python plot_drift_ice_anom.py
```

It downloads the sea-ice fraction subset, computes the anomaly, and writes
`fig3-drift_ice_anom.png` (300 dpi) to this folder.

## Layout

```
.
├── plot_drift_ice_anom.py    # script that builds the figure (entry point)
└── fig3-drift_ice_anom.png   # output figure
```

## Data

| Source | Variable | Access | Extent |
|--------|----------|--------|--------|
| Copernicus Marine `METOFFICE-GLO-SST-L4-REP-OBS-SST` | `sea_ice_fraction` | `copernicusmarine.open_dataset(...)` (live) | ≈57.2–67.5°N, 54.3–35.8°W; 2012-12-31 → 2025-12-31 (analysis window 2014–2025) |

### Sources (for citation)

- **Sea ice fraction** — Met Office / Copernicus Marine Service (CMEMS) product
  **`METOFFICE-GLO-SST-L4-REP-OBS-SST`** (the OSTIA global reprocessed SST/sea-ice
  L4 analysis; current CMEMS id `SST_GLO_SST_L4_REP_OBSERVATIONS_010_011`), as
  specified by the `dataset_id` in the script. OSTIA system reference:

  > Good, S., Fiedler, E., Mao, C., et al. (2020): *The Current Configuration of the
  > OSTIA System for Operational Production of Foundation Sea Surface Temperature and
  > Ice Concentration Analyses*, Remote Sensing, 12, 720,
  > doi:[10.3390/rs12040720](https://doi.org/10.3390/rs12040720).

  Also acknowledge the E.U. Copernicus Marine Service as distributor.

Part of the GreenFjord overview-figures set.
