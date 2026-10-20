# dmi_metobs_narsarsuaq

Hourly station observations at Narsarsuaq airport (DMI station 04270).

## Contents

`dmi_metobs_narsarsuaq.csv`: index `time` (UTC, hourly, 1961-01-01 to 2026-10-15),
columns `mean_air_temp` (deg C), `abs_max_temp_last_hour`,
`abs_max_temp_last_12_hours`, `abs_min_temp_last_hour`,
`abs_min_temp_last_12_hours` (deg C), `mean_rel_humidity` (%),
`mean_wind_speed`, `highest_wind_speed_last_hour` (m s-1),
`mean_wind_direction`, `mean_wind_direction_last_hour` (deg),
`air_pressure_sea_level` (hPa), `accum_precip_last_hour` (mm),
`cloud_cover_percent` (%). Early years are 3-hourly, so most rows are empty
before about 2000. The data are raw, not quality controlled.

## Source

DMI open data API, `metObs` (<https://www.dmi.dk/friedata/dokumentation/meteorological-observation-api>).
This is source S32 in [`DATA_SOURCES.md`](../../DATA_SOURCES.md).

## Regenerate

```
.venv/bin/python data/dmi_metobs_narsarsuaq/download_dmi_metobs_narsarsuaq.py
```

No credentials needed. The script calls
`greenfjord.data.weather_station_dmi.fetch_dmi_station` and fetches the full
record up to now, so the end date differs from the file in the repo.

## Used by

- `figures/fig2-SST_T2m_TRENDS/plot_SST_T2m_TRENDS.py`
  (panel c, annual mean of `mean_air_temp`)
