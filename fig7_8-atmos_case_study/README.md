# Fig 7 & 8 — Aerosol atmospheric case study (Narsaq, Greenland)

This folder builds two figures for the GreenFjord aerosol case study, comparing
the Narsaq (southern Greenland) 2023 campaign against established background
stations. All scripts use the shared `figure.mplstyle`.

**Fig 7 — particle number concentrations.** Number concentration of aerosol
particles (10–710 nm) for July/August at Narsaq (2023), Zeppelin (2010–2020),
Villum (2010–2017), Mace Head (2011–2012) and Jungfraujoch (2012–2014). Boxes =
interquartile range, whiskers = 10th/90th percentiles, bar = median. Overlaid
composition shows the fractional contribution of four dominant PM ions
(**Sodium** purple, **Nitrate** blue, **Sulfate** red, **Ammonium** orange) for
Narsaq (2023), Zeppelin (1993–2019), Villum (1990–2017) and Jungfraujoch
(2011–2021); Mace Head has no composition data. Two renderings are kept, both
final deliverables:

- `fig7-particle_concentrations_piecharts.png` (`plot_particle_concentrations_piecharts.py`)
  — pie charts overlaid above each box (matches the original figure; adds a small
  gap between slices).
- `fig7-particle_concentrations_stackedbars.png` (`plot_particle_concentrations_stackedbars.py`)
  — alternative two-panel view: stacked-bar composition (%) on top, log-scale
  boxplots below.

**Fig 8 — PM10 record & absorbing-aerosol-index anomaly**
(`plot_pm10_aai.py` → `fig8-pm10_aai.png`). Main plot: annually integrated GOME-2
absorbing aerosol index (AAI) anomaly for the area of Narsaq (2013–2024), one bar
per year, relative to the 2013–2024 mean. Inset: the summer-2023 Narsaq PM10 mass
concentration record (Fidas Frog, density 1.5 g cm⁻³), with the WHO 45 µg m⁻³
guideline as a dashed line and the two exceedance peaks (30 Jun, 19 Jul)
highlighted. Ion colours carry community meaning and are sampled exactly from the
original figures.

## Run

From the repo root (scripts read from `data/` and write into this folder):

```bash
uv run --project . python fig7_8-atmos_case_study/plot_particle_concentrations_piecharts.py
uv run --project . python fig7_8-atmos_case_study/plot_particle_concentrations_stackedbars.py
uv run --project . python fig7_8-atmos_case_study/plot_pm10_aai.py
```

Set `MPLCONFIGDIR="$TMPDIR/mpl"` if matplotlib complains about its cache. (The
piecharts script emits a harmless `findfont: font weight 100` warning.)

## Layout

```
.
├── plot_particle_concentrations_piecharts.py    # Fig 7 (pie-overlay version)
├── plot_particle_concentrations_stackedbars.py  # Fig 7 (stacked-bar version)
├── plot_pm10_aai.py                             # Fig 8
├── figure.mplstyle                              # shared matplotlib style
├── fig7-particle_concentrations_piecharts.png   # output — Fig 7
├── fig7-particle_concentrations_stackedbars.png # output — Fig 7 (alt)
├── fig8-pm10_aai.png                            # output — Fig 8
├── data/
│   ├── box-plots.txt                            # particle-count box statistics
│   ├── Pie-charts.txt                           # ion composition fractions
│   ├── PM10-concentrations.txt                  # Narsaq 2023 PM10 record
│   └── greenfjord_timeseries_aai_anom_gome2b_2013_2024.csv
└── examples/
    ├── aai.py                                   # downloads ESA CCI GOME-2B AAI netCDFs
    ├── boxplot-piecharts.png                    # original Fig 7 (reference recreated)
    ├── concentrations.png                       # original Fig 8 (reference recreated)
    └── plot_pm10_aai_old.py                     # superseded two-panel Fig 8 script
```

## Data

