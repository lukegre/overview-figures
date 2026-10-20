"""Tidal-flat growth in a Greenland fjord and its glacial sediment drivers.

Panels (a, b): two Landsat maps of the fjord with the tidal flats outlined.
Panel (c): normalised tidal-plain area vs. year, coloured by tide height, with a
           bootstrapped linear fit and its confidence band.
Panel (d): daily ablation rate vs. daily turbidity (Ian Delaney's 2023 sensors).
Panel (e): Jespersen Bræ freshwater discharge (MAR / Mankoff et al. 2020): daily
           discharge plus the annual total and its linear trend.

Data flow: the cleaned Landsat netCDF (tidal-flat masks), the tide-height table,
the two 2023 logger files and the MAR discharge CSV are read from ``data/``. The
RGB + SWIR background of panels (a, b) is fetched from the Microsoft Planetary
Computer for the two map dates (snapped to the nearest netCDF scene) and cached
in ``cache/``. Panels (c, d, e) share one OLS + percentile-bootstrap recipe.
All settings live in ``config_SEDIMENT_DELIVERY.yaml``.

The scene cache filename encodes the scene date, bbox and max cloud cover. It
cannot encode the EPSG / resolution or the netCDF grid, so delete ``cache/``
after changing those (see README).

Run from the repository root:

    MPLCONFIGDIR="$TMPDIR/mpl" .venv/bin/python fig14_SEDIMENT_DELIVERY/plot_SEDIMENT_DELIVERY.py
"""

from __future__ import annotations

import math
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import xarray as xr
from matplotlib.lines import Line2D

from greenfjord.config import get_script_name, read_config
from greenfjord.viz import set_paper_style

# paths and names, derived from the script name (plot_<NAME>.py)
HERE = Path(__file__).resolve().parent
NAME = get_script_name(__file__)  # SEDIMENT_DELIVERY
FIG_STEM = f"fig_{NAME}"  # prefix of the figure outputs

# config
cfg = read_config(HERE / f"config_{NAME}.yaml")
ana = cfg["analysis"]
plot = cfg["plot"]
panels = plot["panels"]
output = cfg["output"]
reg = ana["regression"]
NETCDF = HERE / cfg["inputs"]["netcdf"]
AREA_CSV = HERE / cfg["inputs"]["area_csv"]
TURBIDITY = HERE / cfg["inputs"]["turbidity"]
ABLATOMETER = HERE / cfg["inputs"]["ablatometer"]
DISCHARGE = HERE / cfg["inputs"]["discharge"]

RGB_BANDS = ["red", "green", "blue"]
STAC_URL = "https://planetarycomputer.microsoft.com/api/stac/v1"


# =============================================================================
# Landsat scenes (Planetary Computer) for panels (a, b)
# =============================================================================
def scene_cache_path(scene_time):
    """Cache file of one scene; the name holds every setting that changes its content."""
    lc = ana["landsat"]
    bbox = "_".join(str(v) for v in lc["bbox"])
    day = scene_time.strftime("%Y-%m-%d")
    return HERE / "cache" / f"landsat_scene-{day}-bbox{bbox}-cc{lc['max_cloud_cover']}.nc"


def fetch_scene(ds, scene_time):
    """Download the Landsat C2 L2 scene nearest `scene_time` (RGB + SWIR) on the netCDF grid."""
    import planetary_computer
    import pystac_client
    import stackstac

    lc = ana["landsat"]
    day = pd.Timestamp(scene_time).normalize()
    window = f"{(day - pd.Timedelta(days=1)).date()}/{(day + pd.Timedelta(days=1)).date()}"
    items = (
        pystac_client.Client.open(STAC_URL, modifier=planetary_computer.sign_inplace)
        .search(
            collections=["landsat-c2-l2"],
            bbox=lc["bbox"],
            datetime=window,
            query={"eo:cloud_cover": {"lt": lc["max_cloud_cover"]}},
        )
        .item_collection()
    )
    da = stackstac.stack(
        items,
        assets=RGB_BANDS + ["swir16"],
        epsg=lc["epsg"],
        bounds_latlon=lc["bbox"],
        chunksize=2048,
        resolution=lc["resolution_m"],
    )
    # acquisition closest to the tidal-plain scene time, aligned to the exact netCDF grid
    da = da.sel(time=pd.Timestamp(scene_time), method="nearest")
    da = da.reindex(x=ds.x, y=ds.y, method="nearest", tolerance=20)

    scene = xr.Dataset({b: da.sel(band=b, drop=True) for b in RGB_BANDS + ["swir16"]})
    # stackstac attaches non-serialisable coords / attrs; keep only x, y and drop attrs
    scene = scene.drop_vars([c for c in scene.coords if c not in ("x", "y")], errors="ignore")
    scene.attrs = {}
    for name in scene.variables:
        scene[name].attrs = {}
    return scene


