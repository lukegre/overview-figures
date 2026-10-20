"""Sensitivity of annual SST trends to the chosen trend period (Fig. S).

Reproduces the layout of ``examples/Screenshot 2026-07-29 at 15.28.42.png``,
which was originally produced by ``examples/sst.ipynb``: a heat map where
each cell is the Theil-Sen slope of annually averaged sea-surface temperature
(SST) for a trend period running from a given *start year* (top axis) to a
given *end year* (left axis). Cells are annotated with their slope when the
Mann-Kendall test finds the trend significant (p < ``alpha``).

Significance is tested on the original series (``prewhitening: off``) or on a
trend-free prewhitened series (Yue et al., 2002, Hydrol. Process. 16, 1807) to
account for lag-1 autocorrelation: ``auto`` prewhitens only when the lag-1
autocorrelation is significant at ``alpha``, ``force`` always does. The slope
is always the Theil-Sen slope of the original series.

Data flow (all of the analysis functions live in
``greenfjord.analysis.seasonal_trends``):

    monthly DMI SST (``data/sst_dmioi_monthly``)
      -> mask ice-covered pixels, average over the configured ocean regions
      -> calendar-year means                            (time -> year)
      -> ``seasonal_trends.calc_trend_start_sensitivity`` (start_year x end_year)

The trend cube is cached in ``cache/``. The filename encodes every setting that
changes the cached numbers (``start_year``, ``end_year``, ``ocean_regions``,
``min_years``, ``step_size``, ``prewhitening`` and ``alpha``). The input paths
(``inputs:``) cannot go in the name, so delete the cache after changing inputs.

All settings (``inputs``, analysis period / region / trend grid, plot colours
and sizes, ``output`` formats, dpi and CSV export) live in
``config_S_SST_TREND_PERIODS.yaml`` next to this script.

Note on units: unlike the prototype screenshot (kelvin per year) slopes are
plotted in °C per ``trend_unit_per_years`` years (10 = per decade), matching
``fig2-sst_t2m_trends``.

Run from the repository root:

    MPLCONFIGDIR="$TMPDIR/mpl" .venv/bin/python \
        figS-sst_seasonal_trends/plot_S_SST_TREND_PERIODS.py
"""

from __future__ import annotations

from functools import partial
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import xarray as xr

from greenfjord.config import get_script_name, read_config
from greenfjord.viz import set_paper_style

# paths and names, derived from the script name (plot_<NAME>.py)
HERE = Path(__file__).resolve().parent
NAME = get_script_name(__file__)  # S_SST_TREND_PERIODS
FIG_STEM = f"fig_{NAME}"  # prefix of the PNG / PDF outputs
DATA_STEM = f"data_{NAME}"  # prefix of the CSV outputs

# config
cfg = read_config(HERE / f"config_{NAME}.yaml")
ana = cfg["analysis"]
plot = cfg["plot"]
output = cfg["output"]
SST_ZARR = HERE / cfg["inputs"]["sst"]
REGION_MASK = HERE / cfg["inputs"]["region_mask"]

START_YEAR = ana["start_year"]
END_YEAR = ana["end_year"]
OCEAN_REGIONS = ana["ocean_regions"]
REGION_NAME = ana["region_name"]
MIN_YEARS = ana["min_years"]
STEP_SIZE = ana["step_size"]
ALPHA = ana["alpha"]
# YAML 1.1 reads an unquoted ``off`` as False
PREWHITENING = "off" if ana["prewhitening"] is False else ana["prewhitening"]
TREND_UNIT_PER_YEARS = ana["trend_unit_per_years"]
CMAP = plot["cmap"]

# cache of the trend cube, keyed on every analysis setting that changes it
# (input paths are not in the name: delete the cache after changing inputs)
_regions = "_".join(str(region) for region in OCEAN_REGIONS)
CACHE = HERE / "cache" / (
    f"sst-annual_trend_sensitivity-{START_YEAR}_{END_YEAR}-regions{_regions}"
    f"-min{MIN_YEARS}-step{STEP_SIZE}-tfpw_{PREWHITENING}-alpha{ALPHA}.nc"
)


