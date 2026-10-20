"""Sea-ice seasonality and phenology trends around southern Greenland (Fig. S).

Top row: mean number of days per season (DJF, MAM, JJA, SON) with sea-ice
fraction above ``analysis.ice_day_fraction``. Bottom row: Theil-Sen trends of
the start, end, duration and days of cover of the persistent sea-ice season,
shown where the Mann-Kendall test is significant (``analysis.alpha``).

Data flow (analysis functions in ``greenfjord.analysis.phenology`` / ``trends``):

    daily DMI OI sea-ice fraction (``data/sea_ice_dmioi_daily``)
      -> seasonal mean ice days                         (top row)
      -> yearly season start / end / duration / count   (cached)
      -> Theil-Sen slope + Mann-Kendall p-value         (cached)  (bottom row)

The caches in ``cache/`` encode every setting that changes their numbers
(years, ``ice_day_fraction``, ``min_ice_days``, ``min_gap``, ``trend_method``).
The input file cannot go in the name, so delete the caches if it changes.
All settings live in ``config_S_SEAICE_PHENOL.yaml``.

Run from the repository root:

    MPLCONFIGDIR="$TMPDIR/mpl" .venv/bin/python figures/figS_SEAICE_PHENOL/plot_S_SEAICE_PHENOL.py
"""

from __future__ import annotations

from pathlib import Path
from string import ascii_lowercase

import matplotlib.pyplot as plt
import numpy as np
import xarray as xr

from greenfjord.analysis import phenology, trends
from greenfjord.config import get_script_name, read_config
from greenfjord.viz import geo, set_paper_style

# paths and names, derived from the script name (plot_<NAME>.py)
HERE = Path(__file__).resolve().parent
NAME = get_script_name(__file__)  # S_SEAICE_PHENOL
FIG_STEM = f"fig_{NAME}"  # prefix of the PNG / PDF outputs

# config
cfg = read_config(HERE / f"config_{NAME}.yaml")
ana = cfg["analysis"]
plot = cfg["plot"]
output = cfg["output"]
SEA_ICE_DAILY = HERE / cfg["inputs"]["sea_ice_daily"]
Y0, Y1 = ana["years"]

# the filenames encode the settings that change the cached numbers
_KEY = (
    f"years{Y0}_{Y1}-ice_day_fraction{ana['ice_day_fraction']:g}"
    f"-min_ice_days{ana['min_ice_days']}-min_gap{ana['min_gap']}"
)
CACHE_PHENOLOGY = HERE / "cache" / f"phenology-{_KEY}.nc"
CACHE_TREND = HERE / "cache" / f"trend-{_KEY}-{ana['trend_method']}.nc"

TREND_FUNCS = {
    "standard": lambda da: trends.theilsen_mannkendall(da, dim="year", nan_policy="omit"),
    "tfpw": lambda da: trends.theilsen_mannkendall_tfpw(da, dim="year"),
}


def load_daily() -> xr.DataArray:
    """Daily sea-ice fraction (0-1) over the plot extent plus buffer."""
    return xr.open_dataarray(SEA_ICE_DAILY).load()


def load_seasonal(ice_fraction: xr.DataArray) -> xr.DataArray:
    """Mean days per season with ice, masked to cells that are ever ice-covered."""
    mask_icecover = (ice_fraction > ana["ice_threshold"]).sum("time") > ana["mask_min_days"]
    ice_days = ice_fraction.sel(time=slice(str(Y0), str(Y1))) > ana["ice_day_fraction"]
    seasonal = ice_days.groupby("time.season").sum("time") / (Y1 - Y0 + 1)
    return seasonal.sel(season=ana["seasons"]).where(mask_icecover)


def load_phenology(ice_fraction: xr.DataArray) -> xr.Dataset:
    """Yearly season start / end / duration / count per pixel, cached."""
    if not CACHE_PHENOLOGY.exists():
        ice = ice_fraction.sel(time=slice(str(Y0), str(Y1)))
        # only pixels that ever have ice, flattened to 1-D to keep the rolling cheap
        flat = ice.stack(points=["latitude", "longitude"]).where(
            lambda x: x.sum("time") > ana["min_ice_days"], drop=True
        )
        flat = flat.where(lambda x: x > 0)
        stats = phenology.get_phenology_stats(
            flat, flat > ana["ice_day_fraction"], min_gap=ana["min_gap"]
        ).unstack("points")
        CACHE_PHENOLOGY.parent.mkdir(exist_ok=True)
        stats.to_netcdf(CACHE_PHENOLOGY)
    return xr.open_dataset(CACHE_PHENOLOGY).load()