def install_stackstac_shims():
    """Make stackstac 0.5.0 work with NumPy 2 / pandas 3 (narrow wrappers, same results)."""
    orig_can_cast = np.can_cast
    orig_to_datetime = pd.to_datetime

    def can_cast(from_, to, *a, **k):  # NEP-50: can_cast rejects python scalars
        if isinstance(from_, (int, float, complex)):
            from_ = np.min_scalar_type(from_)
        return orig_can_cast(from_, to, *a, **k)

    def to_datetime(*a, **k):  # pandas 3 removed the infer_datetime_format kwarg
        k.pop("infer_datetime_format", None)
        return orig_to_datetime(*a, **k)

    np.can_cast = can_cast
    pd.to_datetime = to_datetime


def get_scene(ds, times, requested_date):
    """Return (rgb, swir, index) for the netCDF scene nearest `requested_date`, cached."""
    idx = int(np.argmin(np.abs(times - pd.Timestamp(requested_date))))
    cache_file = scene_cache_path(times[idx])
    if cache_file.exists():
        scene = xr.open_dataset(cache_file, engine="h5netcdf")
    else:
        install_stackstac_shims()
        scene = fetch_scene(ds, times[idx])
        cache_file.parent.mkdir(exist_ok=True)
        scene.to_netcdf(cache_file, engine="h5netcdf")
    rgb = scene[RGB_BANDS].to_array("band").transpose("y", "x", "band").values
    return rgb, scene["swir16"], idx


# =============================================================================
# data loading
# =============================================================================
def load_area():
    """Per-scene table of tide-normalised tidal-plain area (panel c)."""
    a = ana["area"]
    return pd.read_csv(AREA_CSV).dropna(subset=[a["x_column"], a["y_column"]])


def load_ablation():
    """Daily ablation rate [cm/day] paired with daily mean turbidity [FNU] (panel d).

    The ablatometer logs the distance to the ice surface in mm every 3 h; the
    distance shrinks as the surface lowers, so the daily ablation rate is the
    negated day-to-day difference of the daily mean (mm -> cm). Only days where
    both sensors report are kept.
    """
    a = ana["ablation"]
    abl = pd.read_csv(ABLATOMETER, parse_dates=["TIMESTAMP"], index_col="TIMESTAMP")
    turb = pd.read_csv(TURBIDITY, parse_dates=["TIMESTAMP"], index_col="TIMESTAMP")
    rate = -abl[a["ablation_column"]].resample("D").mean().diff() / a["mm_per_cm"]
    daily_turb = turb[a["turbidity_column"]].resample("D").mean()
    return pd.concat([rate.rename("ablation"), daily_turb.rename("turbidity")], axis=1).dropna()


def load_discharge():
    """Daily MAR discharge [m³/s] and the annual total [10⁶ m³] for full years (panel e)."""
    d = ana["discharge"]
    df = pd.read_csv(DISCHARGE, index_col=0)
    time = pd.to_datetime(df["time"], format=d["date_format"])
    daily = pd.Series(df[d["column"]].to_numpy(float), index=time).sort_index()

    totals = daily.resample("YS").sum() * d["seconds_per_day"] / d["volume_unit_m3"]
    counts = daily.resample("YS").count()
    annual = totals[counts >= d["min_days_per_year"]]
    daily = daily[daily.index.year.isin(annual.index.year)]
    return daily, annual


# =============================================================================
# shared helpers for the line / scatter panels (c, d, e)
# =============================================================================
def style_axis(ax):
    """No top/right spines, thin grey spines, inward ticks."""
    st = plot["axis"]
    ax.spines[["top", "right"]].set_visible(False)
    for spine in ax.spines.values():
        spine.set_linewidth(st["spine_width"])
        spine.set_color(st["spine_color"])
    ax.tick_params(direction="in", width=st["tick_width"], length=st["tick_length"])


