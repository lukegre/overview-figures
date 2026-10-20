"""Net fraction of land pixels with a significant seasonal ERA5 trend.

A heat map of the net signed fraction (% of pixels with a significant positive
trend minus % with a significant negative trend) for each ERA5 variable (rows)
and season (columns), over the GreenFjord land domain. It shows how widespread
and how consistent in sign the recent climate trends are across the domain.

Data flow:

    monthly ERA5 (``data/era5_monthly_south_greenland``)
      -> crop to the bounding box of the region polygons
      -> keep grid cells whose centre lies inside the ``region`` polygon
      -> clip to start_year..end_year, seasonal means (DJF, MAM, JJA, SON)
      -> per-pixel Theil-Sen slope and Mann-Kendall p-value
      -> fraction of pixels with a significant positive / negative trend
      -> heat map of the net fraction

The seasonal means are taken after clipping the time axis, and incomplete
seasons are kept: the last DJF (labelled by its December year, ``end_year``)
contains December of ``end_year`` only. This is deliberate and reproduces the
original analysis.

All settings live in ``config_ERA_TREND_SIG.yaml``.

Run from the repository root:

    MPLCONFIGDIR="$TMPDIR/mpl" .venv/bin/python fig5-era5_pixel_frac/plot_ERA_TREND_SIG.py
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import xarray as xr

from greenfjord.config import get_script_name, read_config
from greenfjord.viz import set_paper_style

# paths and names, derived from the script name (plot_<NAME>.py)
HERE = Path(__file__).resolve().parent
NAME = get_script_name(__file__)  # ERA_TREND_SIG
FIG_STEM = f"fig_{NAME}"  # prefix of the PNG outputs
DATA_STEM = f"data_{NAME}"  # prefix of the CSV outputs

# config
cfg = read_config(HERE / f"config_{NAME}.yaml")
ana = cfg["analysis"]
plot = cfg["plot"]
output = cfg["output"]
ERA5_FILE = HERE / cfg["inputs"]["era5"]
REGION_POLYGONS = HERE / cfg["inputs"]["region_polygons"]

REGION = ana["region"]
START_YEAR = ana["start_year"]
END_YEAR = ana["end_year"]
SEASONS = ana["seasons"]
ALPHA = ana["alpha"]
VARIABLES = ana["variables"]  # ERA5 name -> label


def load_net_fraction() -> pd.DataFrame:
    """Return the net fraction of pixels with a significant trend.

    Pixels are the ERA5 grid cells whose centre lies inside the ``region``
    polygon. Each variable is averaged to seasons (the time axis is clipped to
    ``start_year``..``end_year`` first; partial seasons are kept, so the last
    DJF holds December of ``end_year`` only, as in the original analysis), and
    a Theil-Sen slope and Mann-Kendall p-value are computed per pixel.

    The result is a (variable label x season) frame of the net signed fraction
    in %: significant positive minus significant negative pixels, as a share of
    the valid pixels. Rows are sorted from most to least positive row mean when
    ``plot.sort_by_mean_net_fraction``.
    """
    import geopandas as gpd
    import shapely

    from greenfjord.analysis import seasonal_trends, trends

    polygons = gpd.read_file(REGION_POLYGONS)
    lon_min, lat_min, lon_max, lat_max = polygons.total_bounds
    geometry = polygons.loc[polygons["index"] == REGION, "geometry"].union_all()

    ds = (
        xr
        .open_dataset(ERA5_FILE)[list(VARIABLES)]
        .rename(valid_time="time")
        .drop_vars(["expver", "number"], errors="ignore")
        .sel(longitude=slice(lon_min, lon_max), latitude=slice(lat_max, lat_min))
    )

    # pixel selection: cells whose centre lies inside the polygon
    lon2d, lat2d = np.meshgrid(ds["longitude"].to_numpy(), ds["latitude"].to_numpy())
    mask = xr.DataArray(
        shapely.contains_xy(geometry, lon2d, lat2d),
        coords={"latitude": ds["latitude"], "longitude": ds["longitude"]},
        dims=("latitude", "longitude"),
    )

    net = {}
    for var, label in VARIABLES.items():
        da = ds[var].where(mask).sel(time=slice(f"{START_YEAR}-01-01", f"{END_YEAR}-12-31"))
        # partial seasons are kept: the last DJF is December of END_YEAR alone
        seasonal = seasonal_trends.preprocess_data(
            da.resample(time="QS-DEC").mean(), clip_time=False
        ).sel(year=slice(START_YEAR, END_YEAR))
        result = trends.theilsen_mannkendall(seasonal, dim="year", nan_policy="drop")
        slope = result.sel(parameter="slope", drop=True)
        pvalue = result.sel(parameter="pvalue", drop=True)

        dims = ["latitude", "longitude"]
        valid = pvalue.notnull().sum(dim=dims)
        significant = pvalue < ALPHA
        n_positive = (significant & (slope > 0)).sum(dim=dims)
        n_negative = (significant & (slope < 0)).sum(dim=dims)
        net[label] = ((n_positive - n_negative) / valid * 100).to_series()

    net = pd.DataFrame(net).T[SEASONS]
    if plot["sort_by_mean_net_fraction"]:
        net = net.loc[net.mean(axis=1).sort_values(ascending=False).index]
    net.columns.name = "season"
    return net


def write_csv(net: pd.DataFrame) -> None:
    """Write the plotted net fraction in % (variable x season), rows in plotted order."""
    net.to_csv(HERE / f"{DATA_STEM}-net_fraction.csv")


def plot_net_fraction_heatmap(fig: plt.Figure, ax: plt.Axes, net: pd.DataFrame) -> None:
    """Draw the variable x season heat map of the net fraction (%) on ``ax``.

    The colour bar is added to ``fig``. Cells with an absolute value below
    ``plot.hide_below_abs`` are masked (drawn in the background colour) and not
    annotated. Strong cells get light annotation text. Every appearance setting
    comes from the ``plot`` section of the config.
    """
    data = net.to_numpy()
    nrows, ncols = data.shape
    vmax = plot["vmax"]
    tick_length = plot["tick_length"]
    annotation = plot["annotation"]
    colorbar = plot["colorbar"]

    ax.set_facecolor(plot["background_color"])
    # near-zero cells are masked and drawn in the background colour
    cmap = plt.get_cmap(plot["cmap"]).copy()
    cmap.set_bad(plot["background_color"])
    masked = np.ma.masked_where(np.abs(data) < plot["hide_below_abs"], data)
    im = ax.imshow(masked, cmap=cmap, vmin=-vmax, vmax=vmax, aspect="auto")

    labels_wrapped = net.index.str.wrap(
        width=plot["label_wrap_width"], break_long_words=False
    ).tolist()
    ax.set_xticks(range(ncols), net.columns)
    ax.set_yticks(range(nrows), labels_wrapped)
    ax.tick_params(length=tick_length)
    for spine in ax.spines.values():
        spine.set_visible(True)
        spine.set_linewidth(plot["spine_linewidth"])
        spine.set_color(plot["spine_color"])

    # gaps between cells
    ax.set_xticks(np.arange(-0.5, ncols), minor=True)
    ax.set_yticks(np.arange(-0.5, nrows), minor=True)
    ax.grid(
        which="minor",
        color=plot["cell_gap_color"],
        linewidth=plot["cell_gap_linewidth"],
    )
    ax.tick_params(which="minor", length=tick_length)

    # annotate each cell with its absolute value; hide near-zero values
    for i in range(nrows):
        for j in range(ncols):
            v = data[i, j]
            if abs(v) < plot["hide_below_abs"]:
                continue
            ax.text(
                j,
                i,
                annotation["format"].format(abs(v)),
                ha="center",
                va="center",
                fontweight=annotation["font_weight"],
                fontsize=annotation["font_size"],
                color=(
                    annotation["light_color"]
                    if abs(v) > annotation["light_text_above_abs"]
                    else annotation["dark_color"]
                ),
            )

    cbar = fig.colorbar(im, ax=ax, pad=colorbar["pad"], aspect=colorbar["aspect"])
    cbar.set_ticks([-vmax, 0, vmax])
    cbar.set_label(colorbar["label"], labelpad=colorbar["label_pad"])
    for spine in cbar.ax.spines.values():
        spine.set_linewidth(colorbar["spine_linewidth"])
        spine.set_color(colorbar["spine_color"])
    cbar.ax.tick_params(length=tick_length)


def main() -> None:
    set_paper_style(plot.get("style"))
    net = load_net_fraction()
    if output.get("save_csv"):
        write_csv(net)

    fig, ax = plt.subplots(figsize=plot["figsize"], constrained_layout=True)
    plot_net_fraction_heatmap(fig, ax, net)

    for fmt in output["formats"]:
        fig.savefig(HERE / f"{FIG_STEM}.{fmt}", dpi=output["dpi"], bbox_inches="tight")


if __name__ == "__main__":
    main()
