"""Glacier-front retreat around Qalerallit / Naajat Sermiat (South Greenland).

Two panels: (a) bar plot of the total front retreat per glacier (1992-2024)
flush above a satellite map of the latest glacier outlines; (b) traced front
outlines of one glacier for every available year, coloured by year, over a
true-colour Sentinel-2 scene with the Little Ice Age extent as a dashed line.
All settings live in ``config_GLACIER_RETREAT.yaml``.

Data flow:

    glacier_retreat.csv + glacier_outline-rectangles.gpkg
      -> total retreat per glacier, numbered and coloured
      -> panel (a): bars + outline map over Esri World Imagery tiles
    hand-drawn (1973-1985) + traced (1992-2024) front polygons
      -> one terminus line per year
      -> panel (b): fronts over the Sentinel-2 scene + Little Ice Age line

The Sentinel-2 scene is built by ``data/glacier_i16n6104w4669/download_sentinel2.py``.

Run from the repository root:

    MPLCONFIGDIR="$TMPDIR/mpl" .venv/bin/python fig6-glacier_retreat/plot_GLACIER_RETREAT.py
"""

from __future__ import annotations

from functools import reduce
from pathlib import Path

import contextily as cx
import geopandas as gpd
import matplotlib as mpl
import matplotlib.patheffects as pe
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import rioxarray  # noqa: F401  (registers the .rio accessor)
import xarray as xr
from matplotlib import gridspec
from matplotlib.colors import to_hex
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle
from shapely.geometry import box

from greenfjord.config import get_script_name, read_config
from greenfjord.viz import set_paper_style

# paths and names, derived from the script name (plot_<NAME>.py)
HERE = Path(__file__).resolve().parent
NAME = get_script_name(__file__)  # GLACIER_RETREAT
FIG_STEM = f"fig_{NAME}"  # prefix of the figure outputs

# config
cfg = read_config(HERE / f"config_{NAME}.yaml")
inp = cfg["inputs"]
ana = cfg["analysis"]
plot = cfg["plot"]
pa = plot["panel_a"]
pb = plot["panel_b"]
output = cfg["output"]
RETREAT_CSV = HERE / inp["retreat_csv"]
OUTLINES_GPKG = HERE / inp["outlines_gpkg"]
LIA_GPKG = HERE / inp["lia_gpkg"]
FRONTS_OLD_SHP = HERE / inp["fronts_old_shp"]
FRONTS_NEW_GPKG = HERE / inp["fronts_new_gpkg"]
SENTINEL2_TIF = HERE / inp["sentinel2_tif"]


def load_retreat() -> pd.DataFrame:
    """Return total front retreat per glacier with columns ``id, retreat, label, color``.

    ``glacier_retreat.csv`` holds cumulative retreat per glacier (column
    ``glacier_NN``) and year; the total is the last minus the first valid value
    (positive = retreat, negative = advance). Excluded ids are dropped, the rest
    numbered, and each glacier gets a colour from its number.
    """
    cum = pd.read_csv(RETREAT_CSV, index_col="year")
    total = cum.apply(lambda s: s.dropna().iloc[-1] - s.dropna().iloc[0]).rename("retreat")
    total.index = total.index.str.replace("glacier_", "").astype(int)  # "glacier_07" -> 7
    if ana["retreat_unit"] == "m":
        total = total * 1000.0

    df = total.reset_index().rename(columns={"index": "id"})
    df = df[~df["id"].isin(ana["exclude_ids"])].reset_index(drop=True)

    rank = df["id"] - df["id"].min()
    if ana["reverse_labels"]:
        rank = rank.max() - rank
    start = ana["label_start"]
    df["label"] = rank + start

    cmap = plt.get_cmap(ana["glacier_cmap"])
    df["color"] = [to_hex(cmap((lbl - start) / max(len(df) - 1, 1))) for lbl in df["label"]]
    return df


def load_latest_outlines(df: pd.DataFrame) -> gpd.GeoDataFrame:
    """Return the latest outline per glacier with label and colour, in the map CRS."""
    gdf = gpd.read_file(OUTLINES_GPKG)
    latest = gdf.sort_values("year").groupby("id", as_index=False).last()
    latest = gpd.GeoDataFrame(latest, geometry="geometry", crs=gdf.crs)
    latest = latest.merge(df[["id", "label", "color"]], on="id", how="inner")
    latest = latest[~latest["label"].isin(pa["exclude_from_map"])]
    return latest.to_crs(epsg=pa["map_epsg"])


def _longest_line(multiline):
    """Return the single longest line (longer than ``min_front_length_m``) of a (multi)line."""
    parts = gpd.GeoSeries(multiline).explode(index_parts=True)
    return parts[parts.length > ana["min_front_length_m"]].iloc[0]