def add_fit(ax, x, y, xg=None, xg_plot=None):
    """OLS line + bootstrap confidence band; returns (slope, r2, pval).

    ``xg`` is the grid the fit is evaluated on (in the units of ``x``); pass
    ``xg_plot`` when the axis plots something else, e.g. panel (e) fits against
    year numbers but draws against datetimes.
    """
    fit = plot["fit"]
    if xg is None:
        xg = np.linspace(x.min(), x.max(), reg["n_grid"])
    if xg_plot is None:
        xg_plot = xg
    slope, intercept, r2, pval = _ols(x, y)
    lo, hi = _bootstrap_band(x, y, xg, reg["n_boot"], reg["ci"], reg["seed"])
    ax.fill_between(xg_plot, lo, hi, color=fit["band_color"], alpha=fit["band_alpha"], zorder=1)
    ax.plot(xg_plot, intercept + slope * xg, color=fit["line_color"], linewidth=fit["line_width"], zorder=2)
    return slope, r2, pval


def add_fit_stats(ax, r2, pval, loc=(0.05, 0.03), va="bottom", ha="left"):
    """The R²/p-value box used identically in panels (c), (d) and (e)."""
    fit = plot["fit"]
    ax.text(
        loc[0],
        loc[1],
        fit["stats_text"].format(r2=r2, pval=pval),
        transform=ax.transAxes,
        fontsize=fit["stats_fontsize"],
        ha=ha,
        va=va,
        bbox=dict(boxstyle="round,pad=0.3", facecolor="white", alpha=fit["stats_box_alpha"], edgecolor="none"),
        zorder=4,
    )


# =============================================================================
# panels
# =============================================================================
def plot_map(ax, ds, index, title, scene=None):
    """Draw one fjord map: RGB land + SWIR water (or a flat fallback) + flats outline."""
    p = panels["maps"]
    flats = ds["tidal_flats"].isel(time=index).values.astype(float)
    ocean = np.isfinite(ds["rgb"].isel(time=index, band=0).values)  # fjord footprint

    if scene is not None:
        rgb, swir = scene
        # RGB true-colour base (land + fjord); NaN (scene edge) -> white
        disp = np.clip(rgb / p["rgb_vmax"], 0, 1)
        disp = np.where(np.isfinite(disp), disp, 1.0)
        ax.imshow(disp, origin="upper", interpolation="nearest")

        # SWIR over the ocean only (subtract the ocean median, clip >= 0)
        sw = np.where(ocean, np.asarray(swir, float), np.nan)
        sw = np.clip(sw - np.nanmedian(sw), 0, None)
        sw = np.where(ocean, sw, np.nan)
        ax.imshow(
            sw,
            origin="upper",
            interpolation="nearest",
            cmap=p["swir_cmap"],
            vmin=p["swir_vmin"],
            vmax=p["swir_vmax"],
        )
    else:
        # fallback: flat land + water / flats colours (no imagery fetched)
        ax.set_facecolor(p["land_fallback_color"])
        field = np.full(flats.shape, np.nan)
        field[ocean] = p["swir_vmin"]
        field[flats > 0.5] = p["swir_vmax"]
        ax.imshow(
            field,
            origin="upper",
            interpolation="nearest",
            cmap=p["swir_cmap"],
            vmin=p["swir_vmin"],
            vmax=p["swir_vmax"],
        )

    ax.contour(flats, levels=[0.5], colors=[p["contour_color"]], linewidths=p["contour_linewidth"])
    ax.set_title(title, loc="center", fontsize=plot["title_fontsize"], ha="left", x=p["title_x"])
    ax.set_xticklabels([])
    ax.set_yticklabels([])
    ax.tick_params(length=p["tick_length"])


