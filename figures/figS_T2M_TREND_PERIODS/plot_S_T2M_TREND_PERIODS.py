"""Sensitivity of seasonal 2 m air-temperature trends to the trend period.

The air-temperature counterpart to ``figS-sst_seasonal_trends``: one heat map per
season, where each cell is the Theil-Sen slope of seasonally averaged ERA5 2 m
air temperature (t2m) for a trend period running from a given *start year*
(columns) to a given *end year* (rows). Significant cells (Mann-Kendall p < ``alpha``)
are annotated with their slope.

Significance is tested on the original series (``prewhitening: "off"``) or on a
trend-free prewhitened series (Yue et al., 2002, Hydrol. Process. 16, 1807) to
account for lag-1 autocorrelation: ``"auto"`` prewhitens only when the lag-1
autocorrelation is significant at ``alpha``, ``"force"`` always does. The slope
is always the Theil-Sen slope of the original series.

Data flow (all of the analysis functions live in
``greenfjord.analysis.seasonal_trends``):

    monthly ERA5 t2m (``data/era5_monthly_south_greenland``)
      -> crop to the bounding box of the region polygons
      -> cos(lat)-weighted mean over the ``subset`` polygon
         (``data/greenfjord_land_ocean_ice/greenfjord_land_ocean_ice.gpkg``)
      -> seasonal means (DJF, MAM, JJA, SON; a season needs all 3 months)
         via ``seasonal_trends.preprocess_data``        (time -> year x season)
      -> ``seasonal_trends.calc_trend_start_sensitivity`` (end_year x start_year)

The trend cube is cached in ``cache/``. The filename encodes every setting that
changes the cached numbers (``subset``, ``start_year``, ``end_year``,
``min_years``, ``step_size``, ``prewhitening`` and ``alpha``). The input paths
(``inputs:``) cannot go in the name, so delete the cache after changing inputs.

All settings (``inputs``, analysis period / region / trend grid, plot colours,
``output`` formats, dpi and CSV export) live in ``config_S_T2M_TREND_PERIODS.yaml``
next to this script.

Slopes are plotted in °C per ``trend_unit_per_years`` years (10 = per decade),
matching ``fig2-sst_t2m_trends``.

Run from the repository root:

    MPLCONFIGDIR="$TMPDIR/mpl" .venv/bin/python \
        figS-t2m_seasonal_trends/plot_S_T2M_TREND_PERIODS.py
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
NAME = get_script_name(__file__)  # S_T2M_TREND_PERIODS
FIG_STEM = f"fig_{NAME}"  # prefix of the PNG / PDF outputs
DATA_STEM = f"data_{NAME}"  # prefix of the CSV outputs

# config
cfg = read_config(HERE / f"config_{NAME}.yaml")
ana = cfg["analysis"]
plot = cfg["plot"]
output = cfg["output"]
ERA5_FILE = HERE / cfg["inputs"]["era5"]
REGION_POLYGONS = HERE / cfg["inputs"]["region_polygons"]

SUBSET = ana["subset"]
REGION_NAME = ana["region_name"]
START_YEAR = ana["start_year"]
END_YEAR = ana["end_year"]
SEASONS = ana["seasons"]
MIN_YEARS = ana["min_years"]
STEP_SIZE = ana["step_size"]
ALPHA = ana["alpha"]
# YAML 1.1 reads an unquoted ``off`` as False
PREWHITENING = "off" if ana["prewhitening"] is False else ana["prewhitening"]
TREND_UNIT_PER_YEARS = ana["trend_unit_per_years"]
CMAP = plot["cmap"]
VMAX = plot["vmax"]
CAPTION_SIZE = plot["caption_size"]
CBAR_TICK_SIZE = plot["cbar_tick_size"]

# row of each polygon set in greenfjord_land_ocean_ice.gpkg
SUBSET_VALUES = {"land": 1, "ocean": 2, "ice": 3}

# cache of the trend cube, keyed on every analysis setting that changes it
# (input paths are not in the name: delete the cache after changing inputs)
CACHE = HERE / "cache" / (
    f"t2m-seasonal_trend_sensitivity-{SUBSET}-{START_YEAR}_{END_YEAR}"
    f"-min{MIN_YEARS}-step{STEP_SIZE}-tfpw_{PREWHITENING}-alpha{ALPHA}.nc"
)


def load_seasonal_t2m() -> xr.DataArray:
    """Return the subset-mean seasonal t2m as a ``(year, season)`` DataArray.

    The monthly ERA5 field is cropped to the bounding box of the region
    polygons, then averaged over the ``subset`` polygon, weighted by
    cos(latitude). Seasons missing a month (the DJF that starts in the last
    December) are set to NaN.
    """
    import geopandas as gpd
    import xarray_raster_vector  # noqa: F401 - registers the .rv accessor

    from greenfjord.analysis import seasonal_trends

    polygons = gpd.read_file(REGION_POLYGONS)
    lon_min, lat_min, lon_max, lat_max = polygons.total_bounds

    t2m = (
        xr
        .open_dataset(ERA5_FILE)["t2m"]
        .rename(valid_time="time")
        .drop_vars(["expver", "number"], errors="ignore")
        .sel(time=slice(f"{START_YEAR}-01-01", f"{END_YEAR}-12-31"))
        .sel(longitude=slice(lon_min, lon_max), latitude=slice(lat_max, lat_min))
    )
    mask = polygons.rv.to_raster(t2m).rename({"x": "longitude", "y": "latitude"})
    weights = np.cos(np.deg2rad(t2m["latitude"])).where(mask == SUBSET_VALUES[SUBSET])

    subset_mean = (
        (t2m - 273.15)
        .weighted(weights.fillna(0))
        .mean(dim=["latitude", "longitude"])
        .compute()
        .assign_attrs(long_name="2 m Air Temperature", units="°C")
    )

    # keep only complete seasons (3 months), then reshape to (year, season)
    quarters = subset_mean.resample(time="QS-DEC")
    complete = quarters.mean().where(quarters.count() == 3)
    seasonal = seasonal_trends.preprocess_data(complete, clip_time=False)
    return seasonal.sel(year=slice(START_YEAR, END_YEAR)).assign_attrs(subset_mean.attrs)


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
    """Return (and cache) the start/end-year sensitivity of seasonal trends."""
    if CACHE.exists():
        return xr.open_dataset(CACHE)["t2m"]

    from greenfjord.analysis import seasonal_trends

    trend_func = get_trend_func()  # validates the setting before any work

    sensitivity = seasonal_trends.calc_trend_start_sensitivity(
        load_seasonal_t2m().to_dataset(name="t2m"),
        trend_func=trend_func,
        min_years=MIN_YEARS,
        step_size=STEP_SIZE,
    )
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    sensitivity.to_netcdf(CACHE)
    return sensitivity["t2m"]


def write_csv(sensitivity: xr.DataArray) -> None:
    """Write the plotted numbers as two CSVs laid out like the figure.

    One block per season, each a grid of end year (rows, latest first) x start
    year (columns); short trend periods are left empty, as they are blank in the
    figure. The first column holds the season, the second the end year.
    ``-slope.csv`` holds slopes in °C per ``trend_unit_per_years`` years, only
    the significant ones -- the cells annotated in the figure. ``-pvalue.csv``
    holds all Mann-Kendall p-values.
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

        rows = []
        for season in SEASONS:
            block = (
                panel.sel(season=season)
                .transpose("end_year", "start_year")
                .sortby("end_year", ascending=False)
            )
            start_years = [str(year) for year in block["start_year"].to_numpy()]
            rows.append(["season", "end_year\\start_year"] + start_years)
            for end_year, values in zip(block["end_year"].to_numpy(), block.to_numpy()):
                cells = ["" if not np.isfinite(v) else fmt.format(v) for v in values]
                rows.append([season, str(end_year)] + cells)

        with (HERE / f"{DATA_STEM}-{suffix}.csv").open("w", newline="") as handle:
            csv.writer(handle).writerows(rows)


