"""Sea-ice and chlorophyll bloom duration trends around southern Greenland.

Two-panel map: (a) the trend in the annual sea-ice season duration, recomputed
here from the daily DMI OI sea-ice fraction, and (b) the trend in chlorophyll
bloom duration (Nicholson et al., OC-CCI v6.0), read as a ready-made trend map.
All settings live in ``config_ICE_CHL_SEAS_DURATION.yaml``.

Data flow:

    daily DMI OI sea-ice fraction (``data/sea_ice_dmioi_daily``)
      -> yearly ice season start / end / duration (persistent ice cover)
      -> Theil-Sen slope + Mann-Kendall test of the duration, significant slopes only (cached)
      -> panel (a)
    bloom duration trend (``data/chlorophyll_bloom_duration_trend.nc``)
      -> small isolated patches masked
      -> panel (b)

Run from the repository root:

    MPLCONFIGDIR="$TMPDIR/mpl" .venv/bin/python fig4-ice_chla_phenology/plot_ICE_CHL_SEAS_DURATION.py
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import xarray as xr
from cartopy import crs as ccrs
from cartopy import feature as cfeature
from scipy.ndimage import label

from greenfjord.analysis import phenology, trends
from greenfjord.config import get_script_name, read_config
from greenfjord.viz import set_paper_style

# paths and names, derived from the script name (plot_<NAME>.py)
HERE = Path(__file__).resolve().parent
NAME = get_script_name(__file__)  # ICE_CHL_SEAS_DURATION
FIG_STEM = f"fig_{NAME}"  # prefix of the figure outputs

# config
cfg = read_config(HERE / f"config_{NAME}.yaml")
ana = cfg["analysis"]
plot = cfg["plot"]
output = cfg["output"]
SEA_ICE_DAILY = HERE / cfg["inputs"]["sea_ice_daily"]
CHL_BLOOM_TREND = HERE / cfg["inputs"]["chl_bloom_trend"]

# the filename encodes every analysis setting that changes the cached numbers
CACHE = HERE / "cache" / (
    f"sea_ice_duration_trend-{ana['start_year']}_{ana['end_year']}"
    f"-thr{ana['ice_threshold']}-gap{ana['min_gap']}-mindays{ana['min_ice_days']}"
    f"-minyears{ana['min_season_years']}-alpha{ana['alpha']}.nc"
)


def load_sea_ice_trend() -> xr.DataArray:
    """Return the significant sea-ice duration trend as ``(latitude, longitude)`` in days per year."""
    if CACHE.exists():
        return xr.open_dataarray(CACHE)

    ice_fraction = xr.open_dataarray(SEA_ICE_DAILY).sel(time=slice(str(ana["start_year"]), str(ana["end_year"])))
    # only pixels that ever have ice, flattened to 1-D to keep the rolling cheap
    flat = ice_fraction.load().stack(points=["latitude", "longitude"])
    flat = flat.where(lambda x: x.sum("time") > ana["min_ice_days"], drop=True)
    flat = flat.where(lambda x: x > 0)
    stats = phenology.get_phenology_stats(flat, flat > ana["ice_threshold"], min_gap=ana["min_gap"])
    stats = stats.unstack("points")

    trend = trends.theilsen_mannkendall(stats[["season_duration"]], dim="year")
    has_season = (stats.season_duration > 0).sum("year") > ana["min_season_years"]
    sea_ice_trend = trends.get_significant_slope(trend, threshold=ana["alpha"]).season_duration.where(has_season)
    sea_ice_trend = sea_ice_trend.rename("sea_ice_duration_trend").assign_attrs(
        units="days year-1", long_name="Sea ice duration trend"
    )

    CACHE.parent.mkdir(parents=True, exist_ok=True)
    sea_ice_trend.to_netcdf(CACHE)
    return sea_ice_trend


def load_chl_bloom_trend() -> xr.DataArray:
    """Return the bloom duration trend as ``(lat, lon)`` in days per year, small patches masked."""
    chl_trend = xr.open_dataarray(CHL_BLOOM_TREND)
    labels, n_labels = label(chl_trend.notnull().values)
    for k in range(1, n_labels + 1):
        if (labels == k).sum() < ana["min_chl_patch_pixels"]:
            chl_trend = chl_trend.where(labels != k)
    return chl_trend


def plot_trend_map(ax, trend: xr.DataArray, panel: dict, letter: str):
    """Draw a filled-contour trend map with land, coastline and a lettered title; return the contour set."""
    contours = trend.plot.contourf(
        ax=ax,
        transform=ccrs.PlateCarree(),
        add_colorbar=False,
        center=0,
        **{k: v for k, v in panel.items() if k != "title"},
    )
    ax.add_feature(cfeature.LAND.with_scale(plot["land_scale"]), facecolor=plot["land_color"])
    ax.coastlines(lw=plot["coastline_width"])
    ax.set_title(
        f"$\\bf{{{letter}}}$ {panel['title']}",
        fontsize=plot["title_size"],
        fontweight="normal",
        va="center",
        ha="left",
        loc="left",
        x=plot["title_x"],
        y=plot["title_y"],
        bbox=dict(facecolor="white", alpha=1, edgecolor="none", boxstyle=f"round,pad={plot['title_pad']}"),
    )
    return contours


def main() -> None:
    set_paper_style(plot.get("style"))
    sea_ice_trend = load_sea_ice_trend()
    chl_trend = load_chl_bloom_trend()

    fig = plt.figure(figsize=plot["figsize"], layout="constrained")
    axs = fig.subplot_mosaic("aabb", subplot_kw=dict(projection=ccrs.Mercator()))

    # panel (a): fixed symmetric colour scale
    panel_a = dict(plot["panels"]["a"])
    vlim = panel_a.pop("vlim")
    panel_a["levels"] = np.linspace(-vlim, vlim, panel_a["levels"])
    imgs = {
        "a": plot_trend_map(axs["a"], sea_ice_trend, panel_a, "a"),
        "b": plot_trend_map(axs["b"], chl_trend, plot["panels"]["b"], "b"),
    }
    for key, img in imgs.items():
        cbar = fig.colorbar(img, ax=axs[key], location="bottom", shrink=plot["cbar_shrink"])
        cbar.set_label(plot["cbar_label"])

    # same map extent (and so axes size) for both panels, whatever pixels are masked
    axs["a"].set_extent(axs["b"].get_extent(), crs=axs["b"].projection)

    for fmt in output["formats"]:
        fig.savefig(
            HERE / f"{FIG_STEM}.{fmt}", dpi=output["dpi"], bbox_inches="tight", transparent=plot["transparent"]
        )


if __name__ == "__main__":
    main()