def plot_area_scatter(ax, df):
    """Normalised tidal-plain area vs. year, coloured by tide height (panel c)."""
    p = panels["scatter"]
    a = ana["area"]
    x = df[a["x_column"]].to_numpy(float)
    y = df[a["y_column"]].to_numpy(float)
    hue = df[a["hue_column"]].to_numpy(float)

    vmin, vmax = hue.min(), hue.max()
    ax.scatter(
        x,
        y,
        c=hue,
        cmap=p["cmap"],
        vmin=vmin,
        vmax=vmax,
        s=p["marker_size"],
        edgecolor=p["edgecolor"],
        linewidth=p["edgewidth"],
        alpha=p["marker_alpha"],
        zorder=3,
    )

    _, r2, pval = add_fit(ax, x, y)
    add_fit_stats(ax, r2, pval)
    print(f"(c) tidal-plain area vs. year: n={len(x)}, R2={r2:.3f}, p={pval:.3f}")

    # x axis: days since the first year -> calendar years
    year0 = df[a["year_column"]].min()
    tick0 = (p["xtick_start_year"] - year0) * a["days_per_year"]
    ticks = np.arange(tick0, p["xtick_stop_days"], a["days_per_year"] * p["tick_step_years"])
    ax.set_xticks(ticks)
    ax.set_xticklabels((ticks / a["days_per_year"] + year0).astype(int))
    ax.set_xlim(p["xlim_pad_days"][0], x.max() + p["xlim_pad_days"][1])
    ax.set_xlabel(p["xlabel"])
    ax.set_ylabel(p["ylabel"])

    # discrete legend at regular tide-height steps
    step = p["legend_step"]
    levels = np.arange(np.ceil(vmin / step) * step, np.floor(vmax / step) * step + step / 100, step)
    cmap = plt.get_cmap(p["cmap"])
    handles = [
        Line2D(
            [0],
            [0],
            marker="o",
            linestyle="",
            markerfacecolor=cmap((lv - vmin) / (vmax - vmin)),
            markeredgecolor=p["edgecolor"],
            markeredgewidth=p["edgewidth"],
            markersize=p["legend_marker_size"],
            label=f"{lv:.1f}",
        )
        for lv in levels
    ]
    ax.legend(
        handles=handles,
        title=p["legend_title"],
        loc="upper left",
        frameon=True,
        fontsize="small",
        labelspacing=0.5,
        handletextpad=0.3,
        columnspacing=0.5,
        title_fontsize="medium",
        ncol=p["legend_ncol"],
    )
    style_axis(ax)


def plot_ablation_scatter(ax, df):
    """Daily ablation rate against daily turbidity, with the shared OLS fit (panel d)."""
    p = panels["ablation"]
    x = df["turbidity"].to_numpy(float)
    y = df["ablation"].to_numpy(float)

    ax.scatter(
        x,
        y,
        color=plot["colors"]["blue"],
        s=p["marker_size"],
        edgecolor=p["edgecolor"],
        linewidth=p["edgewidth"],
        alpha=p["marker_alpha"],
        zorder=3,
    )
    _, r2, pval = add_fit(ax, x, y)
    add_fit_stats(ax, r2, pval, loc=p["stats_loc"], ha="right")
    print(f"(d) ablation vs. turbidity: n={len(x)} daily pairs, R2={r2:.3f}, p={pval:.3f}")

    ax.set_xlabel(p["xlabel"])
    ax.set_ylabel(p["ylabel"])
    ax.margins(x=p["margins"]["x"], y=p["margins"]["y"])
    style_axis(ax)


