"""Recreate figure 4: sea ice duration trend and chlorophyll bloom duration
trend around southern Greenland."""

import pathlib

import dotenv
import matplotlib.pyplot as plt
import numpy as np
import xarray as xr
from cartopy import crs as ccrs
from cartopy import feature as cfeature
from scipy.ndimage import label

HERE = pathlib.Path(__file__).parent
REPO = pathlib.Path(dotenv.find_dotenv()).parent
LAND_COLOR = "0.93"


def load_data():
    sea_ice_duration_trend = xr.open_dataarray(HERE / "data" / "seaice_duration_trend.nc").drop_vars([
        "spatial_ref",
        "stat",
    ])
    chl_bloom_duration_trend = xr.open_dataarray(HERE / "data" / "chlorophyll_bloom_duration_trend.nc")
    # remove small isolated patches from chlorophyll bloom trend
    arr = np.array(chl_bloom_duration_trend.notnull().values)
    labels, n_labels = label(arr)
    for k in range(1, n_labels + 1):
        if (labels == k).sum() < 20:
            chl_bloom_duration_trend = chl_bloom_duration_trend.where(labels != k)

    return sea_ice_duration_trend, chl_bloom_duration_trend


def make_figure(sea_ice_duration_trend, chl_bloom_duration_trend):
    mosaic = "aabb"
    fig = plt.figure(figsize=(6, 3.1), layout="constrained")
    axs = fig.subplot_mosaic(mosaic, subplot_kw=dict(projection=ccrs.Mercator()))

    cbar_props = dict(location="bottom", shrink=0.8)
    imgs = []
    cbars = []

    # -----------------------------------------------------------------
    # Sea ice duration trend
    # -----------------------------------------------------------------
    props = dict(
        transform=ccrs.PlateCarree(),
        add_colorbar=False,
        robust=True,
        cmap="RdBu_r",
        center=0,
        levels=11,
        extend="both",
    )
    imgs += (sea_ice_duration_trend.plot.contourf(ax=axs["a"], **props),)
    cbars += (plt.colorbar(imgs[-1], ax=axs["a"], **cbar_props),)

    # -----------------------------------------------------------------
    # Chlorophyll bloom duration trend
    # -----------------------------------------------------------------
    props = dict(
        transform=ccrs.PlateCarree(),
        add_colorbar=False,
        robust=True,
        cmap="BrBG",
        center=0,
        levels=15,
    )
    imgs += (chl_bloom_duration_trend.plot.contourf(ax=axs["b"], **props),)
    cbars += (plt.colorbar(imgs[-1], ax=axs["b"], **cbar_props),)

    [axs[k].add_feature(cfeature.LAND.with_scale("50m"), facecolor=LAND_COLOR) for k in axs]
    [axs[k].coastlines(lw=0.5) for k in "ab"]

    props_font = dict(
        fontsize="large",
        fontweight="normal",
        va="center",
        ha="left",
        loc="left",
        bbox=dict(facecolor="white", alpha=1, edgecolor="none", boxstyle="round,pad=0.1"),
    )
    props_right = props_font | dict(x=0.015, y=0.015)

    axs["a"].set_title("$\\bf{a}$ Sea ice duration", **props_right)
    cbars[0].set_label("Duration trend (days$\\,\\cdot\\,$yr$^{-1}$)")

    axs["b"].set_title("$\\bf{b}$ Chlorophyll bloom duration", **props_right)
    cbars[1].set_label("Duration trend (days$\\,\\cdot\\,$yr$^{-1}$)")

    return fig


if __name__ == "__main__":
    data = load_data()
    fig = make_figure(*data)
    fig.savefig(HERE / "fig4-ice_chla_phenology.png", dpi=300, bbox_inches="tight", transparent=True)