def plot_trend_heatmap(
    ax: plt.Axes,
    trends: xr.DataArray,
    *,
    vmax: float,
    caption: str,
    show_start_years: bool,
    show_end_years: bool,
) -> plt.cm.ScalarMappable:
    """Draw one season's start-year x end-year heat map of trend slopes on ``ax``.

    ``trends`` has ``start_year``, ``end_year`` and ``parameter`` (slope,
    pvalue) dimensions. Slopes are scaled to °C per ``trend_unit_per_years``
    years and coloured symmetrically about zero (``+-vmax``); significant
    cells (p < ``alpha``) are annotated with their slope. Start year runs
    along the top axis and end year down the left axis, so the valid periods
    fill the upper-left triangle. ``caption`` is written in the empty
    lower-right corner. Shared axes: start-year labels only if
    ``show_start_years`` (top row), end-year labels only if ``show_end_years``
    (left column). Returns the mesh, for the colour bar.
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
        edgecolors=plot["cell_edge_color"],
        linewidth=plot["cell_edge_linewidth"],
    )

    # Significant cells carry their slope value. The text switches to the light
    # colour on the dark ends of the colour map so it stays legible.
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
            color=annotation["light_color"] if abs(value) / vmax > annotation["switch_threshold"] else annotation["dark_color"],
        )

    ax.set_xlim(0, len(start_years))
    ax.set_ylim(0, len(end_years))
    ax.set_aspect("equal")
    ax.set_xticks(np.arange(len(start_years)) + 0.5)
    ax.set_yticks(np.arange(len(end_years)) + 0.5)
    ax.set_xticklabels([str(year) for year in start_years], rotation=90)
    ax.set_yticklabels([str(year) for year in end_years])
    ax.xaxis.set_ticks_position("top")
    ax.xaxis.set_label_position("top")
    ax.tick_params(axis="both", length=0, pad=1.5)

    if show_start_years:
        ax.set_xlabel("Start year", labelpad=4)
    else:
        ax.tick_params(axis="x", labeltop=False)
    if show_end_years:
        ax.set_ylabel("End year", labelpad=4)
    else:
        ax.tick_params(axis="y", labelleft=False)

    for spine in ax.spines.values():
        spine.set_visible(False)

    # The lower-right of each panel is empty (periods shorter than min_years are
    # not evaluated), so the caption sits there, right-aligned.
    ax.text(
        0.985,
        0.015,
        caption,
        transform=ax.transAxes,
        ha="right",
        va="bottom",
        fontsize=CAPTION_SIZE,
        linespacing=1.35,
    )

    return image


def main() -> None:
    set_paper_style(plot.get("style"))
    sensitivity = load_trend_sensitivity().sel(season=SEASONS)
    if output["save_csv"]:
        write_csv(sensitivity)

    slopes = sensitivity.sel(parameter="slope") * TREND_UNIT_PER_YEARS
    data_vmax = np.ceil(float(np.nanmax(np.abs(slopes))) * 10) / 10
    vmax = data_vmax if VMAX is None else VMAX

    name = sensitivity.attrs.get("long_name", "2 m Air Temperature")

    # The panels are square (equal aspect, one cell per trend period). figsize,
    # margins and cbar_axes in the config size the 2 x 2 grid and place the
    # colour bar to its right.
    fig = plt.figure(figsize=plot["figsize"])
    grid = fig.add_gridspec(2, 2, **plot["margins"])

    image = None
    for index, season in enumerate(SEASONS):
        ax = fig.add_subplot(grid[index // 2, index % 2])
        caption = f"$\\bf{{{plot['panel_letters'][index]}}}$ \nSeason: {season}\n{name}"
        image = plot_trend_heatmap(
            ax,
            sensitivity.sel(season=season),
            vmax=vmax,
            caption=caption,
            show_start_years=index < 2,
            show_end_years=index % 2 == 0,
        )

    cax = fig.add_axes(plot["cbar_axes"])
    colorbar = fig.colorbar(
        image,
        cax=cax,
        extend="both" if vmax < data_vmax else "neither",
    )
    unit = {1: "yr$^{-1}$", 10: "dec$^{-1}$"}.get(TREND_UNIT_PER_YEARS, f"({TREND_UNIT_PER_YEARS} yr)$^{{-1}}$")
    colorbar.set_label(f"{name} trend (°C {unit})")
    colorbar.outline.set_linewidth(0.5)
    cax.tick_params(length=2, width=0.5, labelsize=CBAR_TICK_SIZE)

    for fmt in output["formats"]:
        fig.savefig(HERE / f"{FIG_STEM}.{fmt}", dpi=output["dpi"], bbox_inches="tight")


if __name__ == "__main__":
    main()
