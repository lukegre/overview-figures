"""
Glacier retreat figure (Qalerallit / South Greenland).

Combined figure (2026-07):
  - TOP  : bar plot of TOTAL retreat per glacier (linear retreat distance, km),
           glacier numbers printed above each bar. Numbering starts at 1.
  - BELOW (flush, no gap): map of the latest glacier outlines over a
           web-tile basemap (default: Esri World Imagery / satellite).

Retreat distance:
  Measured per-glacier cumulative front retreat [km] from glacier_retreat.csv
  (one column per glacier, one row per year; 1992 baseline). The total retreat
  is the last observation minus the first for each glacier (positive = retreat,
  negative = advance).

Bars and outlines share a per-glacier "identity" colour (Spectral_r, purple->red);
numbers link the two panels.

It is imported by ``../plot_glacier_retreat.py`` (left panel) and can also be run
standalone to regenerate the individual ``examples/glacier_retreat-map_v2.png``.

Run:
    ../../.venv/bin/python scripts/make_glacier_retreat_map.py

Tweak the CONFIG block below.
"""

from __future__ import annotations

from pathlib import Path

import contextily as cx
import geopandas as gpd
import matplotlib.patheffects as pe
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib import gridspec
from matplotlib.colors import to_hex
from matplotlib.patches import Rectangle
from shapely.geometry import box

# --------------------------------------------------------------------------- #
# CONFIG
# --------------------------------------------------------------------------- #
# data lives in ../data relative to this script (folder was reorganised 2026-07)
_ROOT = Path(__file__).resolve().parent.parent
GPKG = _ROOT / "data" / "glacier_outline-rectangles.gpkg"
RETREAT_CSV = _ROOT / "data" / "glacier_retreat.csv"  # measured cumulative retreat [km] per glacier/year
OUT_FIG = _ROOT / "examples" / "glacier_retreat-map_v2.png"

# Basemap tile provider. Swap for any contextily provider, e.g.:
#   cx.providers.Esri.WorldImagery      -> satellite (default)
#   cx.providers.Esri.WorldTopoMap      -> topographic
#   cx.providers.OpenStreetMap.Mapnik   -> OSM
#   cx.providers.CartoDB.Positron       -> light/minimal
BASEMAP = cx.providers.Esri.WorldImagery

CMAP = "Spectral_r"  # colour encodes glacier number (1=purple -> 18=red)
RETREAT_UNIT = "km"  # "km" (native) or "m" for the bar-plot retreat distance
SORT_BARS_BY = "number"  # "number" (1 left -> 18 right) or "retreat"
LABEL_START = 1  # glacier numbering starts here (1-based)
REVERSE_LABELS = True  # True -> number 1 is the highest id (reversed vs source)
MAP_PAD_FRAC = 0.08  # fractional padding around outlines on the map
EXCLUDE_IDS = [
    18
]  # source glacier ids dropped from the WHOLE figure (id 18 = was #1); rest renumber
EXCLUDE_FROM_MAP = []  # glacier NUMBERS (map labels) to omit from the map panel ONLY
MAP_BLACK_LABELS = range(5, 15)  # map numbers drawn with black text (legible on light circles)
MAP_BLACK_ALPHA = 0.7  # text opacity for those black-numbered glaciers (marker stays opaque)
MARKER_EDGE_LW = 1.4  # circle-marker edge width
SHOW_TITLE = False  # figure title above the bar plot
# Highlight box on the map (lon/lat: minx, miny, maxx, maxy). Matches the extent of the
# detailed single-glacier figure in 4_qalerallit_glacier.ipynb; frames glacier #1 (id 17).
HIGHLIGHT_BBOX_LONLAT = (-46.804692, 60.972829, -46.588195, 61.087028)
HIGHLIGHT_EDGE = "white"  # highlight-box edge colour
DPI = 200


# --------------------------------------------------------------------------- #
# DATA
# --------------------------------------------------------------------------- #
def load_retreat():
    """Per-glacier total measured front retreat [km or m]. Keeps all glaciers.

    Reads glacier_retreat.csv (one glacier_NN column per glacier, one row per
    year, cumulative from a 1992 baseline). Total retreat is the last minus the
    first valid observation per glacier (positive = retreat, negative = advance).
    """
    cum = pd.read_csv(RETREAT_CSV, index_col="year")
    span = (int(cum.index.min()), int(cum.index.max()))

    # total = last valid - first valid, per glacier column
    total = cum.apply(lambda s: s.dropna().iloc[-1] - s.dropna().iloc[0]).rename("retreat")
    total.index = total.index.str.replace("glacier_", "").astype(int)  # "glacier_07" -> 7
    if RETREAT_UNIT == "m":
        total = total * 1000.0

    df = total.reset_index().rename(columns={"index": "id"})
    # drop glaciers excluded from the whole figure, then number the rest 1..N
    df = df[~df["id"].isin(EXCLUDE_IDS)].reset_index(drop=True)

    # glacier number (1-based). REVERSE_LABELS flips it so number 1 = highest id.
    rank = df["id"] - df["id"].min()
    if REVERSE_LABELS:
        rank = rank.max() - rank
    df["label"] = rank + LABEL_START

    # colour ENCODES the glacier number: number 1 -> purple, number N -> red
    cmap = plt.get_cmap(CMAP)
    n = len(df)
    df["color"] = [to_hex(cmap((lbl - LABEL_START) / max(n - 1, 1))) for lbl in df["label"]]
    return df, span


