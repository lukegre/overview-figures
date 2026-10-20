# era5_monthly_south_greenland

ERA5 monthly means of near-surface variables over south Greenland.

## Contents

`era5_monthly_south_greenland.nc` (netCDF, dims `valid_time`, `latitude`,
`longitude`): 1982-01 to 2025-12 (528 months), 55 to 70 deg N, 80 to 30 deg W,
0.25 deg grid.

| Variable | Meaning | Units |
|---|---|---|
| `t2m` | 2 m temperature | K |
| `d2m` | 2 m dewpoint temperature | K |
| `msl` | mean sea level pressure | Pa |
| `cbh` | cloud base height | m |
| `si10` | 10 m wind speed | m s-1 |
| `tcc` | total cloud cover | 1 |
| `lcc` | low cloud cover | 1 |

`era5_monthly_south_greenland-subset.nc` is a spatial crop of the same data
(57.25 to 67.5 deg N, 54.25 to 36 deg W). No script reads it and no code that
made it is recorded.

## Source

ERA5 monthly averaged reanalysis on single levels
(`reanalysis-era5-single-levels-monthly-means`), Copernicus Climate Change
Service (C3S) / ECMWF; Hersbach et al. 2020, doi:10.1002/qj.3803. This is
source S6 in [`DATA_SOURCES.md`](../../DATA_SOURCES.md).

## Regenerate

```
.venv/bin/python data/era5_monthly_south_greenland/download_era5_monthly_south_greenland.py
```

Needs a CDS account: `cdsapi` reads `CDSAPI_URL` / `CDSAPI_KEY` from `.env`, or
`~/.cdsapirc`. The request (variables, years, area) is rebuilt from the
metadata of the existing file and was not run when this folder was created.
The full request is too large for CDS, so the script splits it into 5-year
chunks (1982-1985, 1986-1990, ..., 2021-2025), runs them two at a time
(`MAX_CONCURRENT`, due to the CDS rate limit), then concatenates them along `valid_time` and deletes the
chunk files. The script also holds `merge()`, kept from the earlier `era5_request.py`, for
combining several downloaded files.

## Used by

- `figures/fig2-SST_T2m_TRENDS/plot_SST_T2m_TRENDS.py` (panel c, `t2m`)
- `figures/figS_T2M_TREND_PERIODS/plot_S_T2M_TREND_PERIODS.py` (`t2m`)
- `figures/fig5-ERA_TREND_SIG/plot_ERA_TREND_SIG.py` (`t2m`, `d2m`, `tcc`, `lcc`, `cbh`, `si10`)
