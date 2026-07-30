"""Sensitivity of seasonal 2 m air-temperature trends to the trend period.

The air-temperature counterpart to ``figS-sst_seasonal_trends``: one heat map per
season, where each cell is the Theil-Sen slope of seasonally averaged ERA5 2 m
air temperature (t2m) for a trend period running from a given *start year*
(rows) to a given *end year* (columns). Cells are marked with a dot when the
Mann-Kendall test finds the trend significant (p < 0.05).

Data flow (all of the analysis functions live in
``greenfjord.analysis.seasonal_trends``):

    daily ERA5 t2m (``fig2-sst_t2m_trends/data``)
      -> average over the GreenFjord land polygon
      -> ``seasonal_trends.preprocess_data``              (time -> year x season)
      -> ``seasonal_trends.calc_trend_start_sensitivity`` (start_year x end_year)

The trend cube is cached to ``data/t2m-seasonal_trend_sensitivity.nc``; delete
that file to recompute.

Slopes are plotted in °C per decade, matching ``fig2-sst_t2m_trends``.

Run from the repository root:

    MPLCONFIGDIR="$TMPDIR/mpl" .venv/bin/python \
        figS-t2m_seasonal_trends/plot_t2m_seasonal_trends.py
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import xarray as xr

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
FIG2_DATA = HERE.parent / "fig2-sst_t2m_trends" / "data"

ERA5_ZARR = FIG2_DATA / "era5-daily-greenfjord.zarr"
ERA5_REGIONS = FIG2_DATA / "era5-land-ocean-ice.gpkg"
TREND_CACHE = DATA / "t2m-seasonal_trend_sensitivity.nc"
OUT_PNG = HERE / "figS-t2m_seasonal_trends.png"
OUT_PDF = HERE / "figS-t2m_seasonal_trends.pdf"

START_YEAR = 1982
END_YEAR = 2021

# Subsets follow the row order in era5-land-ocean-ice.gpkg (land=1, ocean=2,
# ice=3). "land" is the GreenFjord AOI, the grey series in fig2.
SUBSET = "land"
SUBSET_VALUES = {"land": 1, "ocean": 2, "ice": 3}

# Shortest trend period (years) and the step between start / end years. These
# match figS-sst_seasonal_trends: start years 1982-2006, end years 1997-2021.
MIN_YEARS = 15
STEP_SIZE = 2

SEASONS = ["DJF", "MAM", "JJA", "SON"]
PANEL_LETTERS = ["a", "b", "c", "d"]

# Slope scaling: theilsen slopes come out as °C per year.
PER_DECADE = 10
CMAP = "RdBu_r"
SIGNIFICANCE = 0.05

# Shared colour limit in °C dec-1. None spans the full range, which winter
# dominates; set a number (e.g. 2.0) to clip it and bring out JJA and SON.
VMAX = None


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


def load_seasonal_t2m() -> xr.DataArray:
    """Return the subset-mean seasonal t2m as a ``(year, season)`` DataArray.

    The spatial mean is taken over the ``SUBSET`` polygon of
    ``era5-land-ocean-ice.gpkg`` and weighted by cos(latitude).
    """
    import geopandas as gpd
    import xarray_raster_vector  # noqa: F401 - registers the .rv accessor

    from greenfjord.analysis import seasonal_trends

    t2m = xr.open_zarr(ERA5_ZARR, chunks={})["t2m"].sel(
        time=slice(f"{START_YEAR}-01-01", f"{END_YEAR}-12-31")
    )
    mask = gpd.read_file(ERA5_REGIONS).rv.to_raster(t2m).rename({"x": "longitude", "y": "latitude"})
    weights = np.cos(np.deg2rad(t2m["latitude"])).where(mask == SUBSET_VALUES[SUBSET])

    subset_mean = (
        (t2m - 273.15)
        .weighted(weights.fillna(0))
        .mean(dim=["latitude", "longitude"])
        .compute()
        .assign_attrs(long_name="2 m Air Temperature", units="°C")
    )

    return seasonal_trends.preprocess_data(subset_mean)


def load_trend_sensitivity() -> xr.DataArray:
    """Return (and cache) the start/end-year sensitivity of seasonal trends."""
    if TREND_CACHE.exists():
        return xr.open_dataset(TREND_CACHE)["t2m"]

    from greenfjord.analysis import seasonal_trends, trends

    seasonal = load_seasonal_t2m()
    sensitivity = seasonal_trends.calc_trend_start_sensitivity(
        seasonal.to_dataset(name="t2m"),
        trend_func=trends.theilsen_mannkendall_tfpw,
        min_years=MIN_YEARS,
        step_size=STEP_SIZE,
    )
    DATA.mkdir(exist_ok=True)
    sensitivity.to_netcdf(TREND_CACHE)
    return sensitivity["t2m"]


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
    # so the panel caption sits inside the axes there.
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


def main() -> None:
    set_paper_style()
    sensitivity = load_trend_sensitivity().sel(season=SEASONS)

    slopes = sensitivity.sel(parameter="slope") * PER_DECADE
    data_vmax = np.ceil(float(np.nanmax(np.abs(slopes))) * 10) / 10
    vmax = data_vmax if VMAX is None else VMAX

    name = sensitivity.attrs.get("long_name", "2 m Air Temperature")

    # The panels are square (equal aspect, 13 x 13 trend periods), so the figure
    # height is chosen to match the width of the two-panel grid.
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

    image = None
    for index, season in enumerate(SEASONS):
        ax = fig.add_subplot(grid[index // 2, index % 2])
        title = f"$\\bf{{{PANEL_LETTERS[index]}}}$ \nSeason: {season}\n{name}"
        image = plot_season(
            ax,
            sensitivity.sel(season=season),
            vmax=vmax,
            title=title,
            show_end_years=index < 2,
            show_start_years=index % 2 == 1,
        )

    # Ticks and label go on the left of the colour bar so nothing collides with
    # the captions of the left-hand panels.
    cax = fig.add_axes([0.075, 0.20, 0.017, 0.60])
    colorbar = fig.colorbar(
        image,
        cax=cax,
        extend="both" if vmax < data_vmax else "neither",
    )
    cax.yaxis.set_ticks_position("left")
    cax.yaxis.set_label_position("left")
    colorbar.set_label(f"{name} trend (°C dec$^{{-1}}$)")
    colorbar.outline.set_linewidth(0.5)
    cax.tick_params(length=2, width=0.5, labelsize=7.2)

    fig.savefig(OUT_PNG, dpi=300, bbox_inches="tight")
    fig.savefig(OUT_PDF, bbox_inches="tight")


if __name__ == "__main__":
    main()
