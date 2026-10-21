# GreenFjord overview-figures

Scripts and data for the figures in the GreenFjord overview paper.

> [!TIP]
> ### ▶️ Run figures from the YAML in VS Code
> Open `figures/<folder>/config_<NAME>.yaml` and click the **▷ Run Code** button (top right). It runs the matching `plot_<NAME>.py`.
>
> **Requires** the recommended [Code Runner](https://marketplace.visualstudio.com/items?itemName=formulahendry.code-runner) extension. VS Code prompts you to install it when you open the repo (config in `.vscode/`). The `.venv` must exist first.

- `figures/` holds one folder per figure (see [FIGURE_TEMPLATE.md](FIGURE_TEMPLATE.md)): a `plot_<NAME>.py` entry point, a `config_<NAME>.yaml`, a per-figure `README.md` and the output `fig_<NAME>.png`.
- `data/` holds the shared input datasets, each with its own `README.md` and download script.
- [DATA_SOURCES.md](DATA_SOURCES.md) is the full audit of every data source (IDs S1–S32, status, citations).

Run a figure from the repo root:

```bash
MPLCONFIGDIR="$TMPDIR/mpl" .venv/bin/python figures/<folder>/plot_<NAME>.py
```

## Data sources & citations

Summary per figure; source IDs refer to the tables in [DATA_SOURCES.md](DATA_SOURCES.md).
Status: ✅ identified · 🟡 partly identified (version, DOI or provider detail missing) · ❌ not identified.

| Figure | Data source (ID) | Citation / provider | Status |
|---|---|---|---|
| **Fig 1** `fig1-MAP` | Sampling-location sheet (S1) | GreenFjord project (unversioned Google Sheet) | 🟡 |
| | G250 topographic basemap (S2) | GEUS, Greenland G250 Topographic Map | ✅ |
| | Natural Earth 10 m (S3) | naturalearthdata.com | ✅ |
| | Municipal borders (S31) | geoBoundaries, Runfola et al. 2020, doi:10.1371/journal.pone.0231866 | ✅ |
| **Fig 2** `fig2-SST_T2m_TRENDS` | DMI SST L4 `analysed_st` (S4) | DMI via CMEMS, doi:10.48670/moi-00123; Nielsen-Englyst et al. 2023, doi:10.1016/j.rse.2022.113331 | ✅ |
| | ERA5 t2m (S6) | Hersbach et al. 2020, doi:10.1002/qj.3803 | 🟡 |
| | DMI Narsarsuaq station (S32) | DMI Open Data metObs API (CC BY 4.0) | 🟡 |
| | GEBCO 2023 + distance-to-coast region mask (S7) | GEBCO Compilation Group 2023, doi:10.5285/f98b053b-0cbc-6c23-e053-6c86abc0af7b; NASA OBPG distance to coast | ✅ / 🟡 |
| | Land/ocean/ice polygons (S8) | GreenFjord-derived (internal) | ✅ |
| **Fig 3** `fig3-DRIFT_ICE_ANOMS` | DMI SST/sea-ice L4 `sea_ice_fraction` (S4) | as Fig 2 | ✅ |
| **Fig 4** `fig4-ICE_CHL_SEAS_DURATION` | Sea-ice duration trend from DMI L4 (S4) | as Fig 2 | ✅ |
| | Chlorophyll bloom phenology, OC-CCI v6.0 (S9) | Nicholson et al. 2023, doi:10.5281/zenodo.8402932; ESSD 17, 1959–1975, doi:10.5194/essd-17-1959-2025 | ✅ |
| **Fig 5** `fig5-ERA_TREND_SIG` | ERA5 single levels, monthly means (S6) | Hersbach et al. 2020, doi:10.1002/qj.3803 | 🟡 |
| | Land polygon (S8) | GreenFjord-derived (internal) | ✅ |
| **Fig 6** `fig6_GLACIER_RETREAT` | Landsat C2 L1 (S10) | USGS/NASA via Microsoft Planetary Computer | 🟡 |
| | Sentinel-2 L2A, Aug 2024 (S12) | Copernicus Sentinel-2 data, ESA | ✅ |
| | Esri World Imagery tiles (S13) | Esri, Maxar, Earthstar Geographics | ✅ |
| | Glacier-front outlines and tables (S14) | GreenFjord cryo cluster, [glacier-retreat](https://gitlab.com/greenfjord/cryo-cluster/glacier-retreat) | 🟡 |
| | Little Ice Age extent (S15) | GreenFjord project (internal) | ✅ |
| **Fig 7** `fig7_AEROSOL_CONC` | Narsaq 2023 aerosol campaign (S16) | This study (Fidas Frog, PM10, ion composition) | ✅ |
| | Particle number, Zeppelin/Villum/Mace Head/Jungfraujoch (S17) | Schmale et al. 2017, doi:10.1038/sdata.2017.3 | ✅ |
| | Ion composition (S18) | Schmale et al. 2022, doi:10.5194/acp-22-3067-2022 | ✅ |
| **Fig 8** `fig8_AEROSOL_ANOM` | GOME-2B Absorbing Aerosol Index (S19) | KNMI via TEMIS; Tilstra et al. 2010; de Graaf et al. 2005, doi:10.1029/2004JD005178 | ✅ |
| | Narsaq PM10 (S16) | This study | ✅ |
| **Fig 9** `fig9_FJORD_ICE_BARS` | Fjord ice concentration / stage of development (S20) | GreenFjord cryo cluster, [fjord-ice-cover](https://gitlab.com/greenfjord/cryo-cluster/fjord-ice-cover) | 🟡 |
| | Fjord/glacier flux table (S21) | GreenFjord project (internal), Andreas Vieli | ✅ |
| **Fig 10** `fig10_FJORD_ICE_TIMESERIES` | Fjord ice concentration / stage of development (S20) | as Fig 9 | 🟡 |
| **Fig 11** `fig11_CTD_SECTIONS` | GF24 CTD + nutrient workbook (S27) | GreenFjord ocean cluster (internal) | ✅ |
| | BedMachine Greenland v6 (S25) | Morlighem et al. 2025, doi:10.5067/6B6B225B8V2D | ✅ |
| | Fjord centreline geometry (S26) | Separate `greenland-fjord-properties` repo | ✅ |
| **Fig 12** `fig12_FISH` | Fish landings, FIX012 (S22) | Statistics Greenland StatBank, accessed 2024-11-12 | ✅ |
| | eDNA MiFish 12S and EukAtara 18S (S23, S24) | GreenFjord project (internal) | 🟡 |
| | BedMachine v6 (S25), fjord geometry (S26) | as Fig 11 | ✅ |
| **Fig 13** `fig13_SEDIMENT_DELIVERY` | Landsat C2 L2 SR (S11) | USGS/NASA via Microsoft Planetary Computer | ✅ |
| | Qaqortoq tide gauge (S28) | DTU Space; Caldwell et al. 2015, doi:10.7289/V5V40S7W | 🟡 |
| | Turbidity and ablatometer loggers (S29) | GreenFjord field sensors (Ian Delaney, 2023) | 🟡 |
| | Jespersen Bræ discharge (S30) | Mankoff et al. 2020, doi:10.5194/essd-12-2811-2020 | ✅ |
| **Fig S** `figS_SST_TREND_PERIODS` | DMI SST L4 (S4); GEBCO region mask (S7) | as Fig 2 | ✅ / 🟡 |
| **Fig S** `figS_SEAICE_PHENOL` | DMI L4 `sea_ice_fraction` (S4) | as Fig 2 | ✅ |
| **Fig S** `figS_T2M_TREND_PERIODS` | ERA5 t2m daily (S6); polygons (S8) | as Fig 2 | 🟡 / ✅ |
| **Table S** `tableS-era5_seasonal_trends` | ERA5 daily (S6); polygons (S8) | as Fig 2 (notebook unfinished) | 🟡 |

### Shared datasets in `data/`

| Folder | Content |
|---|---|
| `dmi_metobs_narsarsuaq` | DMI Narsarsuaq station observations (S32) |
| `era5_monthly_south_greenland` | ERA5 monthly means from CDS (S6) |
| `fjord_bathymetry` | BedMachine fjord sections (S25) |
| `fjord_ice_regions_monthly` | Fjord ice-chart workbook (S20) |
| `geoboundaries_grl_adm1` | Greenland municipal borders (S31) |
| `greenfjord_land_ocean_ice` | Land/ocean/ice polygons (S8) |
| `ocean_regions_mask` | GEBCO + distance-to-coast region mask (S7) |
| `sea_ice_dmioi_daily` | Daily DMI sea-ice fraction (S4) |
| `sst_dmioi_monthly` | Monthly DMI SST (S4) |

### Open citation gaps

- **Fjord ice charts (S20)**: from the `fjord-ice-cover` repo; the underlying ice-chart provider (likely DMI SIGRID-3) and a repo version/commit are not recorded.
- **Glacier fronts (S14)**: from the `glacier-retreat` repo; no version/commit recorded.
- **ERA5 (S6)**: exact CDS request for the daily zarr not recorded.
- **Internal datasets (S1, S15, S16, S21, S23, S24, S27, S29)**: no DOI yet.
