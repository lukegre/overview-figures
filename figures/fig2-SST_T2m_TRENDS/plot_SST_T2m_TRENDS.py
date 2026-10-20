"""Regional SST and 2 m air-temperature trends around southern Greenland.

Three panels: (a) the regional mask, (b) annual regional sea-surface temperature
(SST) from the DMI OI product, and (c) annual 2 m air temperature for two ERA5
regions plus the Narsarsuaq airport station (DMI station 04270, shown as a marker
on the map). Observed annual means are solid lines and Theil-Sen trends are
dashed. SST shading is half the product ``analysis_error``. Significance comes
from the Mann-Kendall test on the trend-free prewhitened series
(``trends.theilsen_mannkendall_tfpw``); trends with p < ``alpha`` are labelled in
bold at the right edge in °C per decade. All settings live in
``config_SST_T2m_TRENDS.yaml``.

Data flow:

    monthly DMI OI SST (``data/sst_dmioi_monthly``) + ocean region mask
      -> regional mean (nearest-neighbour mask) -> annual mean -> Theil-Sen / MK   (b)
    monthly ERA5 t2m (``data/era5_monthly_south_greenland``) + land/ocean/ice polygons
      -> annual mean weighted by days in month -> regional mean                    (c)
    hourly DMI station record (``data/dmi_metobs_narsarsuaq``; raw, not quality controlled)
      -> daily mean -> monthly mean -> annual mean weighted by days in month       (c)
      -> Theil-Sen / MK on the ERA5 + station series

Run from the repository root:

    MPLCONFIGDIR="$TMPDIR/mpl" .venv/bin/python fig2-sst_t2m_trends/plot_SST_T2m_TRENDS.py
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import xarray as xr
import xarray_raster_vector  # noqa: F401 - registers the .rv accessor
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

from greenfjord.analysis import trends
from greenfjord.config import get_script_name, read_config
from greenfjord.data.weather_station_dmi import read_dmi_csv
from greenfjord.viz import set_paper_style
from greenfjord.viz.geo import add_coastline

# paths and names, derived from the script name (plot_<NAME>.py)
HERE = Path(__file__).resolve().parent
NAME = get_script_name(__file__)  # SST_T2m_TRENDS
FIG_STEM = f"fig_{NAME}"  # prefix of the outputs

# config
cfg = read_config(HERE / f"config_{NAME}.yaml")
ana = cfg["analysis"]
plot = cfg["plot"]
output = cfg["output"]
SST_MONTHLY = HERE / cfg["inputs"]["sst_monthly"]
REGION_MASK = HERE / cfg["inputs"]["region_mask"]
ERA5_MONTHLY = HERE / cfg["inputs"]["era5_monthly"]
LAND_OCEAN_ICE = HERE / cfg["inputs"]["land_ocean_ice"]
STATION_CSV = HERE / cfg["inputs"]["station_csv"]

KELVIN = 273.15  # 0 °C in K
YEARS = slice(f"{ana['start_year']}-01-01", f"{ana['end_year']}-12-31")
STATION = ana["station"]
# line colours and IDs of panel (c): ERA5 regions, then the station
T2M_REGIONS = [*ana["t2m_regions"], {"id": STATION["region_id"], "name": STATION["name"], "color": STATION["color"]}]


def fit_trends(temperature: xr.DataArray) -> tuple[xr.DataArray, ...]:
    """Return Theil-Sen slope, intercept and Mann-Kendall (TFPW) p-value of ``temperature`` per region."""
    fit = trends.theilsen_mannkendall_tfpw(temperature, dim="year")
    return (
        fit.sel(parameter="slope", drop=True),
        fit.sel(parameter="intercept", drop=True),
        fit.sel(parameter="pvalue", drop=True),
    )


def load_region_mask() -> xr.DataArray:
    """Load the regional mask and attach its geographic CRS."""
    mask = xr.open_dataarray(REGION_MASK, drop_variables="spatial_ref")
    return mask.rio.write_crs("EPSG:4326")


def load_sst_series(mask: xr.DataArray) -> tuple[xr.DataArray, ...]:
    """Return annual regional SST (°C), uncertainty, trend, Theil-Sen slope and MK p-value."""
    ds = xr.open_zarr(SST_MONTHLY, chunks={}).sel(time=YEARS)
    ds = ds.rename(analysed_st="analysed_sst")

    sst_mask = (
        mask.rename(x="longitude", y="latitude")
        .interp_like(ds, method="nearest")
        .where(lambda x: x.isin([region["id"] for region in ana["sst_regions"]]))
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
    temperature = regional["analysed_sst"] - KELVIN
    uncertainty = regional["analysis_error"] / plot["lines"]["sst"]["uncertainty_divisor"]
    year = temperature["year"]

    # Theil-Sen slope with Mann-Kendall significance on the trend-free prewhitened series
    slope, intercept, p_value = fit_trends(temperature)

    # Refit the shelf regions from refit start_year on; the others keep the full-period fit
    refit = ana["shelf_refit"]
    shelf = dict(region=refit["region_ids"])
    shelf_slope, shelf_intercept, shelf_p = fit_trends(
        temperature.sel(region=refit["region_ids"], year=slice(refit["start_year"], None))
    )
    slope.loc[shelf] = shelf_slope
    intercept.loc[shelf] = shelf_intercept
    p_value.loc[shelf] = shelf_p

    trend = slope * year + intercept
    trend.loc[shelf] = trend.sel(region=refit["region_ids"]).where(year >= refit["start_year"])
    return temperature, uncertainty, trend, slope, p_value


def load_era5_annual() -> xr.DataArray:
    """Return annual ERA5 t2m (°C) per ``t2m_regions`` region, weighted by days in month."""
    t2m = (
        xr.open_dataset(ERA5_MONTHLY)["t2m"]
        .rename({"valid_time": "time"})
        .drop_vars(["expver", "number"], errors="ignore")
    )
    t2m = t2m.assign_coords(longitude=((t2m["longitude"] + 180) % 360) - 180).sel(time=YEARS)
    weights = t2m.time.dt.days_in_month
    region_mask = (
        gpd.read_file(LAND_OCEAN_ICE)
        .rv.to_raster(t2m)
        .where(lambda x: x.isin([region["id"] for region in ana["t2m_regions"]]))
        .rename({"x": "longitude", "y": "latitude"})
        .rename("region")
    )
    annual = (t2m * weights).groupby("time.year").sum() / weights.groupby("time.year").sum()
    return annual.groupby(region_mask).mean(["latitude", "longitude"]).compute() - KELVIN


def load_station_annual() -> xr.DataArray:
    """Return annual mean station air temperature (°C) on a ``year`` dim.

    Hourly (3-hourly before ~2000) values are averaged to daily, then monthly;
    annual means are weighted by days in month.
    """
    hourly = read_dmi_csv(STATION_CSV)["mean_air_temp"]
    monthly = hourly.resample("1D").mean().resample("1MS").mean()
    monthly = monthly[str(ana["start_year"]) : str(ana["end_year"])]
    days = monthly.index.days_in_month
    annual = (monthly * days).groupby(monthly.index.year).sum() / (
        days.to_series(index=monthly.index).groupby(monthly.index.year).sum()
    )
    return xr.DataArray(annual.values, coords={"year": annual.index.values}, dims="year")


def load_t2m_series() -> tuple[xr.DataArray, ...]:
    """Return ERA5 regions plus the station: annual t2m (°C), trend, slope and MK p-value."""
    era5 = load_era5_annual()
    station = load_station_annual().expand_dims(region=[STATION["region_id"]])
    temperature = xr.concat(
        [era5.sel(region=[region["id"] for region in ana["t2m_regions"]]), station.astype(era5.dtype)],
        dim="region",
        join="inner",
    )
    slope, intercept, p_value = fit_trends(temperature)
    trend = slope * temperature["year"] + intercept
    return temperature, trend, slope, p_value


def plot_region_map(ax: plt.Axes, legend_ax: plt.Axes, mask: xr.DataArray) -> None:
    """Draw the ocean regions, the GreenFjord outlines and the station marker; add the legend."""
    m = plot["map"]
    n_regions = len(m["region_colors"])
    shown = mask.where(mask > 0)
    image = ax.contourf(
        shown["x"],
        shown["y"],
        shown,
        levels=np.arange(0.5, n_regions + 1),
        colors=m["region_colors"],
        alpha=m["region_alpha"],
        antialiased=False,
    )
    image.set_rasterized(True)

    # hatch the chosen region on top of its fill
    hatched = m["hatched_region_id"]
    with plt.rc_context({"hatch.color": m["hatch_color"]}):
        ax.contourf(
            shown["x"],
            shown["y"],
            shown,
            levels=[hatched - 0.5, hatched + 0.5],
            colors="none",
            hatches=[m["hatch"]],
        )
    ax.contour(
        shown["x"],
        shown["y"],
        shown,
        levels=np.arange(1.5, n_regions),
        colors=m["boundary_color"],
        linewidths=m["boundary_width"],
        alpha=m["boundary_alpha"],
    )

    # land polygons give a continuous coastline around the mask
    ax.set_xlim(float(mask["x"].min()), float(mask["x"].max()))
    ax.set_ylim(float(mask["y"].min()), float(mask["y"].max()))
    add_coastline(
        ax,
        land_kwargs={
            "facecolor": m["land_color"],
            "edgecolor": m["land_edge_color"],
            "lw": m["land_edge_width"],
            "zorder": m["land_zorder"],
        },
    )

    overlays = gpd.read_file(LAND_OCEAN_ICE).set_index("index")
    overlays.loc[[m["greenfjord_land_index"]]].plot(
        ax=ax,
        color="none",
        edgecolor=m["greenfjord_land_edge_color"],
        linewidth=m["greenfjord_land_edge_width"],
        zorder=20,
    )
    ax.plot(
        STATION["lon"],
        STATION["lat"],
        marker="o",
        ms=m["marker_size"],
        mfc=STATION["color"],
        mec=m["marker_edge_color"],
        mew=m["marker_edge_width"],
        ls="none",
        zorder=30,
    )
    overlays.loc[[m["greenfjord_ocean_index"]]].boundary.plot(
        ax=ax,
        color=m["greenfjord_ocean_edge_color"],
        linewidth=m["greenfjord_ocean_edge_width"],
        linestyle=":",
        zorder=22,
    )

    ax.set_aspect(m["aspect"])
    ax.set_facecolor(m["land_color"])
    ax.set_xlabel("")
    ax.set_ylabel("")
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_title(m["title"], loc="left", pad=m["title_pad"])
    for spine in ax.spines.values():
        spine.set_visible(True)
        spine.set_linewidth(m["spine_width"])
        spine.set_color(m["spine_color"])

    # legend: ocean regions (hatched one marked), GreenFjord land outline, station marker
    region_handles = [
        Patch(
            fc=color,
            ec="none",
            hatch=m["hatch"] if region_id == hatched else None,
            hatchcolor=m["hatch_color"],
            label=label,
        )
        for region_id, (color, label) in enumerate(zip(m["region_colors"], m["region_names"]), start=1)
    ]
    greenfjord_handle = Patch(
        fc=m["land_color"],
        ec=m["greenfjord_land_edge_color"],
        lw=m["greenfjord_land_edge_width"],
        label=m["greenfjord_label"],
    )
    station_handle = Line2D(
        [],
        [],
        marker="o",
        ms=m["legend_marker_size"],
        mfc=STATION["color"],
        mec=m["marker_edge_color"],
        mew=m["marker_edge_width"],
        ls="none",
        label=STATION["name"],
    )
    legend_ax.axis("off")
    legend_ax.legend(
        handles=[*region_handles, greenfjord_handle, station_handle],
        loc="upper left",
        mode="expand",
        borderaxespad=0,
        **m["legend"],
    )


def plot_temperature_lines(
    ax: plt.Axes,
    temperature: xr.DataArray,
    trend: xr.DataArray,
    slope: xr.DataArray,
    p_value: xr.DataArray,
    regions: list[dict],
    *,
    title: str,
    ylabel: str,
    ylim: tuple[float, float],
    uncertainty: xr.DataArray | None = None,
) -> None:
    """Draw annual temperatures, trends and collision-aware slope labels."""
    ln = plot["lines"]
    year = temperature["year"].to_numpy()
    unit = f"{plot['temperature_unit']} {plot['trend_period_label']}⁻¹"
    annotations: list[tuple[float, float, str, bool]] = []

    for region in regions:
        region_id, color = region["id"], region["color"]
        values = temperature.sel(region=region_id).to_numpy()
        fitted = trend.sel(region=region_id).to_numpy()
        ax.plot(year, values, color=color, lw=ln["line_width"], zorder=3)
        ax.plot(
            year,
            fitted,
            color=color,
            ls=ln["trend_line_style"],
            lw=ln["trend_line_width"],
            alpha=ln["trend_line_alpha"],
            zorder=2,
        )
        if uncertainty is not None:
            spread = uncertainty.sel(region=region_id).to_numpy()
            ax.fill_between(
                year,
                values - spread,
                values + spread,
                color=color,
                alpha=ln["uncertainty_alpha"],
                linewidth=0,
                zorder=1,
            )

        significant = float(p_value.sel(region=region_id)) < ana["alpha"]
        rate = float(slope.sel(region=region_id)) * ana["trend_unit_per_years"]
        annotations.append((float(values[-1]), rate, color, significant))

    # Place labels in a single column. When endpoint y-values are too close,
    # stack them vertically while preserving their endpoint-derived order.
    minimum_spacing = (ylim[1] - ylim[0]) * ln["label_min_spacing_fraction"]
    previous_label_y = np.inf
    for final_value, rate, color, significant in sorted(annotations, key=lambda item: item[0], reverse=True):
        label_y = min(final_value, previous_label_y - minimum_spacing)
        ax.annotate(
            f"{plot['slope_label_format'].format(rate)} {unit}",
            xy=(year[-1], label_y),
            xytext=(ln["label_offset_points"], 0),
            textcoords="offset points",
            color=color,
            fontsize=ln["label_font_size"],
            fontweight="bold" if significant else "normal",
            ha="left",
            va="center",
            clip_on=False,
        )
        previous_label_y = label_y

    ax.set_xlim(ana["start_year"], ana["end_year"])
    ax.set_ylim(*ylim)
    ax.set_xticks(ln["xticks"])
    ax.set_xlabel("")
    ax.set_ylabel(ylabel)
    ax.set_title(title, loc="left", pad=ln["title_pad"])
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)


def main() -> None:
    set_paper_style(plot.get("style"))
    mask = load_region_mask()
    sst, sst_uncertainty, sst_trend, sst_slope, sst_p = load_sst_series(mask)
    t2m, t2m_trend, t2m_slope, t2m_p = load_t2m_series()

    fig = plt.figure(figsize=plot["figsize"])
    outer = fig.add_gridspec(1, 2, **plot["outer_grid"])

    left = outer[0].subgridspec(2, 1, **plot["map_grid"])
    ax_map = fig.add_subplot(left[0])
    ax_map.set_anchor("N")
    ax_map_legend = fig.add_subplot(left[1])

    right = outer[1].subgridspec(2, 2, **plot["lines_grid"])
    ax_sst = fig.add_subplot(right[0, 0])
    ax_t2m = fig.add_subplot(right[1, 0], sharex=ax_sst)

    plot_region_map(ax_map, ax_map_legend, mask)
    ylabel = f"Temperature ({plot['temperature_unit']})"
    sst_cfg, t2m_cfg = plot["lines"]["sst"], plot["lines"]["t2m"]
    plot_temperature_lines(
        ax_sst,
        sst,
        sst_trend,
        sst_slope,
        sst_p,
        ana["sst_regions"],
        title=sst_cfg["title"],
        ylabel=ylabel,
        ylim=sst_cfg["ylim"],
        uncertainty=sst_uncertainty,
    )
    plot_temperature_lines(
        ax_t2m,
        t2m,
        t2m_trend,
        t2m_slope,
        t2m_p,
        T2M_REGIONS,
        title=t2m_cfg["title"],
        ylabel=ylabel,
        ylim=t2m_cfg["ylim"],
    )
    ax_sst.tick_params(axis="x", labelbottom=False)
    ax_t2m.set_xlabel(t2m_cfg["xlabel"])
    ax_sst.set_yticks(sst_cfg["yticks"])
    ax_t2m.set_yticks(t2m_cfg["yticks"])

    # Keep the map legend directly below the realised geographic axes.
    fig.canvas.draw()
    map_pos = ax_map.get_position()
    legend_height = plot["legend_height_inches"] / fig.get_figheight()
    legend_gap = plot["legend_gap_inches"] / fig.get_figheight()
    ax_map_legend.set_position([
        map_pos.x0,
        map_pos.y0 - legend_gap - legend_height,
        map_pos.width,
        legend_height,
    ])

    for fmt in output["formats"]:
        # only the PNG is saved with a transparent background
        transparent = bool(output["transparent_png"]) and fmt == "png"
        fig.savefig(HERE / f"{FIG_STEM}.{fmt}", dpi=output["dpi"], bbox_inches="tight", transparent=transparent)


if __name__ == "__main__":
    main()