def load_domain_mean_sst() -> xr.DataArray:
    """Return the monthly domain-mean SST as a ``(time,)`` DataArray.

    Ice-covered pixels are dropped (``sea_ice_frac > 0``) before averaging, as
    in ``examples/sst.ipynb``; the spatial mean is weighted by cos(latitude).
    """
    ds = xr.open_zarr(SST_ZARR, chunks={}).sel(
        time=slice(f"{START_YEAR}-01-01", f"{END_YEAR}-12-31")
    )
    sst = ds["analysed_st"].where(ds["sea_ice_frac"] <= 0) - 273.15

    mask = (
        xr
        .open_dataset(REGION_MASK, drop_variables="spatial_ref")["region"]
        .rename(x="longitude", y="latitude")
        .interp_like(sst.isel(time=0, drop=True), method="nearest")
    )
    weights = np.cos(np.deg2rad(sst["latitude"])).where(mask.isin(OCEAN_REGIONS))

    domain_mean = (
        sst
        .weighted(weights.fillna(0))
        .mean(dim=["latitude", "longitude"])
        .compute()
        .assign_attrs(long_name="Sea Surface Temperature", units="°C")
    )

    return domain_mean


def load_period_means() -> xr.DataArray:
    """Return calendar-year domain-mean SST as ``(year, season)``.

    The single ``Annual`` "season" keeps the shape the trend code expects.
    """
    return (
        load_domain_mean_sst()
        .groupby("time.year")
        .mean("time")
        .sel(year=slice(START_YEAR, END_YEAR))
        .expand_dims(season=["Annual"])
        .transpose("year", "season", ...)
        .assign_attrs(long_name="Sea Surface Temperature", units="°C")
    )


def get_trend_func():
    """Return the trend function for the configured ``prewhitening`` mode."""
    from greenfjord.analysis import trends

    if PREWHITENING == "auto":
        return partial(trends.theilsen_mannkendall_tfpw, only_if_significant=True, alpha=ALPHA)
    if PREWHITENING == "force":
        return partial(trends.theilsen_mannkendall_tfpw, only_if_significant=False, alpha=ALPHA)
    if PREWHITENING == "off":
        return partial(trends.theilsen_mannkendall, nan_policy="drop")
    raise ValueError(f"prewhitening must be 'auto', 'force' or 'off', got {PREWHITENING!r}")


def load_trend_sensitivity() -> xr.DataArray:
    """Return (and cache) the start/end-year sensitivity of the trends."""
    if CACHE.exists():
        return xr.open_dataset(CACHE)["SST"]

    from greenfjord.analysis import seasonal_trends

    trend_func = get_trend_func()  # validates the setting before any work

    sensitivity = seasonal_trends.calc_trend_start_sensitivity(
        load_period_means().to_dataset(name="SST"),
        trend_func=trend_func,
        min_years=MIN_YEARS,
        step_size=STEP_SIZE,
    )
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    sensitivity.to_netcdf(CACHE)
    return sensitivity["SST"]


def write_csv(sensitivity: xr.DataArray) -> None:
    """Write the plotted numbers as two CSVs laid out like the figure.

    Each is a grid of end year (rows, latest first) x start year (columns);
    short trend periods are left empty, exactly as they are blank in the
    figure. ``-slope.csv`` holds slopes in °C per ``trend_unit_per_years``
    years, only the significant ones -- the cells annotated in the figure.
    ``-pvalue.csv`` holds all Mann-Kendall p-values.
    """
    import csv

    significant = sensitivity.sel(parameter="pvalue", drop=True) < ALPHA

    for suffix, parameter, scale, fmt in (
        ("slope", "slope", TREND_UNIT_PER_YEARS, "{:.4f}"),
        ("pvalue", "pvalue", 1, "{:.4g}"),
    ):
        panel = sensitivity.sel(parameter=parameter, drop=True) * scale
        if parameter == "slope":
            panel = panel.where(significant)
        block = (
            panel.sel(season="Annual")
            .transpose("end_year", "start_year")
            .sortby("end_year", ascending=False)
        )

        rows = [["Annual"] + [str(year) for year in block["start_year"].to_numpy()]]
        for end_year, values in zip(block["end_year"].to_numpy(), block.to_numpy()):
            rows.append([str(end_year)] + ["" if not np.isfinite(v) else fmt.format(v) for v in values])

        with (HERE / f"{DATA_STEM}-{suffix}.csv").open("w", newline="") as handle:
            csv.writer(handle).writerows(rows)


