"""Annual SST and 2 m air-temperature trends for the GreenFjord domain.

This is the line-plot counterpart to ``plot_sst_t2m_trends.py``. It combines:

    (a) the regional mask;
    (b) annual regional sea-surface temperature (SST), 1982--2021; and
    (c) annual regional ERA5 2 m air temperature, 1982--2021.

Observed annual means are solid lines and Theil-Sen trends are dashed.
SST shading shows half the product ``analysis_error``, following the prototype
in ``examples/line_plots.ipynb``. Significance comes from the Mann-Kendall test
on trend-free prewhitened series (``trends.theilsen_mannkendall_tfpw``), and
trends with p < 0.05 are annotated at the right edge in degrees Celsius per
decade.

Run from the repository root with:

    MPLCONFIGDIR="$TMPDIR/mpl" uv run python \
        fig2-sst_t2m_trends/plot_sst_t2m_trends_lines.py
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import xarray as xr
import xarray_raster_vector  # noqa: F401 - registers the .rv accessor
from matplotlib.patches import Patch

from greenfjord.analysis import trends

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"

SST_ZARR = (
    DATA / "cmems_obs_si_arc_phy_my_L4-DMIOI_P1D-m_multi-vars_54.48W-35.53W_"
    "58.00N-67.50N_1982-01-01-2024-12-31.monthly.zarr"
)
ERA5_ZARR = DATA / "era5-daily-greenfjord.zarr"
REGION_MASK = DATA / "regions_mask.nc"
ERA5_REGIONS = DATA / "era5-land-ocean-ice.gpkg"
OUT_PNG = HERE / "fig2-sst_t2m_trends_lines.png"
OUT_PDF = HERE / "fig2-sst_t2m_trends_lines.pdf"

START_YEAR = 1982
END_YEAR = 2021

# Region IDs come from data/regions_mask.nc.
SST_REGIONS = [
    (1, "Oceanic", "C0"),
    (2, "Southwest", "C1"),
    (4, "South Eastern", "C3"),
]

# Raster values follow the row order in data/era5-land-ocean-ice.gpkg:
# land=1, ocean=2, ice=3.
T2M_REGIONS = [
    (1, "GreenFjord", "0.55"),
    (2, "Southwest", "C1"),
    (3, "Ice sheet", "C4"),
]

LAND_COLOR = "0.95"


def set_paper_style() -> None:
    """Apply a compact, publication-oriented Matplotlib style."""
    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.size": 8,
        "axes.titlesize": 8.5,
        "axes.labelsize": 8,
        "axes.linewidth": 0.5,
        "axes.titleweight": "normal",
        "xtick.labelsize": 7.2,
        "ytick.labelsize": 7.2,
        "xtick.major.size": 3,
        "ytick.major.size": 3,
        "xtick.major.width": 0.6,
        "ytick.major.width": 0.6,
        "legend.fontsize": 7.2,
        "legend.frameon": False,
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "savefig.facecolor": "white",
        "savefig.dpi": 300,
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
    })


def load_region_mask() -> xr.DataArray:
    """Load the cached regional mask and attach its geographic CRS."""
    mask = xr.open_dataarray(REGION_MASK, drop_variables="spatial_ref")
    return mask.rio.write_crs("EPSG:4326")


def load_sst_series(mask: xr.DataArray) -> tuple[xr.DataArray, ...]:
    """Return annual SST, uncertainty, trend, Theil-Sen slope and MK p-value."""
    ds = xr.open_zarr(SST_ZARR, chunks={}).sel(
        time=slice(f"{START_YEAR}-01-01", f"{END_YEAR}-12-31")
    )
    ds = ds.rename({"analysed_st": "analysed_sst"} if "analysed_st" in ds.data_vars else {})

    sst_mask = (
        mask
        .rename(x="longitude", y="latitude")
        .interp_like(ds, method="nearest")
        .where(lambda x: x.isin([region[0] for region in SST_REGIONS]))
        .rename("region")
    )
    regional = (
        ds[["analysed_sst", "analysis_error"]]
        .groupby(sst_mask)
        .mean(dim=["latitude", "longitude"])
        .groupby("time.year")
        .mean("time")
        .compute()
    )

    temperature = regional["analysed_sst"] - 273.15
    uncertainty = regional["analysis_error"] / 2
    year = temperature["year"]

    # Theil-Sen slope with Mann-Kendall significance on the trend-free
    # prewhitened series. Both are rank-based, so the inverse-error-variance
    # year weighting used by the least-squares version no longer applies.
    fit = trends.theilsen_mannkendall_tfpw(temperature, dim="year")
    slope = fit.sel(parameter="slope", drop=True)
    intercept = fit.sel(parameter="intercept", drop=True)
    p_value = fit.sel(parameter="pvalue", drop=True)

    # Fit the two shelf-region trends only over 1990--2021. The Oceanic
    # region retains the complete 1982--2021 trend used in the notebook.
    shelf_regions = [2, 4]
    shelf_temperature = temperature.sel(region=shelf_regions, year=slice(1982, None))
    shelf_fit = trends.theilsen_mannkendall_tfpw(shelf_temperature, dim="year")
    slope.loc[dict(region=shelf_regions)] = shelf_fit.sel(parameter="slope", drop=True)
    intercept.loc[dict(region=shelf_regions)] = shelf_fit.sel(parameter="intercept", drop=True)
    p_value.loc[dict(region=shelf_regions)] = shelf_fit.sel(parameter="pvalue", drop=True)

    trend = slope * year + intercept
    trend.loc[dict(region=shelf_regions)] = trend.sel(region=shelf_regions).where(year >= 1982)
    return temperature, uncertainty, trend, slope, p_value


def load_t2m_series() -> tuple[xr.DataArray, ...]:
    """Return annual ERA5 t2m, its trend, Theil-Sen slope and MK p-value."""
    t2m = xr.open_zarr(ERA5_ZARR, chunks={})["t2m"].sel(
        time=slice(f"{START_YEAR}-01-01", f"{END_YEAR}-12-31")
    )
    region_mask = (
        gpd
        .read_file(ERA5_REGIONS)
        .rv.to_raster(t2m)
        .where(lambda x: x.isin([region[0] for region in T2M_REGIONS]))
        .rename({"x": "longitude", "y": "latitude"})
        .rename("region")
    )
    temperature = (
        t2m
        .groupby("time.year")
        .mean("time")
        .groupby(region_mask)
        .mean(["latitude", "longitude"])
        .compute()
        - 273.15
    )
    year = temperature["year"]
    fit = trends.theilsen_mannkendall_tfpw(temperature, dim="year")
    slope = fit.sel(parameter="slope", drop=True)
    intercept = fit.sel(parameter="intercept", drop=True)
    p_value = fit.sel(parameter="pvalue", drop=True)
    trend = slope * year + intercept
    return temperature, trend, slope, p_value


def plot_region_map(
    ax: plt.Axes,
    legend_ax: plt.Axes,
    mask: xr.DataArray,
) -> None:
    """Draw the ocean regions and land/ocean/ice study-area overlays."""
    shown = mask.where(mask > 0)
    image = ax.contourf(
        shown["x"],
        shown["y"],
        shown,
        levels=np.arange(0.5, 5),
        colors=["C0", "C1", "C2", "C3"],
        alpha=0.8,
        antialiased=False,
    )
    image.set_rasterized(True)
    ax.contour(
        shown["x"],
        shown["y"],
        shown,
        levels=[1.5, 2.5, 3.5],
        colors="white",
        linewidths=0.35,
        alpha=0.9,
    )

    # Add the Natural Earth land polygons used by the project's standard map
    # helper. Their edges provide a continuous coastline around the mask.
    from greenfjord.viz.geo import add_coastline

    ax.set_xlim(float(mask["x"].min()), float(mask["x"].max()))
    ax.set_ylim(float(mask["y"].min()), float(mask["y"].max()))
    add_coastline(
        ax,
        land_kwargs={
            "facecolor": LAND_COLOR,
            "edgecolor": "0.2",
            "lw": 0.4,
            "zorder": 10,
        },
    )

    overlays = gpd.read_file(ERA5_REGIONS).set_index("index")
    overlays.loc[["land"]].plot(
        ax=ax,
        color="none",
        edgecolor="0.15",
        linewidth=1.0,
        zorder=20,
    )
    overlays.loc[["ice"]].plot(
        ax=ax,
        color=plt.cm.tab10(4),
        edgecolor="#333333",
        linewidth=1.0,
        linestyle=":",
        alpha=0.65,
        zorder=21,
    )
    overlays.loc[["ocean"]].boundary.plot(
        ax=ax,
        color="#333333",
        linewidth=1.0,
        linestyle=":",
        zorder=22,
    )

    ax.set_xlim(float(mask["x"].min()), float(mask["x"].max()))
    ax.set_ylim(float(mask["y"].min()), float(mask["y"].max()))
    ax.set_aspect(2)
    ax.set_facecolor(LAND_COLOR)
    ax.set_xlabel("")
    ax.set_ylabel("")
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_title(r"$\bf{a}$  Regional mask", loc="left", pad=3)
    for spine in ax.spines.values():
        spine.set_visible(True)
        spine.set_linewidth(0.5)
        spine.set_color("0.2")

    legend_ax.axis("off")
    legend_ax.legend(
        handles=[
            Patch(fc="C0", ec="none", label="Oceanic"),
            Patch(fc="C1", ec="none", label="Southwest"),
            Patch(fc="C2", ec="none", label="Central western"),
            Patch(fc="C3", ec="none", label="South Eastern"),
            Patch(
                fc="C4",
                ec="#333333",
                lw=1,
                ls=":",
                label="Ice sheet",
            ),
            Patch(fc=LAND_COLOR, ec="0.15", lw=1, label="GreenFjord"),
        ],
        loc="upper left",
        ncol=2,
        mode="expand",
        borderaxespad=0,
        handlelength=2.0,
        handleheight=1.3,
        handletextpad=0.45,
        columnspacing=0.8,
        labelspacing=0.65,
    )


def plot_temperature_lines(
    ax: plt.Axes,
    temperature: xr.DataArray,
    trend: xr.DataArray,
    slope: xr.DataArray,
    p_value: xr.DataArray,
    regions: list[tuple[int, str, str]],
    *,
    title: str,
    ylabel: str,
    ylim: tuple[float, float],
    uncertainty: xr.DataArray | None = None,
    zero_line: bool = False,
) -> None:
    """Draw annual temperatures, trends and collision-aware slope labels."""
    year = temperature["year"].to_numpy()
    annotations: list[tuple[float, float, str, bool]] = []

    for region_id, _name, color in regions:
        values = temperature.sel(region=region_id).to_numpy()
        fitted = trend.sel(region=region_id).to_numpy()
        ax.plot(year, values, color=color, lw=1.6, zorder=3)
        ax.plot(
            year,
            fitted,
            color=color,
            ls="--",
            lw=0.9,
            alpha=0.9,
            zorder=2,
        )
        if uncertainty is not None:
            spread = uncertainty.sel(region=region_id).to_numpy()
            ax.fill_between(
                year,
                values - spread,
                values + spread,
                color=color,
                alpha=0.1,
                linewidth=0,
                zorder=1,
            )

        significant = float(p_value.sel(region=region_id)) < 0.05
        rate = float(slope.sel(region=region_id)) * 10
        final_value = float(values[-1])
        annotations.append((final_value, rate, color, significant))

    # Place labels in a single column. When endpoint y-values are too close,
    # stack them vertically while preserving their endpoint-derived order.
    minimum_spacing = (ylim[1] - ylim[0]) * 0.075
    previous_label_y = np.inf
    for final_value, rate, color, significant in sorted(
        annotations,
        key=lambda item: item[0],
        reverse=True,
    ):
        label_y = min(final_value, previous_label_y - minimum_spacing)
        ax.annotate(
            f"{rate:+.2f} °C dec⁻¹",
            xy=(year[-1], label_y),
            xytext=(5, 0),
            textcoords="offset points",
            color=color,
            fontsize=7.2,
            fontweight="bold" if significant else "normal",
            ha="left",
            va="center",
            clip_on=False,
        )
        previous_label_y = label_y

    if zero_line:
        ax.axhline(0, color="0.25", lw=0.5, alpha=0.35, zorder=0)

    ax.set_xlim(START_YEAR, END_YEAR)
    ax.set_ylim(*ylim)
    ax.set_xticks([1982, 1990, 2000, 2010, 2020])
    ax.set_xlabel("")
    ax.set_ylabel(ylabel)
    ax.set_title(title, loc="left", pad=3)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)


def main() -> None:
    set_paper_style()
    mask = load_region_mask()
    sst, sst_uncertainty, sst_trend, sst_slope, sst_p = load_sst_series(mask)
    t2m, t2m_trend, t2m_slope, t2m_p = load_t2m_series()

    fig = plt.figure(figsize=(8, 3.4))
    outer = fig.add_gridspec(
        1,
        2,
        width_ratios=[1.02, 1.9],
        wspace=0.18,
        left=0.045,
        right=0.99,
        top=0.96,
        bottom=0.105,
    )

    left = outer[0].subgridspec(2, 1, height_ratios=[1, 0.2], hspace=0.14)
    ax_map = fig.add_subplot(left[0])
    ax_map.set_anchor("N")
    ax_map_legend = fig.add_subplot(left[1])

    right = outer[1].subgridspec(
        2,
        2,
        width_ratios=[1, 0.44],
        height_ratios=[1, 1],
        wspace=0.08,
        hspace=0.24,
    )
    ax_sst = fig.add_subplot(right[0, 0])
    ax_t2m = fig.add_subplot(right[1, 0], sharex=ax_sst)

    plot_region_map(ax_map, ax_map_legend, mask)
    plot_temperature_lines(
        ax_sst,
        sst,
        sst_trend,
        sst_slope,
        sst_p,
        SST_REGIONS,
        title=r"$\bf{b}$  Sea-surface temperature",
        ylabel="Temperature (°C)",
        ylim=(0, 7),
        uncertainty=sst_uncertainty,
    )
    plot_temperature_lines(
        ax_t2m,
        t2m,
        t2m_trend,
        t2m_slope,
        t2m_p,
        T2M_REGIONS,
        title=r"$\bf{c}$  2 m air temperature",
        ylabel="Temperature (°C)",
        ylim=(-12, 6),
        zero_line=False,
    )
    ax_sst.tick_params(axis="x", labelbottom=False)
    ax_t2m.set_xlabel("Year")
    ax_sst.set_yticks([0, 2, 4, 6])
    ax_t2m.set_yticks(np.arange(-8, 8, 4))

    # Keep the map legend directly below the realised geographic axes.
    fig.canvas.draw()
    map_pos = ax_map.get_position()
    legend_height = 0.65 / fig.get_figheight()
    legend_gap = 0.1 / fig.get_figheight()
    ax_map_legend.set_position([
        map_pos.x0,
        map_pos.y0 - legend_gap - legend_height,
        map_pos.width,
        legend_height,
    ])

    fig.savefig(OUT_PNG, dpi=300, bbox_inches="tight", transparent=True)
    fig.savefig(OUT_PDF, bbox_inches="tight")


if __name__ == "__main__":
    main()
