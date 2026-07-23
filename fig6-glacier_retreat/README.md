# Fig 6 — Glacier retreat, Qalerallit / Naajat Sermiat, South Greenland

Two-panel figure of glacier-front retreat for the GreenFjord *all-longterm-trends*
analysis, centred on the Qalerallit / Naajat Sermiat glacier system (≈ 61.0 °N,
46.7 °W).

- **Panel (a) — Glacier locations.** A bar plot of the *total* measured front
  retreat distance (km, 1992 → 2024) for 18 glaciers, drawn flush above an Esri
  World Imagery satellite map of each glacier's latest outline. Bars and map
  circles share a per-glacier identity colour (`Spectral_r`, glacier 1 = purple →
  glacier 18 = red); the numbers link the two. Positive bars = retreat, the single
  negative bar (glacier 5) = a small net advance. The white box marks the extent of
  panel (b).
- **Panel (b) — Qalerallit / Naajat Sermiat glaciers.** Traced glacier-front
  outlines for every available year (1973 → 2023), coloured by year with
  `inferno_r` (light/yellow = oldest, dark = most recent) over a true-colour
  Sentinel-2 summer scene (August 2024). The dashed white line is the Little Ice
  Age maximum extent.

The figure is assembled by a single entry-point script so fonts, line widths and
styling stay consistent across both panels. The two panels' data loading is reused
from the helper scripts in `scripts/`, which can also each be run standalone.

## Run

```bash
# from this folder; contextily fetches Esri satellite tiles (needs network on
# first run — tiles are then cached by contextily)
uv run --project .. python plot_glacier_retreat.py
```

Writes `fig6-glacier_retreat.png` (200 dpi) to this folder. The Sentinel-2 basemap
for panel (b) is read from the cached GeoTIFF in `data/glacier_i16n6104w4669/`; if
that file is deleted it is re-downloaded from the Microsoft Planetary Computer
(needs network **and** the extra `scikit-image` package, see Dependencies).

## Layout

```
.
├── plot_glacier_retreat.py            # entry point — builds the combined 2-panel figure
├── fig6-glacier_retreat.png           # final figure
├── LOG.md                             # running work log for the retreat-map design
├── scripts/                           # helper modules imported by the entry point
│   ├── make_glacier_fronts.py         #   panel (b): year-coloured fronts + Sentinel-2
│   └── make_glacier_retreat_map.py    #   panel (a): retreat bar plot + outline map
├── data/                              # all input datasets (see table below)
│   ├── glacier_outline-rectangles.gpkg
│   ├── glacier_retreat.csv
│   ├── glacier_area_cover.csv
│   ├── LIAextenthistorical.gpkg
│   └── glacier_i16n6104w4669/         # single-glacier data for panel (b)
└── examples/                          # exploratory / superseded, not the final figure
    ├── 4_qalerallit_glacier.ipynb     #   original notebook (needs external `src` pkg)
    ├── glacier-fronts.png             #   standalone panel-(b) output
    ├── glacier_retreat-map_v2.png     #   standalone panel-(a) output
    └── glacier_retreat-map.png        #   earlier retreat-map version
```

## Data

All vector data is EPSG:32623 (UTM zone 23N) unless noted. Glacier numbering in the
figure (1–18) is a renumbering of internal source ids; internal id `16`
(`i16n6104w4669`) is the Qalerallit / Naajat Sermiat glacier shown in panel (b).

### Regional — panel (a)

| File | Contents | Units / grid |
|------|----------|--------------|
| `data/glacier_outline-rectangles.gpkg` | 309 near-rectangular glacier outlines, ids 0–18, one per glacier per year | polygons, EPSG:32623 |
| `data/glacier_retreat.csv` | Cumulative front retreat per glacier per year (`glacier_00`…`glacier_18`), 1992 baseline; total retreat = last − first valid | km, 1992–2024 |
| `data/glacier_area_cover.csv` | Glacier area per year, one column per id (0–17) | km², 1992–2024 (not read by the current script; retained from earlier area-based versions) |