def load_fronts() -> gpd.GeoDataFrame:
    """Return one terminus line per year (index = year).

    Combines the hand-drawn (1973-1985) and traced (1992-2024) polygons, clips
    them to a shared rectangle, drops ``drop_year`` and reduces every polygon to
    the longest boundary segment (the terminus arc).
    """
    df_old = gpd.read_file(FRONTS_OLD_SHP)
    df_new = gpd.read_file(FRONTS_NEW_GPKG)

    # shared clip rectangle: union of both extents, southern edge pulled up to
    # the traced data, trimmed on the west/east edges and extended to the south
    bounds = df_old.dissolve().union(df_new.dissolve()).bounds
    bounds.loc[0, "miny"] = df_new.dissolve().bounds["miny"].values
    bounds = bounds.values.squeeze().tolist()
    bounds[0] += ana["clip_trim_west_m"]
    bounds[2] -= ana["clip_trim_east_m"]
    bounds[1] -= ana["clip_extend_south_m"]

    df = (
        pd.concat([df_old, df_new], ignore_index=True)
        .dropna(axis=1, how="any")  # drops the all-null 'good_data...' column
        .set_index("year")
    )
    df["geometry"] = df.clip_by_rect(*bounds)
    df = df.drop(index=ana["drop_year"])

    lines = df.boundary.clip_by_rect(bounds[0], bounds[1], bounds[2], ana["clip_top_northing_m"]).apply(
        _longest_line
    )
    return gpd.GeoDataFrame(geometry=lines, crs=df.crs)


def load_sentinel2() -> xr.DataArray:
    """Return the true-colour Sentinel-2 scene as a ``(band, y, x)`` array of reflectance 0-1."""
    da = rioxarray.open_rasterio(SENTINEL2_TIF).astype("float64")
    return da.assign_coords(band=["red", "green", "blue"])


def _panel_label(ax, text):
    """Bottom-left panel label with a dark, semi-transparent backing box."""
    pad = plot["panel_label_pad"]
    ax.text(
        pad,
        pad,
        text,
        transform=ax.transAxes,
        ha="left",
        va="bottom",
        fontsize=plot["label_fontsize"],
        color="white",
        zorder=7,
        bbox=dict(plot["panel_label_box"]),
    )


def plot_retreat_bars(ax, df):
    """Bar plot of the total retreat per glacier, glacier number above each bar."""
    if pa["sort_bars_by"] == "retreat":
        bar_df = df.sort_values("retreat", ascending=False)
    else:  # by glacier number: 1 on the left, N on the right
        bar_df = df.sort_values("label", ascending=True)
    bar_df = bar_df.reset_index(drop=True)

    x = np.arange(len(bar_df))
    ax.bar(
        x,
        bar_df["retreat"],
        color=bar_df["color"],
        edgecolor=pa["bar_edgecolor"],
        linewidth=pa["bar_edge_width"],
        width=pa["bar_width"],
    )
    ax.axhline(0, color=pa["zero_line_color"], linewidth=pa["zero_line_width"])

    pad = pa["number_pad_frac"] * bar_df["retreat"].max()
    for xi, (_, row) in zip(x, bar_df.iterrows()):
        top = max(row["retreat"], 0) + pad
        ax.annotate(
            int(row["label"]),
            (xi, top),
            ha="center",
            va="bottom",
            fontsize=plot["number_fontsize"],
            fontweight="bold",
            color=pa["number_color"],
        )

    ax.set_ylabel(f"{pa['ylabel']} [{ana['retreat_unit']}]", fontsize=plot["label_fontsize"])
    ax.set_xticks([])
    ax.margins(x=pa["margins_x"])
    ax.set_ylim(top=ax.get_ylim()[1] * pa["headroom"])  # headroom for the numbers
    ax.spines[["top", "right", "bottom"]].set_visible(False)


def plot_outline_map(ax, latest):
    """Latest glacier outlines as numbered markers over a web-tile basemap, with the panel (b) box."""
    minx, miny, maxx, maxy = latest.total_bounds
    dx, dy = maxx - minx, maxy - miny
    pad = pa["map_pad_frac"]
    ax.set_xlim(minx - pad * dx, maxx + pad * dx)
    ax.set_ylim(miny - pad * dy, maxy + pad * dy)

    # box marking the extent of panel (b): translucent wide line under a thin one
    hb = gpd.GeoSeries([box(*pa["highlight_bbox_lonlat"])], crs=4326).to_crs(latest.crs).total_bounds
    for style in (pa["highlight_outer"], pa["highlight_inner"]):
        ax.add_patch(
            Rectangle((hb[0], hb[1]), hb[2] - hb[0], hb[3] - hb[1], fill=False, zorder=4, **style)
        )

    for _, row in latest.iterrows():
        c = row.geometry.representative_point()
        black = int(row["label"]) in pa["black_label_numbers"]
        shape = "circle" if row["label"] in pa["marine_terminating"] else "round"
        ann = ax.annotate(
            int(row["label"]),
            (c.x, c.y),
            ha="center",
            va="center",
            fontsize=plot["number_fontsize"],
            fontweight="bold",
            color="black" if black else "white",
            alpha=pa["black_label_alpha"] if black else 1.0,  # marker stays opaque; only text dims
            zorder=5,
            bbox={
                "boxstyle": f"{shape},pad={pa['marker_pad']}",
                "fc": row["color"],
                "ec": pa["marker_edge_color"],
                "lw": pa["marker_edge_width"],
            },
        )
        ann.get_bbox_patch().set_path_effects([
            pe.withSimplePatchShadow(offset=tuple(pa["marker_shadow_offset"]), alpha=pa["marker_shadow_alpha"])
        ])

    provider = reduce(getattr, pa["basemap_provider"].split("."), cx.providers)
    provider.attribution = pa["basemap_attribution"]
    cx.add_basemap(ax, source=provider, crs=latest.crs, attribution_size=pa["basemap_attribution_size"])
    ax.set_xticks([])
    ax.set_yticks([])
    _panel_label(ax, pa["label"])