# --------------------------------------------------------------------------- #
# PLOT HELPERS
# --------------------------------------------------------------------------- #
def _plot_bars(ax, df, span):
    if SORT_BARS_BY == "retreat":
        bar_df = df.sort_values("retreat", ascending=False)
    else:  # by glacier number: 1 on the left, N on the right
        bar_df = df.sort_values("label", ascending=True)
    bar_df = bar_df.reset_index(drop=True)

    x = np.arange(len(bar_df))
    ax.bar(
        x,
        bar_df["retreat"],
        color=bar_df["color"],
        edgecolor="0.25",
        linewidth=0.6,
        width=0.9,
    )
    ax.axhline(0, color="0.4", linewidth=0.8)

    # glacier number above each bar
    pad = 0.01 * bar_df["retreat"].max()
    for xi, (_, row) in zip(x, bar_df.iterrows()):
        top = max(row["retreat"], 0) + pad
        ax.annotate(
            int(row["label"]),
            (xi, top),
            ha="center",
            va="bottom",
            fontsize=9,
            fontweight="bold",
            color="0.15",  # dark labels above the bars
        )

    ax.set_ylabel(f"Total retreat distance [{RETREAT_UNIT}]")
    if SHOW_TITLE:
        ax.set_title(f"Total glacier retreat, {span[0]}–{span[1]}", fontsize=13)
    ax.set_xticks([])
    ax.margins(x=0.01)
    ax.set_ylim(top=ax.get_ylim()[1] * 1.08)  # headroom for the labels
    ax.spines[["top", "right", "bottom"]].set_visible(False)


def _plot_map(ax, df):
    gdf = gpd.read_file(GPKG)
    latest = gdf.sort_values("year").groupby("id", as_index=False).last()
    latest = gpd.GeoDataFrame(latest, geometry="geometry", crs=gdf.crs)
    latest = latest.merge(df[["id", "label", "color"]], on="id", how="inner")
    # drop glaciers excluded from the map (by map label/number); bar plot keeps them
    latest = latest[~latest["label"].isin(EXCLUDE_FROM_MAP)]
    latest = latest.to_crs(epsg=3857)

    minx, miny, maxx, maxy = latest.total_bounds
    dx, dy = (maxx - minx), (maxy - miny)
    ax.set_xlim(minx - MAP_PAD_FRAC * dx, maxx + MAP_PAD_FRAC * dx)
    ax.set_ylim(miny - MAP_PAD_FRAC * dy, maxy + MAP_PAD_FRAC * dy)

    # highlight box (extent of the detailed single-glacier figure) around glacier #1
    if HIGHLIGHT_BBOX_LONLAT is not None:
        hb = gpd.GeoSeries([box(*HIGHLIGHT_BBOX_LONLAT)], crs=4326).to_crs(latest.crs).total_bounds
        ax.add_patch(
            Rectangle(
                (hb[0], hb[1]),
                hb[2] - hb[0],
                hb[3] - hb[1],
                fill=False,
                edgecolor=HIGHLIGHT_EDGE,
                linewidth=2.0,
                zorder=4,
            )
        )

    for _, row in latest.iterrows():
        c = row.geometry.representative_point()
        black = int(row["label"]) in MAP_BLACK_LABELS
        text_color = "black" if black else "white"
        text_alpha = MAP_BLACK_ALPHA if black else 1.0  # marker stays opaque; only text dims
        ann = ax.annotate(
            int(row["label"]),
            (c.x, c.y),
            ha="center",
            va="center",
            fontsize=8,
            fontweight="bold",
            color=text_color,
            alpha=text_alpha,
            zorder=5,
            bbox=dict(boxstyle="circle,pad=0.2", fc=row["color"], ec="white", lw=MARKER_EDGE_LW),
        )
        # drop shadow on the circle marker
        ann.get_bbox_patch().set_path_effects([
            pe.withSimplePatchShadow(offset=(1.5, -1.5), alpha=0.5)
        ])

    cx.add_basemap(ax, source=BASEMAP, crs=latest.crs, attribution_size=5)
    ax.set_xticks([])
    ax.set_yticks([])


# --------------------------------------------------------------------------- #
# COMBINED FIGURE (bar plot on top, map below, flush)
# --------------------------------------------------------------------------- #
def make_figure(df, span):
    fig = plt.figure(figsize=(8, 10), dpi=DPI)
    gs = gridspec.GridSpec(2, 1, height_ratios=[1, 2.4], hspace=0.0, figure=fig)
    ax_bar = fig.add_subplot(gs[0])
    ax_map = fig.add_subplot(gs[1])

    _plot_bars(ax_bar, df, span)
    _plot_map(ax_map, df)

    # map keeps an equal aspect ratio, so pin the panels together: bar plot to
    # the bottom of its cell, map to the top of its cell -> they meet, no gap.
    ax_bar.set_anchor("S")
    ax_map.set_anchor("N")

    fig.savefig(OUT_FIG, bbox_inches="tight", dpi=DPI)
    print(f"wrote {OUT_FIG}")
    return fig


if __name__ == "__main__":
    df, span = load_retreat()
    make_figure(df, span)