def load_trends(stats: xr.Dataset) -> xr.Dataset:
    """Significant Theil-Sen slopes of the phenology variables, cached."""
    if not CACHE_TREND.exists():
        stats = stats.assign(season_start_wrapped=phenology.wrap_doy(stats.season_start))
        # years without a season have NaN start / end and are left out of the fit
        out = stats[ana["trend_variables"]].map(TREND_FUNCS[ana["trend_method"]])
        out.attrs.update(
            units=plot["panels"]["trends"]["unit"],
            ice_day_fraction=ana["ice_day_fraction"],
            min_gap=ana["min_gap"],
            method=ana["trend_method"],
            years=f"{Y0}-{Y1}",
        )
        out.to_netcdf(CACHE_TREND)
    trend = trends.get_significant_slope(
        xr.open_dataset(CACHE_TREND).load(), threshold=ana["alpha"]
    )
    # pixels need a season in enough years; start / end also a valid date in enough years
    stats = stats.assign(season_start_wrapped=phenology.wrap_doy(stats.season_start))
    has_season = (stats.season_duration > 0).sum("year") > ana["min_season_years"]
    enough_years = stats[ana["trend_variables"]].count("year") > ana["min_date_years"]
    return trend.where(has_season & enough_years)


def plot_season_map(ax, seasonal: xr.DataArray, season: str):
    """Filled-contour map of the mean ice days in one season."""
    p = plot["panels"]["seasons"]
    crop = dict(latitude=slice(*plot["lat"]), longitude=slice(*plot["lon"]))
    return seasonal.sel(season=season).sel(**crop).plot.contourf(
        ax=ax, add_colorbar=False, levels=p["levels"], vmin=p["vmin"], vmax=p["vmax"],
        extend=p["extend"], cmap=p["cmap"], robust=False,
    )  # fmt: skip


def plot_trend_map(ax, trend: xr.Dataset, variable: str):
    """Filled-contour map of the significant trend of one phenology variable."""
    p = plot["panels"]["trends"]
    levels = np.linspace(-p["vlim"], p["vlim"], p["levels"])
    crop = dict(latitude=slice(*plot["lat"]), longitude=slice(*plot["lon"]))
    return trend[variable].sel(**crop).plot.contourf(
        ax=ax, add_colorbar=False, levels=levels, extend=p["extend"], cmap=p["cmap"],
    )  # fmt: skip


def plot_colorbar(fig, axs_row, contours, label: str, ticks=None):
    """One colourbar for a row of maps."""
    cb = fig.colorbar(
        contours, ax=axs_row, pad=plot["cbar_pad"], fraction=plot["cbar_fraction"], aspect=plot["cbar_aspect"]
    )
    cb.set_label(label, labelpad=plot["cbar_labelpad"])
    if ticks is not None:
        cb.set_ticks(ticks)


def plot_panel_label(ax, letter: str, name: str):
    """Bold panel letter and panel name on a translucent box below the map top."""
    kw = dict(y=plot["label_y"], va="bottom", size=plot["label_size"])
    ax.set_title(letter, loc="left", x=plot["letter_x"], fontweight="bold", **kw)
    ax.set_title(f"– {name}", loc="center", x=plot["name_x"], ha="left", bbox=plot["label_box"], **kw)


def main() -> None:
    set_paper_style(plot.get("style"))
    ice_fraction = load_daily()
    seasonal = load_seasonal(ice_fraction)
    trend = load_trends(load_phenology(ice_fraction))

    fig, axs = plt.subplots(2, 4, figsize=plot["figsize"], sharex=True, sharey=True)
    fig.subplots_adjust(hspace=plot["hspace"], wspace=plot["wspace"])

    sp, tp = plot["panels"]["seasons"], plot["panels"]["trends"]
    for ax, season in zip(axs[0], ana["seasons"]):
        cs = plot_season_map(ax, seasonal, season)
    plot_colorbar(fig, axs[0], cs, sp["cbar_label"].format(pct=ana["ice_day_fraction"] * 100), sp["cbar_ticks"])

    for ax, var in zip(axs[1], ana["trend_variables"]):
        cs = plot_trend_map(ax, trend, var)
    plot_colorbar(fig, axs[1], cs, tp["cbar_label"].format(unit=tp["unit"]))

    names = [*ana["seasons"], *ana["trend_titles"]]
    for i, (ax, name) in enumerate(zip(axs.flat, names)):
        geo.add_coastline(ax, land_kwargs=dict(facecolor=plot["land_color"]))
        ax.set_title("")
        ax.set_xlabel(plot["xlabel"] if ax in axs[1] else "")
        ax.set_ylabel(plot["ylabel"] if ax in axs[:, 0] else "")
        ax.set_xticks(plot["xticks"])
        ax.label_outer()
        plot_panel_label(ax, ascii_lowercase[i], name)

    fig.suptitle(plot["title"].format(y0=Y0, y1=Y1), y=plot["title_y"])
    for fmt in output["formats"]:
        fig.savefig(HERE / f"{FIG_STEM}.{fmt}", dpi=output["dpi"], bbox_inches="tight")
    print({v: int(trend[v].notnull().sum()) for v in ana["trend_variables"]})
    print({v: float(abs(trend[v]).max()) for v in ana["trend_variables"]})


if __name__ == "__main__":
    main()
