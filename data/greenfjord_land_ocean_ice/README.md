# greenfjord_land_ocean_ice

Land, ocean and ice polygons of the GreenFjord area, used to average ERA5
fields (rasterised onto the ERA5 grid) and to draw the map overlay in Fig 2.

## Contents

`greenfjord_land_ocean_ice.gpkg` (GeoPackage, one layer, 3 rows, one polygon
each). CRS EPSG:4326 (lon/lat). Bounds: 48.125 to 43.875 deg W, 59.375 to
61.875 deg N (`[-48.125, 59.375, -43.875, 61.875]`).

| Row | `index` | Raster value | Meaning |
|---|---|---|---|
| 0 | `land` | 1 | land area |
| 1 | `ocean` | 2 | ocean area |
| 2 | `ice` | 3 | ice (sheet / glacier) area |

Columns: `index` (text, the names above) and `geometry`. The raster value is
the row order plus one, so keep the row order when editing the file.

## Source

GreenFjord-derived, internal; there is no external source or citation. Made
interactively in
`fig2-sst_t2m_trends/archive/examples/region_plots.ipynb` (archived, not in git).
This is source S8 in [`DATA_SOURCES.md`](../../DATA_SOURCES.md).

## Regenerate

There is no regeneration script. The file was written by the notebook above
(`df.to_file(..., driver='GPKG')`) and is not rebuilt automatically. `*.gpkg`
is gitignored, so the file is not in the repository.

## Used by

- `figures/fig2-SST_T2m_TRENDS/plot_SST_T2m_TRENDS.py` (t2m regions, map overlay)
- `figures/figS_T2M_TREND_PERIODS/plot_S_T2M_TREND_PERIODS.py` (`region_polygons`)
- `figures/fig5-ERA_TREND_SIG/plot_ERA_TREND_SIG.py` (`land` polygon, pixels selected by cell centre)