| File | Used by | Content | Units / notes |
|------|---------|---------|---------------|
| `data/box-plots.txt` | Fig 7 | Per-station particle-count percentiles (`_25`/`_50`/`_75` = Q1/median/Q3; `_10EB`/`_90EB` = whisker lengths from the box edges to the 10th/90th percentiles). Tab-separated. | number concentration, cm⁻³ |
| `data/Pie-charts.txt` | Fig 7 | Ion fractions per station column (`Na_species_PM10` = Narsaq, `Zep_species`, `Vil_species`, `JFJ_species`), rows `NA`/`NO3`/`SO4`/`NH4`. Fractions sum to ~1. Tab-separated. | dimensionless fraction |
| `data/PM10-concentrations.txt` | Fig 8 | Narsaq summer-2023 daily PM10. `mastertime_1d` is **LabVIEW time (seconds since 1904-01-01)**, the Fidas/LabVIEW epoch → first sample maps to 2023-06-21. Tab-separated. | PM10 in µg m⁻³ |
| `data/greenfjord_timeseries_aai_anom_gome2b_2013_2024.csv` | Fig 8 | Daily point estimates of the GOME-2B absorbing aerosol index anomaly for the Narsaq area, 2013-01 → 2024, summed to an annual integral per year in the script (3368 rows). | absorbing aerosol index (anomaly) |

### Sources (for citation)

- **Narsaq (2023)** — measured in this study: particle number concentrations and
  PM10 from a **Fidas Frog** optical particle sizer (assumed density 1.5 g cm⁻³);
  ion composition from PM10 filter analysis.
- **Particle number concentrations for Zeppelin, Villum, Mace Head, Jungfraujoch**
  — Schmale et al. 2017:

  > Schmale, J., Henning, S., Henzing, B., et al. (2017): *Collocated observations
  > of cloud condensation nuclei, particle size distributions, and chemical
  > composition*, Scientific Data, 4, 170003,
  > doi:[10.1038/sdata.2017.3](https://doi.org/10.1038/sdata.2017.3).
- **Ion composition (pie/stacked bars) for Zeppelin, Villum, Jungfraujoch** —
  Schmale et al. 2022 (comparison is approximate because the station time periods
  differ):

  > Schmale, J., Sharma, S., Decesari, S., et al. (2022): *Pan-Arctic seasonal
  > cycles and long-term trends of aerosol properties from 10 observatories*, Atmos.
  > Chem. Phys., 22, 3067–3096,
  > doi:[10.5194/acp-22-3067-2022](https://doi.org/10.5194/acp-22-3067-2022).
- **Absorbing aerosol index** — GOME-2B (GOME-2 on MetOp-B) Absorbing Aerosol
  Index, Level-3 daily gridded product, version **fv1.9** (file convention
  `ESACCI-AEROSOL-L3-AAI-GOME2B-1D-YYYYMMDD-fv1.9.nc`). Produced by **KNMI** (Royal
  Netherlands Meteorological Institute) under the **EUMETSAT AC SAF** and
  distributed via **TEMIS** (`www.temis.nl/airpollution/absaai/`); downloaded by
  `examples/aai.py`. The daily fields are integrated to an annual anomaly (relative
  to the 2013–2024 mean) for the Narsaq area. TEMIS's recommended citation:

  > Tilstra, L. G., Tuinder, O. N. E., and Stammes, P. (2010): *GOME-2 Absorbing
  > Aerosol Index: Statistical analysis, comparison to GOME-1 and impact of
  > instrument degradation*, Proceedings of the 2010 EUMETSAT Meteorological
  > Satellite Conference.

  Foundational algorithm reference:

  > de Graaf, M., Stammes, P., Torres, O., and Koelemeijer, R. B. A. (2005):
  > *Absorbing Aerosol Index: Sensitivity analysis, application to GOME and
  > comparison with TOMS*, J. Geophys. Res., 110, D010201,
  > doi:[10.1029/2004JD005178](https://doi.org/10.1029/2004JD005178).

Part of the GreenFjord overview-figures set.
