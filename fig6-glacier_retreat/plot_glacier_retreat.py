"""
Combined glacier-retreat figure (Qalerallit / South Greenland).

Draws two panels side by side in a single figure. All plotting is done here so
that font sizes, line widths and styling are consistent across both panels:

  LEFT  : full-area glacier melt -> bar plot of total retreat per glacier flush
          above the latest-outline map (over an Esri satellite basemap).
  RIGHT : the specific glacier -> traced glacier-front outlines coloured by year
          over a true-colour Sentinel-2 scene. The x/y ticks are removed here.

Data loading is reused from the two helper scripts in ``scripts/``
(``make_glacier_retreat_map`` and ``make_glacier_fronts``) since that part is
figure-independent; the plotting itself is re-implemented below rather than
calling their axis helpers.

Run:
    ../../.venv/bin/python plot_glacier_retreat.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# helper modules live in scripts/ (folder reorganised 2026-07)
_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(_ROOT / "scripts"))

import contextily as cx
import geopandas as gpd
import make_glacier_fronts as fronts_mod
import make_glacier_retreat_map as retreat_mod
import matplotlib as mpl
import matplotlib.patheffects as pe
import matplotlib.pyplot as plt
import numpy as np
from matplotlib import gridspec
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle
from shapely.geometry import box

# --------------------------------------------------------------------------- #
# CONFIG
# --------------------------------------------------------------------------- #
OUT_FIG = _ROOT / "fig6-glacier_retreat.png"
DPI = 200

# Fraction of the right-panel map's north (top) extent to clip off. Shrinking the
# equal-aspect map lowers its (centred) axis box so the colour bar above it drops
# down to line up with the top of the left-panel bar plot.
CLIP_NORTH_FRAC = 0.055

# Little Ice Age extent overlay on the right panel (dashed white line)
LIA_GPKG = _ROOT / "data" / "LIAextenthistorical.gpkg"
LIA_LABEL = "Little Ice Age extent"

# Left-panel (retreat map) settings -- mirror make_glacier_retreat_map.py
BASEMAP = cx.providers.Esri.WorldImagery
BASEMAP.attribution = ""
RETREAT_UNIT = retreat_mod.RETREAT_UNIT
SORT_BARS_BY = retreat_mod.SORT_BARS_BY
MAP_PAD_FRAC = retreat_mod.MAP_PAD_FRAC
EXCLUDE_FROM_MAP = retreat_mod.EXCLUDE_FROM_MAP
MAP_BLACK_LABELS = retreat_mod.MAP_BLACK_LABELS
MAP_BLACK_ALPHA = retreat_mod.MAP_BLACK_ALPHA
MARKER_EDGE_LW = retreat_mod.MARKER_EDGE_LW
HIGHLIGHT_BBOX_LONLAT = retreat_mod.HIGHLIGHT_BBOX_LONLAT
HIGHLIGHT_EDGE = retreat_mod.HIGHLIGHT_EDGE

# Shared font sizes / line widths (controlled once, applied to both panels)
FS_AXIS_LABEL = 12
FS_BAR_NUMBER = 10
FS_MAP_NUMBER = 10
FRONT_LW = 2.5
FRONT_ALPHA = 0.7


# --------------------------------------------------------------------------- #
# SHARED HELPERS
# --------------------------------------------------------------------------- #
def _panel_label(ax, text):
    """Bottom-left panel label with a dark, semi-transparent backing box."""
    ax.text(
        0.02,
        0.02,
        text,
        transform=ax.transAxes,
        ha="left",
        va="bottom",
        fontsize=FS_AXIS_LABEL,
        color="white",
        zorder=7,
        bbox=dict(boxstyle="round,pad=0.3", fc="0.2", ec="none", alpha=0.6),
    )


# --------------------------------------------------------------------------- #
# LEFT PANEL: bar plot + retreat map
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
            fontsize=FS_BAR_NUMBER,
            fontweight="bold",
            color="0.15",
        )

    ax.set_ylabel(f"Retreat distance [{RETREAT_UNIT}]", fontsize=FS_AXIS_LABEL)
    ax.set_xticks([])
    ax.margins(x=0.01)
    ax.set_ylim(top=ax.get_ylim()[1] * 1.08)  # headroom for the labels
    ax.spines[["top", "right", "bottom"]].set_visible(False)


def _plot_map(ax, df):
    gdf = gpd.read_file(retreat_mod.GPKG)
    latest = gdf.sort_values("year").groupby("id", as_index=False).last()
    latest = gpd.GeoDataFrame(latest, geometry="geometry", crs=gdf.crs)
    latest = latest.merge(df[["id", "label", "color"]], on="id", how="inner")
    latest = latest[~latest["label"].isin(EXCLUDE_FROM_MAP)]
    latest = latest.to_crs(epsg=3857)

    minx, miny, maxx, maxy = latest.total_bounds
    dx, dy = (maxx - minx), (maxy - miny)
    ax.set_xlim(minx - MAP_PAD_FRAC * dx, maxx + MAP_PAD_FRAC * dx)
    ax.set_ylim(miny - MAP_PAD_FRAC * dy, maxy + MAP_PAD_FRAC * dy)

    # highlight box (extent of the detailed single-glacier figure on the right)
    if HIGHLIGHT_BBOX_LONLAT is not None:
        hb = gpd.GeoSeries([box(*HIGHLIGHT_BBOX_LONLAT)], crs=4326).to_crs(latest.crs).total_bounds
        ax.add_patch(
            Rectangle(
                (hb[0], hb[1]),
                hb[2] - hb[0],
                hb[3] - hb[1],
                fill=False,
                edgecolor="black",
                linewidth=5.0,
                zorder=4,
                alpha=0.4,
            )
        )
        ax.add_patch(
            Rectangle(
                (hb[0], hb[1]),
                hb[2] - hb[0],
                hb[3] - hb[1],
                fill=False,
                edgecolor=HIGHLIGHT_EDGE,
                linewidth=3.0,
                zorder=4,
            )
        )

    for _, row in latest.iterrows():
        c = row.geometry.representative_point()
        black = int(row["label"]) in MAP_BLACK_LABELS
        text_color = "black" if black else "white"
        text_alpha = MAP_BLACK_ALPHA if black else 1.0
        ann = ax.annotate(
            int(row["label"]),
            (c.x, c.y),
            ha="center",
            va="center",
            fontsize=FS_MAP_NUMBER,
            fontweight="bold",
            color=text_color,
            alpha=text_alpha,
            zorder=5,
            bbox=dict(boxstyle="circle,pad=0.2", fc=row["color"], ec="white", lw=MARKER_EDGE_LW),
        )
        ann.get_bbox_patch().set_path_effects([
            pe.withSimplePatchShadow(offset=(1.5, -1.5), alpha=0.5)
        ])

    cx.add_basemap(ax, source=BASEMAP, crs=latest.crs, attribution_size=0)
    ax.set_xticks([])
    ax.set_yticks([])
    _panel_label(ax, "a) Glacier locations")


def _draw_left(subspec, df, span):
    """Full-area melt: bar plot flush above the latest-outline map."""
    inner = gridspec.GridSpecFromSubplotSpec(
        2, 1, subplot_spec=subspec, height_ratios=[1, 2.4], hspace=0.0
    )
    ax_bar = plt.subplot(inner[0])
    ax_map = plt.subplot(inner[1])

    _plot_bars(ax_bar, df, span)
    _plot_map(ax_map, df)

    # pin the panels together so the bar plot meets the (equal-aspect) map.
    ax_bar.set_anchor("S")
    ax_map.set_anchor("N")
    return ax_bar, ax_map


# --------------------------------------------------------------------------- #
# RIGHT PANEL: year-coloured fronts over Sentinel-2
# --------------------------------------------------------------------------- #
def _draw_right(subspec, fronts, basemap, lia):
    """Specific glacier: year-coloured fronts over the Sentinel-2 scene."""
    ax = plt.subplot(subspec)
    # pin the (equal-aspect) map to the bottom of its cell so its lower edge
    # lines up with the bottom of the left-panel map; clipping the north extent
    # then only shortens it upward, dropping the colour bar to the bar-plot top.
    ax.set_anchor("S")

    basemap.plot.imshow(ax=ax, vmin=0, vmax=1)
    ax.set_aspect("equal")

    cmap = plt.cm.inferno_r.resampled(len(fronts))
    fronts.plot(ax=ax, colors=cmap.colors, lw=FRONT_LW, alpha=FRONT_ALPHA)

    # keep the panel framed on the Sentinel-2 scene; the LIA line below extends
    # past it and would otherwise auto-expand the axis limits.
    xlim, ylim = ax.get_xlim(), ax.get_ylim()
    # clip the northern (top) part of the scene so the shorter map lets its
    # colour bar line up with the top of the left-panel bar plot.
    ylim = (ylim[0], ylim[1] - CLIP_NORTH_FRAC * (ylim[1] - ylim[0]))

    # Little Ice Age extent (reprojected to the fronts' CRS): dashed white line
    lia.to_crs(fronts.crs).plot(
        ax=ax, color="white", linestyle="--", linewidth=FRONT_LW, alpha=0.5, zorder=6
    )
    ax.set_xlim(xlim)
    ax.set_ylim(ylim)
    lia_handle = Line2D(
        [0], [0], color="white", linestyle="--", lw=FRONT_LW, alpha=0.5, label=LIA_LABEL
    )
    leg = ax.legend(handles=[lia_handle], loc="upper left", fontsize=FS_MAP_NUMBER)
    leg.get_frame().set_facecolor("0.2")
    leg.get_frame().set_alpha(0.6)
    leg.get_frame().set_linewidth(0)
    for txt in leg.get_texts():
        txt.set_color("white")

    ax.set_title("")
    # remove the x/y ticks and axis labels from the right panel
    ax.set_xlabel("")
    ax.set_ylabel("")
    ax.set_xticks([])
    ax.set_yticks([])

    # year colour bar above the panel (matches the front colouring: light = oldest)
    years = fronts.index.astype(int).to_numpy()
    norm = mpl.colors.Normalize(vmin=years.min(), vmax=years.max())
    sm = mpl.cm.ScalarMappable(cmap=plt.cm.inferno_r, norm=norm)
    cax = ax.inset_axes([0.0, 1.02, 1.0, 0.025])
    cbar = ax.figure.colorbar(sm, cax=cax, orientation="horizontal")
    cbar.ax.xaxis.set_ticks_position("top")
    cbar.ax.xaxis.set_label_position("top")
    cbar.set_label("Year", fontsize=FS_AXIS_LABEL)
    cbar.ax.tick_params(labelsize=FS_MAP_NUMBER)
    _panel_label(ax, "b) Qalerallit / Naajat Sermiat glaciers")
    return ax


# --------------------------------------------------------------------------- #
# COMBINED FIGURE
# --------------------------------------------------------------------------- #
def make_figure(df, span, fronts, basemap, lia):
    fig = plt.figure(figsize=(12, 8), dpi=DPI)
    gs = gridspec.GridSpec(1, 2, width_ratios=[1, 1], wspace=0.05, figure=fig)

    _draw_left(gs[0], df, span)
    _draw_right(gs[1], fronts, basemap, lia)

    fig.savefig(OUT_FIG, bbox_inches="tight", dpi=DPI)
    print(f"wrote {OUT_FIG}")
    return fig


if __name__ == "__main__":
    # LEFT panel data (full-area retreat)
    df, span = retreat_mod.load_retreat()

    # RIGHT panel data (single-glacier fronts + Sentinel-2 basemap)
    fronts = fronts_mod.load_fronts()
    bbox = fronts.dissolve().to_crs("EPSG:4326").bounds.values.tolist()[0]
    bbox = tuple(b + off for b, off in zip(bbox, fronts_mod.BBOX_OFFSET))
    basemap = fronts_mod.load_basemap(bbox)

    # Little Ice Age extent overlay
    lia = gpd.read_file(LIA_GPKG)

    make_figure(df, span, fronts, basemap, lia)