def plot_discharge_series(ax, daily, annual):
    """Daily discharge (left axis) + annual total and its trend (right axis), panel (e)."""
    p = panels["discharge"]
    blue, orange = plot["colors"]["blue"], plot["colors"]["orange"]
    fit = plot["fit"]
    years = annual.index.year.to_numpy(float)

    ax.plot(
        daily.index,
        daily.to_numpy(float),
        color=blue,
        linewidth=p["daily_width"],
        alpha=p["daily_alpha"],
        zorder=2,
    )
    ax.set_xlabel(p["xlabel"])
    ax.set_ylabel(p["ylabel"], color=blue)
    ax.tick_params(axis="y", colors=blue)
    ax.set_ylim(0, daily.max() * p["headroom"])

    ticks = [pd.Timestamp(f"{yr:.0f}-01-01") for yr in years[p["first_tick_index"] : -1 : p["tick_step_years"]]]
    ax.set_xticks(ticks)
    ax.set_xticklabels([t.year for t in ticks])
    ax.set_xlim(daily.index.min(), daily.index.max())

    # annual totals share the x axis but need their own (volume) scale
    ax2 = ax.twinx()
    mid_year = [pd.Timestamp(f"{yr:.0f}-07-01") for yr in years]
    ax2.plot(mid_year, annual.to_numpy(float), color=orange, linewidth=p["annual_width"], zorder=3)

    # trend through the annual totals: fitted on year numbers, drawn on dates
    _, r2, pval = add_fit(ax2, years, annual.to_numpy(float), xg=years, xg_plot=mid_year)
    print(f"(e) annual discharge trend: n={len(years)} years, R2={r2:.3f}, p={pval:.3f}")

    ax2.set_ylabel(p["ylabel_annual"], color=orange)
    ax2.tick_params(axis="y", colors=orange)
    ax2.set_ylim(0, annual.max() * p["headroom"])

    add_fit_stats(ax, r2, pval, loc=p["stats_loc"], va="top")

    style_axis(ax)
    style_axis(ax2)
    ax2.spines["right"].set_visible(True)  # the annual axis needs its own spine

    labels = p["legend_labels"]
    handles = [
        Line2D([0], [0], color=blue, lw=p["legend_daily_width"], label=labels[0]),
        Line2D([0], [0], color=orange, lw=p["annual_width"], label=labels[1]),
        Line2D([0], [0], color=fit["line_color"], lw=fit["line_width"], label=labels[2]),
    ]
    ax.legend(handles=handles, loc="upper right", frameon=False, fontsize="small")


# =============================================================================
# numeric helpers (no scipy / statsmodels dependency)
# =============================================================================
def _ols(x, y):
    """Simple linear regression -> slope, intercept, R^2, two-sided p(slope)."""
    n = len(x)
    xbar, ybar = x.mean(), y.mean()
    sxx = np.sum((x - xbar) ** 2)
    slope = np.sum((x - xbar) * (y - ybar)) / sxx
    intercept = ybar - slope * xbar
    resid = y - (intercept + slope * x)
    ss_res = np.sum(resid**2)
    ss_tot = np.sum((y - ybar) ** 2)
    r2 = 1 - ss_res / ss_tot
    df = n - 2
    se = math.sqrt(ss_res / df / sxx)
    t = slope / se
    return slope, intercept, r2, _t_two_sided_p(t, df)


def _bootstrap_band(x, y, xg, n_boot, ci, seed):
    """Percentile bootstrap of the regression line, evaluated on grid xg."""
    rng = np.random.default_rng(seed)
    n = len(x)
    preds = np.empty((n_boot, xg.size))
    for i in range(n_boot):
        idx = rng.integers(0, n, n)
        b, a = np.polyfit(x[idx], y[idx], 1)
        preds[i] = a + b * xg
    half = (100 - ci) / 2
    return np.percentile(preds, half, axis=0), np.percentile(preds, 100 - half, axis=0)


def _t_two_sided_p(t, df):
    """Two-sided p-value of Student-t via the regularised incomplete beta."""
    return _betai(df / 2.0, 0.5, df / (df + t * t))


def _betai(a, b, x):
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    lbeta = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
    bt = math.exp(lbeta + a * math.log(x) + b * math.log(1 - x))
    if x < (a + 1) / (a + b + 2):
        return bt * _betacf(a, b, x) / a
    return 1.0 - bt * _betacf(b, a, 1 - x) / b