def plot_front_outlines(ax, fronts, scene, lia):
    """Year-coloured front lines over the Sentinel-2 scene, Little Ice Age line, legend and year colour bar."""
    # pin the (equal-aspect) map to the bottom of its cell so its lower edge lines
    # up with the map of panel (a); clipping the north extent then shortens it upward
    ax.set_anchor("S")

    scene.plot.imshow(ax=ax, vmin=0, vmax=1)
    ax.set_aspect("equal")

    lw = pb["front_linewidth"]
    cmap = plt.get_cmap(pb["front_cmap"])
    fronts.plot(ax=ax, colors=cmap.resampled(len(fronts)).colors, lw=lw, alpha=pb["front_alpha"])

    # keep the panel framed on the scene (the Little Ice Age line extends past it),
    # with the northern part clipped so the colour bar lines up with the bar plot
    xlim, ylim = ax.get_xlim(), ax.get_ylim()
    ylim = (ylim[0], ylim[1] - pb["clip_north_frac"] * (ylim[1] - ylim[0]))

    lia_style = dict(color=pb["lia_color"], linestyle=pb["lia_linestyle"], linewidth=lw, alpha=pb["lia_alpha"])
    lia.to_crs(fronts.crs).plot(ax=ax, zorder=pb["lia_zorder"], **lia_style)
    ax.set_xlim(xlim)
    ax.set_ylim(ylim)

    lia_handle = Line2D(
        [0], [0], color=lia_style["color"], linestyle=lia_style["linestyle"], lw=lw, alpha=lia_style["alpha"],
        label=pb["lia_label"],
    )
    box_style = plot["panel_label_box"]
    leg = ax.legend(handles=[lia_handle], loc=pb["legend_loc"], fontsize=plot["number_fontsize"])
    leg.get_frame().set_facecolor(box_style["fc"])
    leg.get_frame().set_alpha(box_style["alpha"])
    leg.get_frame().set_linewidth(0)
    for txt in leg.get_texts():
        txt.set_color(pb["legend_text_color"])

    ax.set_title("")
    ax.set_xlabel("")
    ax.set_ylabel("")
    ax.set_xticks([])
    ax.set_yticks([])

    # year colour bar above the panel (matches the front colouring: light = oldest)
    years = fronts.index.astype(int).to_numpy()
    norm = mpl.colors.Normalize(vmin=years.min(), vmax=years.max())
    sm = mpl.cm.ScalarMappable(cmap=cmap, norm=norm)
    cax = ax.inset_axes(pb["cbar_inset"])
    cbar = ax.figure.colorbar(sm, cax=cax, orientation="horizontal")
    cbar.ax.xaxis.set_ticks_position("top")
    cbar.ax.xaxis.set_label_position("top")
    cbar.set_label(pb["cbar_label"], fontsize=plot["label_fontsize"])
    cbar.ax.tick_params(labelsize=plot["number_fontsize"])
    _panel_label(ax, pb["label"])


def main() -> None:
    set_paper_style(plot.get("style"))
    df = load_retreat()
    latest = load_latest_outlines(df)
    fronts = load_fronts()
    scene = load_sentinel2()
    lia = gpd.read_file(LIA_GPKG)

    fig = plt.figure(figsize=plot["figsize"], dpi=output["dpi"])
    gs = gridspec.GridSpec(1, 2, width_ratios=plot["width_ratios"], wspace=plot["wspace"], figure=fig)

    # panel (a): bar plot flush above the (equal-aspect) outline map
    inner = gridspec.GridSpecFromSubplotSpec(
        2, 1, subplot_spec=gs[0], height_ratios=pa["height_ratios"], hspace=pa["hspace"]
    )
    ax_bar = plt.subplot(inner[0])
    ax_map = plt.subplot(inner[1])
    plot_retreat_bars(ax_bar, df)
    plot_outline_map(ax_map, latest)
    ax_bar.set_anchor("S")  # pin the panels together so the bar plot meets the map
    ax_map.set_anchor("N")

    plot_front_outlines(plt.subplot(gs[1]), fronts, scene, lia)

    for fmt in output["formats"]:
        fig.savefig(HERE / f"{FIG_STEM}.{fmt}", bbox_inches="tight", dpi=output["dpi"])


if __name__ == "__main__":
    main()