### Single-glacier — panel (b), `data/glacier_i16n6104w4669/`

| File | Contents | Used by figure |
|------|----------|:---:|
| `…-landsat_l1-1973_1985-handdrawn_v2.{shp,shx,dbf,prj,cpg,qix}` | Hand-drawn front polygons for 1973, 1981, 1985 | ✅ |
| `…_poly-manually_adjusted.gpkg` | Traced + manually adjusted front polygons, 1992–2024 | ✅ |
| `…_sentinel2-truecolor-2024-08.tif` | Cached true-colour Sentinel-2 median scene (Aug 2024), the panel-(b) backdrop | ✅ |
| `…-landsat_l1-1973_1985-handdrawn.gpkg` | Earlier (v1) hand-drawn version | — |
| `…_poly.gpkg` | Un-adjusted traced polygons (pre manual QC) | — |
| `…_water.gpkg` | Fjord/water mask (land- vs sea-terminating split in the notebook) | — |
| `…_data.nc` | Source raster cube (bands r/g/swir22/nir, 1992–2024) + clusters/features/masks for the automated tracing (glacier_id=16, centre 61.04 °N, 46.69 °W) | — |
| `…_data_elev.nc` | Companion elevation cube | — |
| `…_figures.pdf` | Diagnostic figures from the tracing pipeline | — |
| `rasters/` | 27 per-year false-colour scenes used to trace the fronts (Landsat C2-L1 1973/1981/1985, then annual 1992–2024; `.aux.xml` are GDAL statistics sidecars) | — |
| `LIAextenthistorical.gpkg` (in `data/`) | Little Ice Age maximum-extent line (single polygon, EPSG:4326) | ✅ |

## Sources (for citation)

- **Satellite imagery** — the false-colour scenes used to trace the fronts (1973,
  1981, 1985 and annual 1992–2024) are **Landsat Collection-2 Level-1**
  (`landsat-c2-l1`), retrieved from the **Microsoft Planetary Computer** via
  `data.get_landsat` (see `examples/4_qalerallit_glacier.ipynb`); cite the
  **USGS/NASA Landsat** program. The panel-(b) true-colour backdrop is a single
  **Sentinel-2 L2A** median scene (August 2024; Copernicus/ESA, `sentinel-2-l2a` on
  the Planetary Computer), fetched by `scripts/make_glacier_fronts.py`. The
  panel-(a) map tiles are **Esri World Imagery** (contextily provider).
  (Sentinel-2 only exists from 2015, so the pre-2015 annual scenes are Landsat, not
  Sentinel-2.)
- **Glacier-front outlines & retreat/area tables** (`glacier_outline-rectangles.gpkg`,
  `glacier_retreat.csv`, `glacier_area_cover.csv`, and the per-glacier vectors) are
  GreenFjord glacier-tracing products: fronts were traced from the imagery above
  (automated pipeline + manual adjustment / hand-drawing for the oldest years). The
  data files carry only minimal attributes (glacier id, centre coordinates); **no
  formal product name, DOI, or author is recorded in the metadata** — confirm the
  citation with the data provider before publication.
- **Little Ice Age extent** (`LIAextenthistorical.gpkg`) — a single extent line; its
  origin is **not recorded in the file metadata** — confirm the source with the data
  provider before citing.

## Dependencies

`contextily` (Esri basemap tiles) is required by this figure and was added to the
repo `pyproject.toml` during the 2026-07 reorganization. Re-downloading the
Sentinel-2 basemap from scratch (only if the cached GeoTIFF is deleted) additionally
needs `scikit-image` (imported by `scripts/make_glacier_fronts._download_sentinel2`),
which is **not** currently in `pyproject.toml` — add it if a cold refetch is needed.

Part of the GreenFjord overview-figures set.
