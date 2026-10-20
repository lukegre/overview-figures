# sea_ice_dmioi_daily

Daily sea-ice fraction around southern Greenland, from the DMI OI Arctic L4
daily reprocessed product.

## Contents

`sea_ice_dmioi_daily.nc` (NetCDF, dims `time`, `latitude`, `longitude`):

| Variable | Units | Meaning |
|---|---|---|
| `sea_ice_fraction` | 1 (fraction, 0-1) | daily sea-ice fraction, float32; attribute `source_dataset_id` names the CMEMS dataset |

Coverage: 1982-01-01 to 2025-12-31 (daily), 58.5 to 63.1 deg N, 52.075 to
39.925 deg W, 0.05 deg grid. This is the plot extent (58.6-63 deg N,
52-40 deg W) plus a 0.1 deg buffer.

## Source

Arctic Ocean Sea and Ice Surface Temperature L4 REPROCESSED (DMI, via CMEMS):
dataset `cmems_obs_si_arc_phy_my_L4-DMIOI_P1D-m`. This is source S4 in
[`DATA_SOURCES.md`](../../DATA_SOURCES.md) (citation there).

## Regenerate

```
.venv/bin/python data/sea_ice_dmioi_daily/download_sea_ice_dmioi_daily.py
```

Needs `COPERNICUSMARINE_SERVICE_USERNAME` / `_PASSWORD` in `.env`. The request
parameters (dataset, variable, bounding box, period) are constants at the top
of the script. The file was copied from the cache of `figS_SEAICE_PHENOL` (formerly `figS-sea_ice_seasonlity`)
and the script reproduces that request; it was not run when this folder was
created, so check that a rebuilt file matches the current one before
replacing it.

## Used by

- `figures/fig3-DRIFT_ICE_ANOMS/plot_DRIFT_ICE_ANOMS.py`
- `figures/fig4-ICE_CHL_SEAS_DURATION/plot_ICE_CHL_SEAS_DURATION.py`
- `figures/figS_SEAICE_PHENOL/plot_S_SEAICE_PHENOL.py` (`dmioi` product)
