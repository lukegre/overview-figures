# Fig S — Sensitivity of seasonal SST trends to the trend period

Supplementary figure showing how much the **seasonal sea-surface temperature
(SST) trend** in the GreenFjord ocean domain depends on the period over which it
is fitted. One panel per season (**a** DJF, **b** MAM, **c** JJA, **d** SON);
within a panel each cell is one trend period, with the **start year** on the
rows and the **end year** on the columns. Cell colour is the Theil–Sen slope
(°C dec⁻¹) and a dot marks periods where the Mann–Kendall test is significant
(p < 0.05). The lower-left of each panel is empty because periods shorter than
15 years are not evaluated.

The layout reproduces `examples/Screenshot 2026-07-29 at 15.28.42.png`, which
came from `examples/sst.ipynb` in an earlier version of the project.

Run from the repository root:

```
MPLCONFIGDIR="$TMPDIR/mpl" .venv/bin/python figS-sst_seasonal_trends/plot_sst_seasonal_trends.py
```

Outputs `figS-sst_seasonal_trends.png` (300 dpi) and `.pdf` to this folder.

## Method

All analysis steps come from `greenfjord.analysis`:

1. Monthly DMI SST is read from `../fig2-sst_t2m_trends/data/cmems_obs_si_...monthly.zarr`
   and clipped to 1982–2021 (`config.TIME_START` / `TIME_END`).
2. Ice-covered pixels are dropped (`sea_ice_frac > 0`), following
   `examples/sst.ipynb`, and Kelvin is converted to °C.
3. The domain mean is taken over ocean regions 1–4 of
   `../fig2-sst_t2m_trends/data/regions_mask.nc` (Oceanic, Southwest, Central
   western, South Eastern — i.e. everything except the unused near-shore band),
   weighted by cos(latitude).
4. `seasonal_trends.preprocess_data` resamples to seasonal means and reshapes
   the time axis to `year × season` (DJF spans Dec of the labelled year plus
   Jan–Feb of the next).
5. `seasonal_trends.calc_trend_start_sensitivity` runs
   `trends.theilsen_mannkendall_tfpw` over every start/end-year combination with
   `min_years=15` and `step_size=2`, giving start years 1982–2006 and end years
   1997–2021.

The resulting cube (`start_year × end_year × season × parameter`) is cached to
`data/sst-seasonal_trend_sensitivity.nc`; **delete that file to recompute**
(≈1 minute). Only the `slope` and `pvalue` parameters are plotted.

Two deliberate differences from the prototype screenshot:

- slopes are shown in **°C per decade** rather than kelvin per year, matching
  `fig2-sst_t2m_trends`;
- the panels are lettered **a–d** and the colour scale is shared and symmetric
  about zero across all four seasons.

## Trends and significance (methods text for the paper)

Every cell of every panel is estimated independently over its own period, so the
sample size ranges from n = 16 years (shortest period) to n = 40 (1982–2021).
Implementation: `greenfjord.analysis.trends.theilsen_mannkendall_tfpw`.

**Slope (cell colour).** Trend magnitudes are Theil–Sen (Sen, 1968) slope
estimates — the median of the slopes of all pairwise combinations of points —
computed with `scipy.stats.theilslopes` on the original, unfiltered seasonal
series. The estimator is rank-based and therefore insensitive to individual
extreme years, which matters over 16-year windows. Slopes are multiplied by ten
for display as °C dec⁻¹. The 95 % Theil–Sen confidence bounds are computed and
stored in the cached cube (`slope_upper_bound`, `slope_lower_bound`) but are not
drawn.

**Significance (dots).** Monotonic trends are tested with the Mann–Kendall test
(Mann, 1945; Kendall, 1975), evaluated as the p-value of Kendall's τ between
value and year (`scipy.stats.kendalltau`, `variant="c"`). To account for
year-to-year autocorrelation in the seasonal means, the test is applied to a
**trend-free prewhitened** series following Yue et al. (2002):

1. estimate the Theil–Sen slope *b* on the original series;
2. detrend, `y' = y − b·t`, so the AR coefficient is not inflated by the trend;
3. estimate the lag-1 autocorrelation ρ₁ from the residuals;
4. prewhiten the residuals, `y'' = y'ₜ − ρ₁·y'ₜ₋₁`, and add the original trend
   back, `y''' = y'' + b·t`;
5. run the ordinary Mann–Kendall test on `y'''`; a dot marks p < 0.05.

