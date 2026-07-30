# Fig S — Sensitivity of seasonal 2 m air-temperature trends to the trend period

Air-temperature counterpart to [`figS-sst_seasonal_trends`](../figS-sst_seasonal_trends/),
using the same layout and method. One panel per season (**a** DJF, **b** MAM,
**c** JJA, **d** SON); within a panel each cell is one trend period, with the
**start year** on the rows and the **end year** on the columns. Cell colour is
the Theil–Sen slope of ERA5 2 m air temperature (°C dec⁻¹) and a dot marks
periods where the Mann–Kendall test is significant (p < 0.05). The lower-left of
each panel is empty because periods shorter than 15 years are not evaluated.

Run from the repository root:

```
MPLCONFIGDIR="$TMPDIR/mpl" .venv/bin/python figS-t2m_seasonal_trends/plot_t2m_seasonal_trends.py
```

Outputs `figS-t2m_seasonal_trends.png` (300 dpi) and `.pdf` to this folder.

## Method

All analysis steps come from `greenfjord.analysis`:

1. Daily ERA5 `t2m` is read from `../fig2-sst_t2m_trends/data/era5-daily-greenfjord.zarr`
   (which already spans exactly 1982–2021) and converted from K to °C.
2. The spatial mean is taken over the **GreenFjord land polygon** (`land`) of
   `../fig2-sst_t2m_trends/data/era5-land-ocean-ice.gpkg`, weighted by
   cos(latitude). Set `SUBSET` to `"ocean"` or `"ice"` for the other two subsets
   used in Fig 2.
3. `seasonal_trends.preprocess_data` resamples to seasonal means and reshapes
   the time axis to `year × season` (DJF spans Dec of the labelled year plus
   Jan–Feb of the next).
4. `seasonal_trends.calc_trend_start_sensitivity` runs
   `trends.theilsen_mannkendall_tfpw` over every start/end-year combination with
   `min_years=15` and `step_size=2`, giving start years 1982–2006 and end years
   1997–2021.

The resulting cube (`start_year × end_year × season × parameter`) is cached to
`data/t2m-seasonal_trend_sensitivity.nc`; **delete that file to recompute**
(a few seconds). Only the `slope` and `pvalue` parameters are plotted.

## Trends and significance (methods text for the paper)

Identical to [`figS-sst_seasonal_trends`](../figS-sst_seasonal_trends/README.md#trends-and-significance-methods-text-for-the-paper),
which carries the full description and the reference list. In brief, and for
every cell independently (n = 16 years for the shortest period, n = 40 for
1982–2021; implementation `greenfjord.analysis.trends.theilsen_mannkendall_tfpw`):

**Slope (cell colour).** Theil–Sen (Sen, 1968) slope — the median of the slopes
of all pairwise point combinations — from `scipy.stats.theilslopes` on the
original, unfiltered seasonal series, displayed as °C dec⁻¹. Rank-based, so
single extreme years do not dominate short windows. The 95 % Theil–Sen bounds are
stored in the cached cube but not drawn.

**Significance (dots).** Mann–Kendall test (Mann, 1945; Kendall, 1975) as the
p-value of Kendall's τ against year (`scipy.stats.kendalltau`, `variant="c"`),
applied to a **trend-free prewhitened** series (Yue et al., 2002) to account for
year-to-year autocorrelation: estimate the Theil–Sen slope, detrend, estimate the
lag-1 autocorrelation ρ₁ from the residuals, prewhiten the residuals
(`y'' = y'ₜ − ρ₁·y'ₜ₋₁`), add the original trend back, then test. A dot marks
p < 0.05. Prewhitening is applied only where ρ₁ exceeds the Anderson (1942)
one-sided 5 % bound (0.23 at n = 40, 0.34 at n = 16); the slope is always taken
from the original series.

**Effect in this figure.** Air temperature has weaker year-to-year memory than
SST, so the bound is cleared in DJF only: prewhitening changed the p-value in 14
of 91 cells in panel **a** and left MAM, JJA and SON untouched. Significant cells
went from 50 → 55 in DJF; MAM (41), JJA (62) and SON (18) are unchanged. Slopes
are unaffected by construction.

**Caveats.** Multiple testing is not corrected — 91 overlapping periods per panel
and four panels sharing years, so the contiguous *block* structure of
significance is the interpretable signal rather than any individual dot. TFPW is
a power-recovery method rather than a conservative one and is known to inflate
type I error for short, strongly autocorrelated series (Bayazit & Önöz, 2007;
Serinaldi & Kilsby, 2016) — consistent with DJF gaining dots here. The Hamed &
Rao (1998) variance correction is the conservative alternative.

## Reading the figure

- Winter dominates the shared colour scale (DJF reaches ≈ 3.7 °C dec⁻¹, roughly
  three times the summer slopes), which leaves JJA and SON pale. Set `VMAX` in
  the script (e.g. `VMAX = 2.0`) to clip the scale and bring out the weaker
  seasons; the colour bar then grows arrows to show the clipping.
- JJA and SON are the *most* robust seasons despite the pale colours: nearly
  every period is significant, whereas DJF flips sign for start years after 2000.
- Cells share years, so neighbouring cells are **not** independent estimates —
  the figure shows the sensitivity of the trend estimate, not many independent
  trends.
- DJF 2021 rests on December 2021 alone, because the input ends 2021-12-31.

## Data

| File | Contents | Units | Notes |
|------|----------|-------|-------|
| `../fig2-sst_t2m_trends/data/era5-daily-greenfjord.zarr` | daily ERA5 single-level fields incl. `t2m` | K | shared with Fig 2; 1982–2021, 0.25° |
| `../fig2-sst_t2m_trends/data/era5-land-ocean-ice.gpkg` | land / ocean / ice polygons | — | produced by `fig2-sst_t2m_trends/examples/region_plots.ipynb`; rasterised with `xarray_raster_vector` |
| `data/t2m-seasonal_trend_sensitivity.nc` | Theil–Sen / Mann–Kendall output per start/end year and season | °C yr⁻¹ (slope) | generated by this script; safe to delete |

### Sources (for citation)

- **2 m air temperature** — ERA5 reanalysis: Hersbach et al. (2020), Copernicus
  Climate Change Service (C3S) / ECMWF.

Part of the GreenFjord overview-figures set.
