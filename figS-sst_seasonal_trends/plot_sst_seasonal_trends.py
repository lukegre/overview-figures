"""Sensitivity of seasonal SST trends to the chosen trend period (Fig. S).

Reproduces the layout of ``examples/Screenshot 2026-07-29 at 15.28.42.png``,
which was originally produced by ``examples/sst.ipynb``: one heat map per
season, where each cell is the Theil-Sen slope of seasonally averaged
sea-surface temperature (SST) for a trend period running from a given *start
year* (rows) to a given *end year* (columns). Cells are marked with a dot when
the Mann-Kendall test finds the trend significant (p < 0.05).

Data flow (all of the analysis functions live in
``greenfjord.analysis.seasonal_trends``):

    monthly DMI SST (``fig2-sst_t2m_trends/data``)
      -> mask ice-covered pixels, average over the ocean regions 1-4
      -> ``seasonal_trends.preprocess_data``            (time -> year x season)
      -> ``seasonal_trends.calc_trend_start_sensitivity`` (start_year x end_year)

With ``--annual`` the same analysis is run on calendar-year means instead, so
the figure and the CSVs collapse to a single panel.

The trend cube is cached to ``data/sst-{seasonal,annual}_trend_sensitivity.nc``;
delete that file to recompute.

Note on units: unlike the prototype screenshot (kelvin per year) slopes are
plotted in °C per decade, matching ``fig2-sst_t2m_trends``.

Run from the repository root:

    MPLCONFIGDIR="$TMPDIR/mpl" .venv/bin/python \
        figS-sst_seasonal_trends/plot_sst_seasonal_trends.py [--annual]
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import xarray as xr

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
FIG2_DATA = HERE.parent / "fig2-sst_t2m_trends" / "data"

SST_ZARR = (
    FIG2_DATA / "cmems_obs_si_arc_phy_my_L4-DMIOI_P1D-m_multi-vars_54.48W-35.53W_"
    "58.00N-67.50N_1982-01-01-2024-12-31.monthly.zarr"
)
REGION_MASK = FIG2_DATA / "regions_mask.nc"

# ``--annual`` swaps every output path and the panel layout; the analysis
# itself is identical, only the averaging period changes.
STEM = {False: "figS-sst_seasonal_trends", True: "figS-sst_annual_trends"}
CACHE_STEM = {False: "sst-seasonal_trend_sensitivity", True: "sst-annual_trend_sensitivity"}

# Panel layout: rows of season names, matching the figure grid.
PANEL_LAYOUT = {False: [["DJF", "MAM"], ["JJA", "SON"]], True: [["Annual"]]}

START_YEAR = 1982
END_YEAR = 2021

# Ocean regions from data/regions_mask.nc; 0 is the near-shore band, which the
# project does not use. 1-4 are Oceanic, Southwest, Central western and
# South Eastern, i.e. the full GreenFjord ocean domain.
OCEAN_REGIONS = [1]

# Shortest trend period (years) and the step between start / end years. These
# reproduce the prototype's 1982-2006 x 1997-2021 grid.
MIN_YEARS = 15
STEP_SIZE = 2

PANEL_LETTERS = ["a", "b", "c", "d"]

# Slope scaling: theilsen slopes come out as °C per year.
PER_DECADE = 10
CMAP = "RdBu_r"
SIGNIFICANCE = 0.05


def set_paper_style() -> None:
    """Apply the same compact style as the other figures in this repository."""
    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.size": 8,
        "axes.titlesize": 8.5,
        "axes.labelsize": 8,
        "axes.linewidth": 0.5,
        "axes.titleweight": "normal",
        "xtick.labelsize": 6.6,
        "ytick.labelsize": 6.6,
        "xtick.major.size": 0,
        "ytick.major.size": 0,
        "legend.fontsize": 7.2,
        "legend.frameon": False,
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "savefig.facecolor": "white",
        "savefig.dpi": 300,
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
    })


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


def load_period_means(annual: bool) -> xr.DataArray:
    """Return domain-mean SST as ``(year, season)``.

    Seasonal runs use the project's DJF-anchored quarters; annual runs keep the
    same shape with a single calendar-year "season" so everything downstream --
    the trend cube, the figure and the CSVs -- is layout-agnostic.
    """
    from greenfjord.analysis import seasonal_trends

    domain_mean = load_domain_mean_sst()

    if not annual:
        return seasonal_trends.preprocess_data(domain_mean)

    return (
        domain_mean
        .groupby("time.year")
        .mean("time")
        .sel(year=slice(START_YEAR, END_YEAR))
        .expand_dims(season=["Annual"])
        .transpose("year", "season", ...)
        .assign_attrs(domain_mean.attrs)
    )


def load_trend_sensitivity(annual: bool) -> xr.DataArray:
    """Return (and cache) the start/end-year sensitivity of the trends."""
    cache = DATA / f"{CACHE_STEM[annual]}.nc"
    if cache.exists():
        return xr.open_dataset(cache)["SST"]

    from greenfjord.analysis import seasonal_trends, trends

    period_means = load_period_means(annual)
    sensitivity = seasonal_trends.calc_trend_start_sensitivity(
        period_means.to_dataset(name="SST"),
        trend_func=trends.theilsen_mannkendall_tfpw,
        min_years=MIN_YEARS,
        step_size=STEP_SIZE,
    )
    DATA.mkdir(exist_ok=True)
    sensitivity.to_netcdf(cache)
    return sensitivity["SST"]


def write_csv(sensitivity: xr.DataArray, annual: bool) -> None:
    """Write the plotted numbers as CSVs laid out like the figure.

    The panel blocks follow ``PANEL_LAYOUT`` -- 2 x 2 seasons (DJF MAM / JJA
    SON) or a single annual block -- each an upper-right triangle of start year
    (rows) x end year (columns); short trend periods are left empty, exactly as
    they are blank in the figure. Slopes are in °C per decade and only the
    significant ones are written -- the cells that carry a dot in the figure.
    The companion file holds all Mann-Kendall p-values.
    """
    import csv

    significant = sensitivity.sel(parameter="pvalue", drop=True) < SIGNIFICANCE

    for suffix, parameter, scale, fmt in (
        ("slope", "slope", PER_DECADE, "{:.4f}"),
        ("pvalue", "pvalue", 1, "{:.4g}"),
    ):
        panel = sensitivity.sel(parameter=parameter, drop=True) * scale
        if parameter == "slope":
            panel = panel.where(significant)
        rows: list[list[str]] = []

        for line in PANEL_LAYOUT[annual]:
            if rows:
                rows.append([])
            blocks = [
                panel.sel(season=season).transpose("start_year", "end_year") for season in line
            ]
            end_years = [str(year) for year in blocks[0]["end_year"].to_numpy()]
            start_years = blocks[0]["start_year"].to_numpy()

            header = []
            for season in line:
                header += [season] + end_years + [""]
            rows.append(header[:-1])

            for index, start_year in enumerate(start_years):
                row = []
                for block in blocks:
                    values = block.to_numpy()[index]
                    row += [str(start_year)]
                    row += ["" if not np.isfinite(v) else fmt.format(v) for v in values]
                    row += [""]
                rows.append(row[:-1])

        path = HERE / f"{STEM[annual]}-{suffix}.csv"
        with path.open("w", newline="") as handle:
            csv.writer(handle).writerows(rows)


def plot_season(
    ax: plt.Axes,
    season: xr.DataArray,
    *,
    vmax: float,
    title: str,
    show_end_years: bool,
    show_start_years: bool,
) -> plt.cm.ScalarMappable:
    """Draw one season's start-year x end-year heat map of trend slopes."""
    slope = season.sel(parameter="slope", drop=True) * PER_DECADE
    significant = season.sel(parameter="pvalue", drop=True) < SIGNIFICANCE

    start_years = slope["start_year"].to_numpy()
    end_years = slope["end_year"].to_numpy()
    values = slope.transpose("start_year", "end_year").to_numpy()

    image = ax.pcolormesh(
        np.arange(len(end_years) + 1),
        np.arange(len(start_years) + 1),
        values,
        cmap=CMAP,
        vmin=-vmax,
        vmax=vmax,
        edgecolors="white",
        linewidth=0.35,
    )

    # Significance dots switch to white on the dark ends of the colour map so
    # they stay legible, as in the prototype figure.
    mark = significant.transpose("start_year", "end_year").to_numpy() & np.isfinite(values)
    rows, cols = np.nonzero(mark)
    shade = np.abs(values[rows, cols]) / vmax
    for on_dark in (False, True):
        selection = shade > 0.55 if on_dark else shade <= 0.55
        ax.scatter(
            cols[selection] + 0.5,
            rows[selection] + 0.5,
            s=4.2,
            color="white" if on_dark else "0.15",
            linewidths=0,
            zorder=3,
        )

    ax.set_xlim(0, len(end_years))
    ax.set_ylim(len(start_years), 0)
    ax.set_aspect("equal")
    ax.set_xticks(np.arange(len(end_years)) + 0.5)
    ax.set_yticks(np.arange(len(start_years)) + 0.5)
    ax.set_xticklabels([str(year) for year in end_years], rotation=90)
    ax.set_yticklabels([str(year) for year in start_years])
    ax.xaxis.set_ticks_position("top")
    ax.xaxis.set_label_position("top")
    ax.yaxis.set_ticks_position("right")
    ax.yaxis.set_label_position("right")
    ax.tick_params(axis="both", length=0, pad=1.5)

    if show_end_years:
        ax.set_xlabel("End year", labelpad=4)
    else:
        ax.tick_params(axis="x", labeltop=False)
    if show_start_years:
        ax.set_ylabel("Start year", labelpad=4)
    else:
        ax.tick_params(axis="y", labelright=False)

    for spine in ax.spines.values():
        spine.set_visible(False)

    # The lower-left of each panel is empty (short periods are not evaluated),
    # so the panel caption sits inside the axes there, as in the prototype.
    ax.text(
        0.015,
        0.015,
        title,
        transform=ax.transAxes,
        ha="left",
        va="bottom",
        fontsize=7.2,
        linespacing=1.35,
    )

    return image


