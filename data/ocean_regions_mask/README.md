# ocean_regions_mask

Ocean regions of the GreenFjord domain, defined from bathymetry and distance
to coast.

## Contents

`ocean_regions_mask.nc`: variable `region` (`y`, `x`, class label, no units)
on a regular lat/lon grid (`y` 58 to 63 deg N, `x` 52 to 40 deg W, about
0.004 deg). Classes (also in the `names` attribute, '|'-joined):

| Value | Region |
|---|---|
| 0 | Near-shore, < 4 km from coast (not used) |
| 1 | Oceanic (deeper than 500 m) |
| 2 | Southwest (east of 47.8 deg W, west of 44.3 deg W) |
| 3 | Central western (west of 47.8 deg W) |
| 4 | South Eastern (east of 44.3 deg W) |

Shelf: shallower than 500 m and more than 4 km offshore. Open ocean: deeper
than 500 m and more than 10 km offshore. Each region is cleaned with a
morphological closing (disk, radius 5 pixels) and small-hole removal
(10 000 pixels).

## Source

GEBCO 2023 bathymetry and distance to coast (0.1 deg), read from the project S3
bucket. This is source S7 in [`DATA_SOURCES.md`](../../DATA_SOURCES.md)
(citation there).

## Regenerate

```
.venv/bin/python data/ocean_regions_mask/download_ocean_regions_mask.py
```

Needs the S3 credentials in `.env`. The mask is computed by
`greenfjord.data.other.get_ocean_regions`; the script only sets its
parameters and writes the file.

## Used by

- `figures/fig2-SST_T2m_TRENDS/plot_SST_T2m_TRENDS.py`
- `figures/figS_SST_TREND_PERIODS/plot_S_SST_TREND_PERIODS.py`
