# fjord_bathymetry

BedMachine v6 bathymetry along the centreline of the two GreenFjord study
fjords (a long-section of each fjord).

## Contents

One NetCDF per aggregation method and fjord:
`fjord_bathymetry_<agg_method>_fjord_<fjord_num>.nc`.

- `agg_method`: statistic taken across each cross-fjord polygon: `min`
  (deepest point, the thalweg), `median`, `mean` or `max` (shallowest).
- `fjord_num`: `54` = glacial fjord (Narsaq), `56` = land fjord (Qaqortoq).

Each file has one dimension and coordinate, `distance_to_glacier_km` (km along
the centreline from the glacier end, ascending, 0.5 km spacing), and three
variables on it:

| Variable | Unit | Meaning |
|---|---|---|
| `bathymetry` | m | BedMachine bed elevation, aggregated per polygon (negative below sea level) |
| `polygon_area` | m2 | area of the cross-fjord polygon |
| `polygon_width` | m | width of the cross-fjord polygon |

Coverage: fjord 54 runs 0 to 123 km from the glacier (247 points), fjord 56
0 to 77.5 km (156 points). The `bathymetry` attributes are those of the
BedMachine file (v6.6) plus `agg_func`.

## Source

BedMachine Greenland v6 (source S25 in [`DATA_SOURCES.md`](../../DATA_SOURCES.md),
citation there) aggregated onto the fjord
centreline geometry in `data/fjords/fjord_<n>/fjord_aggregator.pkl_joblib`
(source S26, built by `greenland-fjord-properties`).

Inputs, kept in this repository's `data/`:

- `data/fjord_bathymetry/BedMachineGreenland_bed-v6.tif` (844 MB, git-ignored; NSIDC IDBMG4 v6,
  doi:10.5067/6B6B225B8V2D, landing page https://nsidc.org/data/idbmg4/versions/6)
- `data/fjords/fjord_<n>/` (git-ignored)

## Regenerate

```
.venv/bin/python data/fjord_bathymetry/download_fjord_bathymetry.py
```

Takes under a minute. The fjord numbers, aggregation methods and polygon
spacing are constants at the top of the script. It uses `fjord_props`
(installed from `pacakges/greenland-fjord-properties`).

## Used by

- `figures/fig11_CTD_SECTIONS/plot_CTD_SECTIONS.py` (default `mean`; other methods
  via `bathymetry.agg_method`)
- `figures/fig12_FISH/plot_FISH.py` (`min`)