def main(annual: bool = False) -> None:
    set_paper_style()
    layout = PANEL_LAYOUT[annual]
    seasons = [season for line in layout for season in line]
    n_cols = len(layout[0])

    sensitivity = load_trend_sensitivity(annual).sel(season=seasons)

    write_csv(sensitivity, annual)

    slopes = sensitivity.sel(parameter="slope") * PER_DECADE
    vmax = float(np.nanmax(np.abs(slopes)))
    vmax = np.ceil(vmax * 10) / 10

    name = sensitivity.attrs.get("long_name", "Sea Surface Temperature")

    # The panels are square (equal aspect, 13 x 13 trend periods), so the figure
    # height is chosen to match the width of the panel grid.
    if annual:
        fig = plt.figure(figsize=(3.4, 3.0))
        grid = fig.add_gridspec(1, 1, left=0.24, right=0.95, top=0.86, bottom=0.04)
        cax = fig.add_axes([0.09, 0.16, 0.032, 0.60])
    else:
        fig = plt.figure(figsize=(5, 4.6))
        grid = fig.add_gridspec(
            2,
            2,
            wspace=0.1,
            hspace=0.12,
            left=0.12,
            right=0.94,
            top=0.915,
            bottom=0.03,
        )
        cax = fig.add_axes([0.075, 0.20, 0.017, 0.60])

    image = None
    for index, season in enumerate(seasons):
        ax = fig.add_subplot(grid[index // n_cols, index % n_cols])
        period = "Annual" if season == "Annual" else f"Season: {season}"
        title = (
            f"$\\bf{{{PANEL_LETTERS[index]}}}$ \n{period}\n{name}"
            # f"{slope_method} slopes\n"
            # f"•  significant with {test_method}"
        )
        image = plot_season(
            ax,
            sensitivity.sel(season=season),
            vmax=vmax,
            title=title,
            show_end_years=index < n_cols,
            show_start_years=index % n_cols == n_cols - 1,
        )

    # Ticks and label go on the left of the colour bar so nothing collides with
    # the captions of the left-hand panels.
    colorbar = fig.colorbar(image, cax=cax)
    cax.yaxis.set_ticks_position("left")
    cax.yaxis.set_label_position("left")
    colorbar.set_label(f"{name} trend (°C dec$^{{-1}}$)")
    colorbar.outline.set_linewidth(0.5)
    cax.tick_params(length=2, width=0.5, labelsize=7.2)

    fig.savefig(HERE / f"{STEM[annual]}.png", dpi=300, bbox_inches="tight")
    fig.savefig(HERE / f"{STEM[annual]}.pdf", bbox_inches="tight")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--annual",
        action="store_true",
        help="use calendar-year means and a single panel instead of the four seasons",
    )
    main(**vars(parser.parse_args()))
