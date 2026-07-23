# GreenFjord overview-figures

Scripts and data for the figures in the GreenFjord overview paper. Each `figN-*`
folder is self-contained: an entry-point `plot_*.py` / `make_*.py` script, its input
data under `data/`, exploratory/superseded material under `examples/`, imported
helpers under `scripts/`, and a per-figure `README.md` documenting the figure and its
data sources. Run any figure with the shared project environment, e.g.:

```bash
MPLCONFIGDIR="$TMPDIR/mpl" uv run --project . python figN-.../plot_*.py
```

## Data sources & citations

Consolidated provenance for every input dataset, per figure. Each figure's own
`README.md` has the fuller description; this table is the citation summary. Entries
marked **⚠ confirm** could not be resolved from the files, code, or repo — verify
with the data provider before publishing.

| Figure | Product | Citation |
|--------|---------|----------|
| **Fig 2** — SST & 2 m air-temperature trends | Sea-surface temperature (DMI SST/sea-ice product, var `analysed_st`, via `ocean.get_sst_ice_dmi()`) | ⚠ confirm — DMI (Danish Meteorological Institute) GHRSST-style combined sea/ice-surface-temperature L4 product; exact product/version not recorded |
| | 2 m air temperature (ERA5 `t2m`) | Hersbach, H., et al. (2020), *The ERA5 global reanalysis*, Q. J. R. Meteorol. Soc., 146, 1999–2049, doi:10.1002/qj.3803 (C3S/ECMWF) |
| | Regional mask (bathymetry) | GEBCO Bathymetric Compilation Group — GEBCO gridded bathymetry, https://www.gebco.net/ |
| | Glacier/fjord flux table (`fluxes_overviewpaper_tabulated.csv`) | ⚠ confirm — GreenFjord overview-paper tabulation; underlying references not recorded |
| **Fig 3** — sea-ice cover duration anomaly | Sea-ice fraction — CMEMS/Met Office OSTIA reprocessed L4 (`METOFFICE-GLO-SST-L4-REP-OBS-SST`; `SST_GLO_SST_L4_REP_OBSERVATIONS_010_011`) | Good, S., et al. (2020), *The Current Configuration of the OSTIA System…*, Remote Sensing, 12, 720, doi:10.3390/rs12040720; E.U. Copernicus Marine Service (distributor) |
| **Fig 4** — sea-ice & chlorophyll phenology | Chlorophyll bloom phenology (OC-CCI v6.0 ocean colour, 4 km) | Nicholson, S., Ryan-Keogh, T., Thomalla, S., Chang, N., & Smith, M. (2023), *Global Phytoplankton Phenological Indices – 4 km resolution* (v1.0) [Dataset], Zenodo, doi:10.5281/zenodo.8402932 (CC-BY-4.0) |
| | Sea-ice concentration (constituent products) | OSI SAF, ESA CCI, CMEMS Baltic, and SMHI sea-ice concentration products (per the `source` attribute) — cite each product per its own guidance |
| **Fig 5** — ERA5 significant-trend pixel fraction | All variables (2 m temp, dewpoint, cloud cover/base, wind, MSL, precip, `sst`, `ptype`, …) — ERA5 single levels | Hersbach, H., et al. (2020), *The ERA5 global reanalysis*, Q. J. R. Meteorol. Soc., 146, 1999–2049, doi:10.1002/qj.3803 (C3S/ECMWF). ERA5 `sst` is a prescribed boundary field from HadISST2 / OSTIA. Trend estimator & significance test **⚠ confirm** (not recorded) |
| **Fig 6** — glacier retreat | False-colour scenes for front tracing (1973–2024) — Landsat Collection-2 Level-1 (`landsat-c2-l1`) | U.S. Geological Survey / NASA, Landsat Collection 2 (via Microsoft Planetary Computer) |
| | True-colour basemap (Aug 2024) — Sentinel-2 L2A (`sentinel-2-l2a`) | Copernicus Sentinel-2 data, ESA (via Microsoft Planetary Computer) |
| | Panel-(a) map tiles | Esri World Imagery (Esri, Maxar, Earthstar Geographics, GIS user community) |
| | Glacier-front outlines, retreat & area tables | GreenFjord glacier-tracing products (this study — traced from the imagery above) |
| | Little Ice Age extent (`LIAextenthistorical.gpkg`) | ⚠ confirm — origin not recorded in file metadata |
| **Fig 7 & 8** — aerosol atmospheric case study | Narsaq 2023 particle number, PM10 & ion composition | This study (Fidas Frog optical particle sizer + PM10 filter analysis) |
| | Particle number concentrations (Zeppelin, Villum, Mace Head, Jungfraujoch) | Schmale, J., et al. (2017), *Collocated observations of cloud condensation nuclei, particle size distributions, and chemical composition*, Scientific Data, 4, 170003, doi:10.1038/sdata.2017.3 |
| | Ion composition (Zeppelin, Villum, Jungfraujoch) | Schmale, J., et al. (2022), *Pan-Arctic seasonal cycles and long-term trends of aerosol properties from 10 observatories*, Atmos. Chem. Phys., 22, 3067–3096, doi:10.5194/acp-22-3067-2022 |
| | Absorbing aerosol index (GOME-2B, KNMI/EUMETSAT AC SAF, via TEMIS) | Tilstra, L. G., Tuinder, O. N. E., & Stammes, P. (2010), *GOME-2 Absorbing Aerosol Index: Statistical analysis…*, Proc. 2010 EUMETSAT Meteorological Satellite Conf. — algorithm: de Graaf, M., et al. (2005), J. Geophys. Res., 110, D010201, doi:10.1029/2004JD005178 |
| **Fig 9 & 10** — ice cover & fluxes | Sea-ice concentration & stage-of-development (`fjord_ice_regions-time_series.xlsx`) | ⚠ confirm — WMO SIGRID-3 ice-chart data, most plausibly DMI Greenland ice charts; product/provider not recorded |
| | Fjord/glacier flux table (`fluxes_overviewpaper_tabulated.csv`) | ⚠ confirm — GreenFjord overview-paper tabulation; underlying references not recorded (same table as Fig 2) |
| | Fjord region mask (`fjord_mask.nc`, UTM 24N) | GreenFjord-derived, project-internal (⚠ confirm) |
| **Fig 14** — tidal plain | Landsat imagery & tidal-flat mask — Landsat Collection-2 Level-2 surface reflectance (`landsat-c2-l2`) | U.S. Geological Survey / NASA, Landsat Collection 2 (via Microsoft Planetary Computer) |
| | Tide-gauge record (Qaqortoq; downloaded from DTU Space) | Data producer: DTU Space (National Space Institute), station Qaqortoq (PSMSL 980/045). Archival/citable version — UHSLC/Joint Archive: Caldwell, P. C., Merrifield, M. A., & Thompson, P. R. (2015), NOAA NCEI, doi:10.7289/V5V40S7W |

### Open citation gaps

The **⚠ confirm** rows above need input that isn't in the repo:

- **DMI SST product (Fig 2)** — pinned to `ocean.get_sst_ice_dmi()` in the
  `greenfjord_trends` package, which isn't installed here; the exact CMEMS/DMI
  product id is unknown until that code is available.
- **Fjord/glacier flux table (Fig 2 & 9/10)** — a manual overview-paper tabulation
  with no embedded reference.
- **Sea-ice concentration / stage-of-development (Fig 9/10)** — structurally an
  operational ice-chart product (WMO SIGRID-3); DMI is the likely provider but is
  not recorded in the file.
- **Little Ice Age extent (Fig 6)** — single extent line, no source metadata.
- **Trend/significance method (Fig 5)** — only the resulting pixel fractions are
  stored, not the estimator or test.

Everything else is resolved from the download code, dataset metadata, or the product
identifiers embedded in the scripts.