def _betacf(a, b, x):
    MAXIT, EPS, FPMIN = 300, 3e-16, 1e-300
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    d = 1.0 / (FPMIN if abs(d) < FPMIN else d)
    h = d
    for m in range(1, MAXIT + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        d = FPMIN if abs(d) < FPMIN else d
        c = 1.0 + aa / c
        c = FPMIN if abs(c) < FPMIN else c
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        d = FPMIN if abs(d) < FPMIN else d
        c = 1.0 + aa / c
        c = FPMIN if abs(c) < FPMIN else c
        d = 1.0 / d
        de = d * c
        h *= de
        if abs(de - 1.0) < EPS:
            break
    return h


# =============================================================================
# main
# =============================================================================
def main() -> None:
    set_paper_style(plot.get("style"))

    ds = xr.open_dataset(NETCDF, engine="h5netcdf")
    times = pd.to_datetime(ds["time"].values)
    area_df = load_area()
    abl_df = load_ablation()
    daily_q, annual_q = load_discharge()

    # nearest netCDF scenes for the two map dates, with fetched (cached) imagery
    mp = panels["maps"]
    dates = [ana["maps"]["left_date"], ana["maps"]["right_date"]]
    scenes, idxs = [], []
    for date in dates:
        idx = int(np.argmin(np.abs(times - pd.Timestamp(date))))
        scene = None
        if ana["landsat"]["enabled"]:
            try:
                rgb, swir, idx = get_scene(ds, times, date)
                scene = (rgb, swir)
            except Exception as exc:  # network / deps unavailable -> flat-colour fallback
                print(f"WARNING: scene fetch failed ({exc}); using flat-colour maps")
        scenes.append(scene)
        idxs.append(idx)

    fig = plt.figure(figsize=plot["figsize"])
    m = plot["margins"]
    # two rows: maps + area scatter on top, the sensor/discharge panels below
    outer = fig.add_gridspec(
        2,
        1,
        height_ratios=plot["row_height_ratios"],
        hspace=plot["row_hspace"],
        left=m["left"],
        right=m["right"],
        top=m["top"],
        bottom=m["bottom"],
    )

    # top row, 4 columns: map | map | empty spacer | scatter. The spacer keeps the
    # scatter's y-axis label from crowding the second map.
    gs = outer[0].subgridspec(
        1,
        4,
        width_ratios=[mp["width_ratio"], mp["width_ratio"], mp["gap_ratio"], panels["scatter"]["width_ratio"]],
        wspace=mp["wspace"],
    )
    ax_a = fig.add_subplot(gs[0, 0])
    ax_b = fig.add_subplot(gs[0, 1])
    ax_c = fig.add_subplot(gs[0, 3])

    # bottom row: ablation scatter | discharge time series. Column widths are set below.
    gs_bot = outer[1].subgridspec(1, 2)
    ax_d = fig.add_subplot(gs_bot[0, 0])
    ax_e = fig.add_subplot(gs_bot[0, 1])

    # The two scatters, (c) and (d), are pinned to exactly the same width; the
    # discharge panel (e) then fills the rest of the row, starting bottom_wspace
    # after (d). Done before drawing so (e)'s twin axis inherits the final position.
    pos_c, pos_d, pos_e = (ax.get_position() for ax in (ax_c, ax_d, ax_e))
    ax_d.set_position((pos_d.x0, pos_d.y0, pos_c.width, pos_d.height))
    x0_e = pos_d.x0 + pos_c.width + panels["ablation"]["bottom_wspace"] * pos_c.width
    ax_e.set_position((x0_e, pos_e.y0, pos_e.x1 - x0_e, pos_e.height))

    for ax, idx, scene in zip((ax_a, ax_b), idxs, scenes):
        plot_map(ax, ds, idx, times[idx].strftime(mp["date_format"]), scene=scene)
    plot_area_scatter(ax_c, area_df)
    plot_ablation_scatter(ax_d, abl_df)
    plot_discharge_series(ax_e, daily_q, annual_q)

    # descriptive (non-bold) titles on the bottom panels, like the date titles on the maps
    for ax, key in ((ax_c, "scatter"), (ax_d, "ablation"), (ax_e, "discharge")):
        p = panels[key]
        ax.set_title(p["title"], loc="center", fontsize=plot["title_fontsize"], ha="left", x=p["title_x"])

    # bold panel letters as left-aligned titles: they share the baseline and font
    # size of the (non-bold) date titles on the two maps
    letters = [(ax_a, mp["letters"][0]), (ax_b, mp["letters"][1])]
    letters += [(ax, panels[k]["letter"]) for ax, k in ((ax_c, "scatter"), (ax_d, "ablation"), (ax_e, "discharge"))]
    for ax, letter in letters:
        ax.set_title(letter, loc="left", fontweight=plot["panel_letter_fontweight"], fontsize=plot["title_fontsize"])

    for fmt in output["formats"]:
        path = HERE / f"{FIG_STEM}.{fmt}"
        fig.savefig(path, dpi=output["dpi"], bbox_inches="tight")
        print(f"saved {path}")


if __name__ == "__main__":
    main()