def plot_trend_heatmap(
    ax: plt.Axes,
    trends: xr.DataArray,
    *,
    vmax: float,
    caption: str,
) -> plt.cm.ScalarMappable:
    """Draw the start-year x end-year heat map of trend slopes on ``ax``.

    ``trends`` has ``start_year``, ``end_year`` and ``parameter`` (slope,
    pvalue) dimensions. Slopes are scaled to °C per ``trend_unit_per_years``
    years and coloured symmetrically about zero (``+-vmax``); significant
    cells (p < ``alpha``) are annotated with their slope. Start year runs
    along the top axis and end year down the left axis, so the valid periods
    fill the upper-left triangle. ``caption`` is written in the empty
    lower-right triangle if ``show_caption`` is set. Returns the mesh, for the
    colour bar.
    """
    slope = trends.sel(parameter="slope", drop=True) * TREND_UNIT_PER_YEARS
    significant = trends.sel(parameter="pvalue", drop=True) < ALPHA

    start_years = slope["start_year"].to_numpy()
    end_years = slope["end_year"].to_numpy()
    values = slope.transpose("end_year", "start_year").to_numpy()
    significant = significant.transpose("end_year", "start_year").to_numpy() & np.isfinite(values)

    image = ax.pcolormesh(
        np.arange(len(start_years) + 1),
        np.arange(len(end_years) + 1),
        values,
        cmap=CMAP,
        vmin=-vmax,
        vmax=vmax,
        edgecolors="white",
        linewidth=0.35,
    )

    # Significant cells carry their slope value. The text is white on the dark
    # ends of the colour map so it stays legible.
    annotation = plot["annotation"]
    for row, col in zip(*np.nonzero(significant)):
        value = values[row, col]
        ax.text(
            col + 0.5,
            row + 0.5,
            annotation["format"].format(value),
            ha="center",
            va="center",
            fontsize=annotation["font_size"],
            color="white" if abs(value) / vmax > 0.55 else "0.15",
        )

    ax.set_xlim(0, len(start_years))
    ax.set_ylim(0, len(end_years))
    ax.set_aspect("equal")
    ax.set_xticks(np.arange(len(start_years)) + 0.5)
    ax.set_yticks(np.arange(len(end_years)) + 0.5)
    ax.set_xticklabels([str(year) for year in start_years], rotation=90)
    ax.set_yticklabels([str(year) for year in end_years])
    ax.set_xlabel("Start year", labelpad=4)
    ax.xaxis.set_ticks_position("top")
    ax.xaxis.set_label_position("top")
    ax.set_ylabel("End year", labelpad=4)
    ax.tick_params(axis="both", length=0, pad=1.5)

    for spine in ax.spines.values():
        spine.set_visible(False)

    # The lower-right of the grid is empty (periods shorter than min_years are
    # not evaluated), so the caption sits there.
    if not plot["show_caption"]:
        return image
    ax.text(
        0.985,
        0.015,
        caption,
        transform=ax.transAxes,
        ha="right",
        va="bottom",
        fontsize=plot["caption_size"],
        linespacing=1.35,
    )

    return image


def main() -> None:
    set_paper_style(plot.get("style"))

    sensitivity = load_trend_sensitivity()
    if output["save_csv"]:
        write_csv(sensitivity)

    slopes = sensitivity.sel(parameter="slope") * TREND_UNIT_PER_YEARS
    vmax = float(np.nanmax(np.abs(slopes)))
    vmax = np.ceil(vmax * 10) / 10

    name = sensitivity.attrs.get("long_name", "Sea Surface Temperature")

    # The panel is square (equal aspect); figsize, margins and cbar_axes in
    # the config size the grid and place the colour bar to its right.
    fig = plt.figure(figsize=plot["figsize"])
    grid = fig.add_gridspec(1, 1, **plot["margins"])
    cax = fig.add_axes(plot["cbar_axes"])

    ax = fig.add_subplot(grid[0, 0])
    image = plot_trend_heatmap(
        ax,
        sensitivity.sel(season="Annual"),
        vmax=vmax,
        caption=f"Annual SST trend\n{REGION_NAME}\nMin. trend length: {MIN_YEARS} years",
    )

    colorbar = fig.colorbar(image, cax=cax)
    unit = {1: "yr$^{-1}$", 10: "dec$^{-1}$"}.get(TREND_UNIT_PER_YEARS, f"({TREND_UNIT_PER_YEARS} yr)$^{{-1}}$")
    colorbar.set_label(f"{name} trend (°C {unit})")
    colorbar.outline.set_linewidth(0.5)
    cax.tick_params(length=2, width=0.5, labelsize=plot["cbar_tick_size"])

    for fmt in output["formats"]:
        fig.savefig(HERE / f"{FIG_STEM}.{fmt}", dpi=output["dpi"], bbox_inches="tight")


if __name__ == "__main__":
    main()
