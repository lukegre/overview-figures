# fjord_ice_regions_monthly

Monthly sea-ice concentration for the Inner / Mid / Outer zones of three
southern Greenland fjord systems, plus a coastal-ocean reference series.

## Contents

`fjord_ice_regions_monthly.xlsx`:

| Sheet | Meaning |
|---|---|
| `seaice_conc` | monthly sea-ice concentration (%), 2014-10 to 2024-10 (121 months). Two header rows: fjord (`Sermelik - Ikersuaq`, `Tunuliarfik`, `Igalikup Kangerlua`, `Oceanic`) and zone (`Inner ` with a trailing space, `Mid`, `Outer`, `Coastal ocean`). First column is `time`. **The only sheet used by the figures.** |
| `region_area_num_pixels` | area and pixel count of each region (unused) |
| `seaice_area_weighted` | area-weighted sea-ice area per region (unused) |
| `sod_count` | stage-of-development counts per region (unused) |

The header spellings (`Sermelik`, `Tunuliarfik`) are those in the workbook, so
figure configs must use them as-is.

## Source

The workbook is a hand-delivered file; there is no download script. The ice
fields follow WMO SIGRID-3 nomenclature, which points to operational ice
charts (probably DMI), but the provider is not recorded in the file. See
source S20 in [`DATA_SOURCES.md`](../../DATA_SOURCES.md), which flags it as
unconfirmed. Confirm the provider before citing.

## Regenerate

Not reproducible from this repository. Replace the file with a new delivery
of the same layout.

## Used by

- `figures/fig9_FJORD_ICE_BARS/plot_FJORD_ICE_BARS.py`
- `figures/fig10_FJORD_ICE_TIMESERIES/plot_FJORD_ICE_TIMESERIES.py`
