# Fig 13 — Biodiversity

Recreates `examples/new_plot.png` from the real data. `plot_biodiversity_transects.py`
is driven entirely by `config.yaml`.

**Panels (a, b)** — annual commercial landings 2012–2024 for the Narsaq and Qaqortoq
districts, from the Greenland Statistics table in
`data/fish_catch/FIX012_20241112-130447.csv` (monthly × vessel-type rows summed to
annual district totals, `-` treated as missing). Atlantic cod, Greenland halibut and
lumpfish get their own line; the remaining twelve species are pooled into
"Other species". The processing follows `examples/explore.R`.

**Panels (c, d)** — eDNA community composition along the two GreenFjord 2023 transects,
over the BedMachine v6 long-section of each fjord. Every station carries a two-row
flag: the upper bar is the MiFish (12S) fish community, the lower bar the EukAtara
(18S) plankton community, both as 100 % stacked bars of read counts. The grouping,
the Atlantic-cod sequence correction and the exclusion of station E follow
`examples/edna_plot.R`. Fjord **#54** is the glacial fjord (~123 km, stations B/D/K)
and **#56** the land fjord (~78 km, stations Z/W/V).

## Tuning the layout

`layout` in `config.yaml` holds every figure-fraction position: `layout.landings` and
`layout.transects` are the top/bottom of the two subplot rows (change these to open or
close the vertical gap between them), `layout.shared` the left/right margins and the
gap between the left and right subplot, and `layout.legends` / `layout.landings_legend`
the legend anchors. Bar thickness is `transects.flags.row_height_m`, with
`row_gap_m` between the fish and plankton bars; if you make the bars much thicker,
check the deep flags still clear the seabed and nudge `transects.flags.placement`.

## Choices worth knowing about

* **`examples/new_plot.png` is a mock-up.** Its landings curves are invented and its
  legend says "Illustrative bathymetry". This script keeps the layout but plots the
  real numbers, so both panels look different from the mock-up.
* **Bathymetry is the thalweg, not the cross-fjord median.** `scripts/get_bathymetry.py`
  defaults to `agg_method="median"`, which averages in the fjord walls: the section
  comes out rough and 150–250 m too shallow, putting the deep casts (355–630 m) inside
  the rock. `transects.bathymetry.agg_method: min` takes the deepest BedMachine cell in
  each cross-fjord polygon instead, which is both smoother and consistent with the
  shipboard seafloor depths recorded in the eDNA metadata. Sections are cached to
  `data/bathymetry_min_fjord_{54,56}.nc`; delete them after changing `agg_method`.
* **Station distances are measured on the centreline**, not taken from the hard-coded
  values in `examples/edna_plot.R`, so the dots always land on the section. They come
  out ~4–5 km larger than the R values (32/60/98 km vs 27/57/92 km for B/D/K, and
  11.5/34.5/62 km vs 7/30/58 km for Z/W/V) because the centreline starts at the head of
  the catchment rather than at the present-day terminus. Set
  `transects.distance_from_centerline: false` to switch back.
* **"Other" is large in most fish bars.** 333 k MiFish reads (the single biggest block
  in the dataset) are assigned only to the genus *Gadus* at 100 % identity, which 12S
  cannot split between Atlantic cod (*G. morhua*) and Greenland cod (*G. ogac*). Calling
  them Atlantic cod would be an identification decision, so they stay in "Other" and
  Atlantic cod appears only at station Z_2m. Add `Gadus: Atlantic cod` to
  `edna.fish_groups` in the config to make the other call — this is the one number in
  the figure that would change a lot.
* **A dashed empty bar** means no reads for that assay at that station. Only
  `GF23_K_2m` is affected (no fish reads).
* `data/fish_catch/pxapi-api_table_BEXSTM4.PX.json` is a saved Greenland Statistics
  *query* for population by locality, not data, and is not used.

## Run

```bash
MPLCONFIGDIR="$TMPDIR/mpl" uv run --project .. python plot_biodiversity_transects.py
```

Output is `fig13-biodiversity.png`. Pass an alternate config as the first argument to
override `config.yaml`. The first run extracts both bathymetry sections from the full
BedMachine GeoTIFF (~30 s); later runs read the netCDF cache. The `uv` cache may be
sandbox-blocked; disable the sandbox if the run fails to open it.
