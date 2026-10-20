# GreenFjord sampling-location sheet

`greenfjord_sample_locations.csv` is a verbatim CSV export of the project's
master sampling-location Google Sheet (one row per sampling event or site).

## Contents

Row 0 holds per-column instructions for the people filling in the sheet, so the
header is on row 1 (read with `skiprows: 1`). Columns used by the figure:

| Column | Use |
|---|---|
| `Cluster` | Sampling group (Ocean, Human, Cryoshpere [sic], Atmosphere, Land, Biodiversity); selects the marker layer |
| `Type` | Sample type (e.g. `CTD`, `Water`); used to include / exclude rows |
| `Lat`, `Lon` | Location, decimal degrees (EPSG:4326) |
| `Location` | Site name; used for transect membership, exclusions and per-site averaging |
| `Station ID` | Ocean station ID; its first letter splits shelf stations between the two transects |

The remaining columns (`Group`, `Year`, `Time`, `Link to paper`, `icon`,
`text_color`, `background_color`, `Extra`) are not used.

## Source

GreenFjord project Google Sheet. It is live and unversioned, so the CSV is a
snapshot; the sheet's ID is in the `SHEET_CSV_URL` constant of the download
script. Listed as S1 in [`DATA_SOURCES.md`](../../../DATA_SOURCES.md).

## Regenerate

From the repository root (needs network access and read access to the sheet):

```bash
.venv/bin/python fig1-map_samples/data/download_sample_locations.py
```

This overwrites `greenfjord_sample_locations.csv` with the current sheet.

## Used by

Only `fig1-map_samples/plot_MAP.py` (the overview map), via `inputs.sample_locations`
in `config_MAP.yaml`.
