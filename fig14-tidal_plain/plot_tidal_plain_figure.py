"""Recreate the tidal-plain overview figure.

Panel (a): two Landsat maps of the fjord with the tidal flats outlined.
Panel (b): normalised tidal-plain area vs. year, coloured by tide height, with a
           bootstrapped linear fit and its confidence band.

All tweakable elements live in ``config.yaml`` (dates, colormaps, scatter
properties, layout, ...). Run with::

    uv run python plot_tidal_plain_figure.py [config.yaml]

Rendering notes
---------------
* Panel (a) follows the recipe in ``1.2_landsat_data.ipynb`` (cells 7/10): the
  fjord is drawn with a colormap (``cividis`` -> dark-navy water at low values,
  yellow tidal flats at high values) and the flats are outlined with a contour.
  The original notebook colours the *SWIR* field over the ocean, but the cleaned
  netCDF only stores ``rgb`` and ``tidal_flats``; we therefore reproduce the same
  look by colouring a field that is 0 over the fjord and ``flat_value`` on the
  flats.
* The netCDF stores RGB only over the fjord (land is NaN), so the natural terrain
  background of the original screenshot is not available and land is a flat colour.
* Panel (b) is rebuilt from ``area_tide_height_fit.csv`` (columns from
  ``2.2_landsat_tide_plains-add_tide_info.ipynb``, cell 21).
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import xarray as xr
import yaml
from matplotlib.lines import Line2D

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE / "scripts"))  # helper modules (fetch_landsat, stac)


plt.rcParams["font.size"] = 10


# =============================================================================
# Panel (a): maps
# =============================================================================
def draw_map(ax, ds, index, title, cfg, scene=None):
    """Draw one fjord map, following the 1.2_landsat_data notebook recipe.

    If `scene` (rgb, swir) is given, render RGB true-colour land + cividis SWIR
    over the ocean. Otherwise fall back to a flat land colour + navy/yellow fill.
    """
    flats = ds["tidal_flats"].isel(time=index).values.astype(float)
    ocean = np.isfinite(ds["rgb"].isel(time=index, band=0).values)  # fjord footprint

    if scene is not None:
        rgb, swir = scene
        # RGB true-colour base (land + fjord); NaN (scene edge) -> white
        disp = np.clip(rgb / cfg["rgb_vmax"], 0, 1)
        disp = np.where(np.isfinite(disp), disp, 1.0)
        ax.imshow(disp, origin="upper", interpolation="nearest")

        # SWIR over the ocean only (notebook: subtract ocean median, clip >=0)
        sw = np.where(ocean, np.asarray(swir, float), np.nan)
        sw = np.clip(sw - np.nanmedian(sw), 0, None)
        sw = np.where(ocean, sw, np.nan)
        ax.imshow(
            sw,
            origin="upper",
            interpolation="nearest",
            cmap=cfg["swir_cmap"],
            vmin=cfg["swir_vmin"],
            vmax=cfg["swir_vmax"],
        )
    else:
        # fallback: flat land + navy water / yellow flats (no imagery fetched)
        ax.set_facecolor(cfg["land_fallback_color"])
        field = np.full(flats.shape, np.nan)
        field[ocean] = cfg["swir_vmin"]
        field[flats > 0.5] = cfg["swir_vmax"]
        ax.imshow(
            field,
            origin="upper",
            interpolation="nearest",
            cmap=cfg["swir_cmap"],
            vmin=cfg["swir_vmin"],
            vmax=cfg["swir_vmax"],
        )

    # outline around the flats
    ax.contour(
        flats, levels=[0.5], colors=[cfg["contour_color"]], linewidths=cfg["contour_linewidth"]
    )

    ax.set_title(title, fontsize=cfg["title_fontsize"])
    ax.set_xticklabels([])
    ax.set_yticklabels([])
    ax.tick_params(length=3)


# =============================================================================
# Panel (b): scatter + regression
# =============================================================================
def draw_scatter(ax, df, cfg):
    """Normalised tidal-plain area vs. year, coloured by tide height."""
    x = df["time_dt0"].to_numpy(float)
    y = df["tidal_plain_area_logistic_norm_to_tide_height"].to_numpy(float)
    hue = df["tide_height"].to_numpy(float)

    vmin, vmax = hue.min(), hue.max()
    ax.scatter(
        x,
        y,
        c=hue,
        cmap=cfg["cmap"],
        vmin=vmin,
        vmax=vmax,
        s=cfg["marker_size"],
        edgecolor=cfg["edgecolor"],
        linewidth=cfg["edgewidth"],
        alpha=cfg.get("marker_alpha", 1.0),
        zorder=3,
    )

    # OLS fit + bootstrap confidence band
    slope, intercept, r2, pval = _ols(x, y)
    xg = np.linspace(x.min(), x.max(), 200)
    lo, hi = _bootstrap_band(x, y, xg, cfg["n_boot"], cfg["ci"], cfg["seed"])
    ax.fill_between(xg, lo, hi, color=cfg["band_color"], alpha=cfg["band_alpha"], zorder=1)
    ax.plot(
        xg, intercept + slope * xg, color=cfg["line_color"], linewidth=cfg["line_width"], zorder=2
    )

    ax.text(
        0.05,
        0.03,
        f"R-squared: {r2:.3f}\nP-value: {pval:.3f}",
        transform=ax.transAxes,
        fontsize="medium",
        ha="left",
        va="bottom",
        bbox=dict(boxstyle="round,pad=0.3", facecolor="white", alpha=0.75, edgecolor="none"),
        zorder=4,
    )

    # x axis: days-since-year0 -> calendar years
    year0 = int(df["year"].min())
    ticks = np.arange(0, 13_000, 365.25 * cfg["tick_step_years"])
    ax.set_xticks(ticks)
    ax.set_xticklabels((ticks / 365.25 + year0).astype(int))
    ax.set_xlim(-100, x.max() + 250)
    ax.set_xlabel(cfg["xlabel"])
    ax.set_ylabel(cfg["ylabel"])

    # discrete legend at regular tide-height steps (mirrors seaborn numeric hue)
    step = cfg["legend_step"]
    levels = np.arange(np.ceil(vmin / step) * step, np.floor(vmax / step) * step + step / 100, step)
    cmap = plt.get_cmap(cfg["cmap"])
    handles = [
        Line2D(
            [0],
            [0],
            marker="o",
            linestyle="",
            markerfacecolor=cmap((lv - vmin) / (vmax - vmin)),
            markeredgecolor=cfg["edgecolor"],
            markeredgewidth=cfg["edgewidth"],
            markersize=7,
            label=f"{lv:.1f}",
        )
        for lv in levels
    ]
    ax.legend(
        handles=handles,
        title=cfg["legend_title"],
        loc="upper left",
        frameon=True,
        fontsize="small",
        labelspacing=0.5,
        handletextpad=0.3,
        columnspacing=0.5,
        title_fontsize="medium",
        ncol=2,
    )

    # lighten the top/right spines
    for side in ("top", "right"):
        ax.spines[side].set_color("#ddd")


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
def main(config_path):
    cfg = yaml.safe_load(Path(config_path).read_text())

    ds = xr.open_dataset(HERE / cfg["data"]["netcdf"], engine="h5netcdf")
    df = pd.read_csv(HERE / cfg["data"]["csv"]).dropna(
        subset=["time_dt0", "tidal_plain_area_logistic_norm_to_tide_height"]
    )

    times = pd.to_datetime(ds["time"].values)
    m = cfg["maps"]

    def nearest_idx(date):
        return int(np.argmin(np.abs(times - pd.Timestamp(date))))

    left_idx = nearest_idx(m["left_date"])
    right_idx = nearest_idx(m["right_date"])

    # fetch (or load cached) RGB + SWIR scenes for the two tidal-plain dates
    left_scene = right_scene = None
    fetch_cfg = cfg.get("fetch", {})
    if fetch_cfg.get("enabled"):
        import fetch_landsat

        # resolve cache_dir against this folder so it lands in data/ regardless of
        # where fetch_landsat lives (it joins the path against its own location).
        cache_dir = str(HERE / fetch_cfg["cache_dir"])
        try:
            rgb_l, swir_l, _, left_idx = fetch_landsat.get_scene(
                ds, m["left_date"], fetch_cfg["bbox"], cache_dir, fetch_cfg["max_cloud_cover"]
            )
            rgb_r, swir_r, _, right_idx = fetch_landsat.get_scene(
                ds, m["right_date"], fetch_cfg["bbox"], cache_dir, fetch_cfg["max_cloud_cover"]
            )
            left_scene = (rgb_l, swir_l)
            right_scene = (rgb_r, swir_r)
        except Exception as exc:  # network/deps unavailable -> flat-colour fallback
            print(f"WARNING: scene fetch failed ({exc}); using flat-colour maps")

    lay = cfg["layout"]
    out = cfg["output"]
    fig = plt.figure(figsize=tuple(out["figsize"]))
    # 4 columns: map | map | empty spacer | scatter. The spacer keeps the
    # scatter's y-axis label from crowding the second map.
    ratios = [
        lay["map_width_ratio"],
        lay["map_width_ratio"],
        lay["panel_gap_ratio"],
        lay["scatter_width_ratio"],
    ]
    gs = fig.add_gridspec(
        1,
        4,
        width_ratios=ratios,
        wspace=lay["map_wspace"],
        left=0.02,
        right=0.98,
        top=0.90,
        bottom=0.12,
    )
    ax_a1 = fig.add_subplot(gs[0, 0])
    ax_a2 = fig.add_subplot(gs[0, 1])
    ax_b = fig.add_subplot(gs[0, 3])

    draw_map(ax_a1, ds, left_idx, times[left_idx].strftime(m["date_format"]), m, scene=left_scene)
    draw_map(
        ax_a2, ds, right_idx, times[right_idx].strftime(m["date_format"]), m, scene=right_scene
    )
    draw_scatter(ax_b, df, cfg["scatter"])

    if lay.get("divider"):
        x_div = (ax_a2.get_position().x1 + ax_b.get_position().x0) / 2
        fig.add_artist(
            plt.Line2D(
                [x_div, x_div], [0.10, 0.92], color="k", linewidth=1.5, transform=fig.transFigure
            )
        )

    # bold panel letters as left-aligned titles: they share the exact baseline
    # and font size of the (non-bold) centred date titles on the two maps.
    for ax, label in ((ax_a1, "a"), (ax_a2, "b"), (ax_b, "c")):
        ax.set_title(label, loc="left", fontweight="bold", fontsize=m["title_fontsize"])

    out_path = HERE / out["path"]
    fig.savefig(out_path, dpi=out["dpi"], bbox_inches="tight")
    print(f"saved {out_path}")


if __name__ == "__main__":
    cfg_arg = sys.argv[1] if len(sys.argv) > 1 else HERE / "config.yaml"
    main(cfg_arg)