Prewhitening is applied only where ρ₁ exceeds the Anderson (1942) one-sided 5 %
bound, `(−1 + 1.645·√(n−2)) / (n−1)` — 0.23 at n = 40, 0.34 at n = 16 —
otherwise the unfiltered series is tested, on the grounds that prewhitening with
a ρ₁ that is mostly estimation noise costs power for no gain. The AR(1) filter
consumes the first value, so a prewhitened 40-year period is tested on 39 points.
The slope is always reported from the original series, as Yue et al. recommend,
because prewhitening alters the residual variance.

**Effect in this figure.** ρ₁ of the detrended series clears the bound only in
MAM (0.37) and DJF (0.23 for the full period), so JJA and SON are tested
unfiltered throughout. Prewhitening changed the p-value in 24 of 91 cells in each
of those two panels and left the other two panels untouched. The count of
significant cells went from 60 → 57 (MAM) and 38 → 42 (DJF); JJA (64) and SON
(56) are unchanged. Slopes are unaffected by construction.

## Caveats

- **Multiple testing is not corrected.** Each panel contains 91 overlapping
  periods and the four panels share the same years, so a fraction of dots is
  expected by chance alone. The interpretable signal is the contiguous *block*
  structure of significance, not any individual cell.
- Cells share years, so neighbouring cells are **not** independent estimates —
  the figure shows sensitivity of the trend estimate, not many independent
  trends.
- **TFPW is a power-recovery method, not a conservative one.** It is known to
  inflate type I error for short and strongly autocorrelated series (Bayazit &
  Önöz, 2007; Serinaldi & Kilsby, 2016), and here it produced *more* significant
  DJF cells rather than fewer. If a conservative test is wanted instead, the
  Hamed & Rao (1998) variance correction inflates the Mann–Kendall variance by
  n/n_eff while leaving the data and slope untouched.
- ρ₁ estimated from ≤ 40 points has a standard error of roughly 1/√n ≈ 0.16, so
  the correction is itself uncertain, and the threshold decision in step 5 above
  can flip for cells sitting near the bound.
- DJF 2021 rests on December 2021 alone, because the input is clipped at
  2021-12-31; the prototype notebook had the same edge effect.

### References

- Anderson, R. L. (1942) Distribution of the serial correlation coefficient.
  *Ann. Math. Stat.* 13, 1–13.
- Bayazit, M. & Önöz, B. (2007) To prewhiten or not to prewhiten in trend
  analysis? *Hydrol. Sci. J.* 52, 611–624.
- Hamed, K. H. & Rao, A. R. (1998) A modified Mann-Kendall trend test for
  autocorrelated data. *J. Hydrol.* 204, 182–196.
- Kendall, M. G. (1975) *Rank Correlation Methods*. Charles Griffin, London.
- Mann, H. B. (1945) Nonparametric tests against trend. *Econometrica* 13,
  245–259.
- Sen, P. K. (1968) Estimates of the regression coefficient based on Kendall's
  tau. *J. Am. Stat. Assoc.* 63, 1379–1389.
- Serinaldi, F. & Kilsby, C. G. (2016) The importance of prewhitening in change
  point analysis under persistence. *Stoch. Environ. Res. Risk Assess.* 30,
  763–777.
- Yue, S., Pilon, P., Phinney, B. & Cavadias, G. (2002) The influence of
  autocorrelation on the ability to detect trend in hydrological series.
  *Hydrol. Process.* 16, 1807–1829.

## Data

| File | Contents | Units | Notes |
|------|----------|-------|-------|
| `../fig2-sst_t2m_trends/data/cmems_obs_si_arc_phy_my_L4-DMIOI_P1D-m_...monthly.zarr` | monthly DMI SST (`analysed_st`), analysis error, sea-ice fraction | K, fraction | shared with Fig 2; from CMEMS `cmems_obs_si_arc_phy_my_L4-DMIOI_P1D-m` |
| `../fig2-sst_t2m_trends/data/regions_mask.nc` | ocean regional mask | class label | cache of `greenfjord.data.other.get_ocean_regions()` (GEBCO bathymetry + distance to coast) |
| `data/sst-seasonal_trend_sensitivity.nc` | Theil–Sen / Mann–Kendall output per start/end year and season | °C yr⁻¹ (slope) | generated by this script; safe to delete |

### Sources (for citation)

- **SST** — DMI Arctic Sea and Ice Surface Temperature L4 product, accessed via
  Copernicus Marine Service (`cmems_obs_si_arc_phy_my_L4-DMIOI_P1D-m`).
- **Regional mask** — GEBCO 2023 gridded bathymetry
  (<https://www.gebco.net/data_and_products/gridded_bathymetry_data/>) combined
  with distance-to-coast.

Part of the GreenFjord overview-figures set.
