# sst_dmioi_monthly

Monthly sea-surface temperature of the GreenFjord domain, from the DMI OI
Arctic L4 daily reprocessed product.

## Contents

`sst_dmioi_monthly.zarr` (zarr v2, dims `time`, `latitude`, `longitude`):

| Variable | Units | Meaning |
|---|---|---|
| `analysed_st` | K | monthly mean of the daily analysed SST; days with sea-ice fraction >= 0.05 are masked |
| `analysis_error` | K | monthly mean of the daily analysis error, same masking |
| `sea_ice_frac` | 1 | monthly mean sea-ice fraction (not masked) |

Coverage: 1982-01 to 2025-12 (528 months), 54.23 to 35.78 deg W, 58 to
67.75 deg N, 0.05 deg grid.

## Source

Arctic Ocean Sea and Ice Surface Temperature L4 REPROCESSED (DMI, via CMEMS):
dataset `cmems_obs_si_arc_phy_my_L4-DMIOI_P1D-m`. This is source S4 in
[`DATA_SOURCES.md`](../../DATA_SOURCES.md) (citation there).

## Regenerate

```
.venv/bin/python data/sst_dmioi_monthly/download_sst_dmioi_monthly.py
```

Needs `COPERNICUSMARINE_SERVICE_USERNAME` / `_PASSWORD` in `.env`. The daily
subset is saved in `raw/` and then resampled to monthly means. The request
(bounding box, period, variables) is reconstructed from the metadata of the
existing file and was not run when this folder was created, so check that the
rebuilt file matches the current one before replacing it.

## Used by

- `figures/fig2-SST_T2m_TRENDS/plot_SST_T2m_TRENDS.py`
- `figures/figS_SST_TREND_PERIODS/plot_S_SST_TREND_PERIODS.py`
