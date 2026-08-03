"""Recreate the biodiversity overview figure (examples/new_plot.png) from data.

Panels (a, b): commercial fish landings 2012-2024 for the Narsaq and Qaqortoq
           districts (Greenland Statistics table FIX012). Monthly landings per
           vessel type are summed to annual district totals; the three focal
           species get their own line and everything else is pooled into
           "Other species".
Panels (c, d): eDNA community composition along the two GreenFjord 2023
           transects, drawn over the real BedMachine v6 bathymetry of each
           fjord. Each station carries a two-row "flag": the top row is the
           MiFish (12S) fish community, the bottom row the EukAtara (18S)
           plankton community, both as 100 % stacked bars of read counts.

Every subplot is lettered in creation order by ``add_panel_label``: a bold
"(a)" followed by the plain description from ``panel_description`` in the
config, left-aligned above the axes.

The two fjords are the glacial fjord (#54, ~123 km) and the land fjord
(#56, ~78 km). Bathymetry is the BedMachine v6 thalweg: the deepest cell in
each cross-fjord polygon along the centreline, extracted with
``scripts/get_bathymetry.py`` and cached to netCDF (the first run reads the
full GeoTIFF and takes ~30 s). The cross-fjord *median* used by default in
``get_bathymetry.py`` is both rougher and too shallow to contain the deep eDNA
casts, so ``transects.bathymetry.agg_method`` is set to ``min``.

All tweakable elements live in ``config.yaml`` (species lists, colours, axis
limits, and the placement of every composition flag). Run with::

    uv run python plot_biodiversity_transects.py [config.yaml]

Notes on the data
-----------------
* The original ``examples/new_plot.png`` is a mock-up: its landings curves and
  its bathymetry ("Illustrative bathymetry" in its legend) are both invented.
  This script keeps that layout but plots the real numbers, so the curves and
  the fjord sections look different from the mock-up.
* Station distance-from-glacier is measured along the same centreline the
  bathymetry uses, so the dots sit on the section. These come out ~4-5 km
  larger than the hand-digitised values in ``examples/edna_plot.R`` because the
  centreline starts at the head of the catchment rather than at the present-day
  glacier terminus. Set ``transects.distance_from_centerline: false`` to use the
  R values instead.
* MiFish reads assigned only to the genus ``Gadus`` (332 k reads, 100 % identity)
  cannot be split between Atlantic cod and Greenland cod at 12S resolution, so
  they stay in "Other" rather than being called Atlantic cod. Only the two
  sequences explicitly re-assigned in ``examples/edna_plot.R`` become
  *Gadus morhua*. Move ``Gadus`` into ``edna.fish_groups`` in the config to
  change that call.
* Station E (``GF23_E_*``) sits in a side fjord that belongs to neither
  transect and is dropped, as it is in ``examples/edna_plot.R``.
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import xarray as xr
import yaml
from matplotlib.colors import to_rgb
from matplotlib.lines import Line2D
from matplotlib.offsetbox import AnchoredOffsetbox, HPacker, TextArea
from matplotlib.patches import Patch, Rectangle

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE / "scripts"))  # get_bathymetry


# =============================================================================
# shared styling
# =============================================================================
def style_axis(ax, style):
    """Repo-wide axis look: no top/right spines, thin grey spines, inward ticks."""
    ax.spines[["top", "right"]].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(style["spine_color"])
        ax.spines[side].set_linewidth(style["spine_width"])
    ax.tick_params(
        direction="in",
        width=style["tick_width"],
        length=style["tick_length"],
        color=style["spine_color"],
    )


def add_panel_label(ax, letter, description, style):
    """Left-aligned panel label above the axes: bold "(a)" then plain description."""
    size = style["panel_label_size"]
    parts = [TextArea(f"{letter}", textprops={"fontsize": size, "fontweight": "bold"})]
    if description:
        parts.append(TextArea(description, textprops={"fontsize": size}))

    ax.add_artist(
        AnchoredOffsetbox(
            loc="lower left",
            child=HPacker(children=parts, pad=0, sep=6, align="baseline"),
            pad=0,
            borderpad=0,
            frameon=False,
            bbox_to_anchor=(0, 1.02),
            bbox_transform=ax.transAxes,
        )
    )


# =============================================================================
# panels (a, b) -- commercial landings
# =============================================================================
def load_landings(cfg):
    """Annual landings per district and species (tonnes)."""
    conf = cfg["landings"]
    df = pd.read_csv(HERE / cfg["data"]["fish_catch"])
    df["tonnes"] = pd.to_numeric(df[conf["value_column"]].replace(conf["na_value"], np.nan))
    annual = df.groupby(["district", "species", "time"])["tonnes"].sum().unstack("species")

    focal = list(conf["species"])
    out = annual[focal].copy()
    out[conf["other_label"]] = annual.drop(columns=focal).sum(axis=1)
    return out


def plot_landings(ax, landings, district, label, cfg, letter, show_ylabel):
    conf = cfg["landings"]
    style = cfg["style"]
    df = landings.loc[district]
    years = df.index.astype(int)

    for species, color in conf["species"].items():
        ax.plot(years, df[species], color=color, lw=conf["line_width"])
    ax.plot(
        years,
        df[conf["other_label"]],
        color=conf["other_color"],
        lw=conf["other_width"],
    )

    ax.set_xlim(years.min(), years.max())
    ax.set_xticks(conf["xticks"])
    ax.set_ylim(*conf["ylim"])
    ax.set_yticks(conf["yticks"])
    if show_ylabel:
        ax.set_ylabel(conf["ylabel"], fontsize=style["font_size"])
    style_axis(ax, style)
    add_panel_label(ax, letter, conf["panel_description"].format(district=label), style)


# =============================================================================
# panels (c, d) -- eDNA composition
# =============================================================================
def _station_letter(station_id):
    """``GF23_B_355m_edna`` -> ``B``."""
    return station_id.split("_")[1]


def load_stations(cfg):
    """One row per eDNA station: letter, sampling depth, lat/lon."""
    plankton = pd.read_csv(HERE / cfg["data"]["edna_plankton"])
    stations = (
        plankton
        .groupby("ID.Number")
        .agg(
            depth=("Sampling.depth..m.", "first"),
            lat=("GPS.Latitude", "first"),
            lon=("GPS.Longitude", "first"),
        )
        .reset_index()
        .rename(columns={"ID.Number": "station"})
    )
    stations["letter"] = stations["station"].map(_station_letter)
    return stations


def composition(counts, groups, order, other_label):
    """Read counts -> 100 % composition table (station x group), in ``order``."""
    grouped = counts.assign(group=counts["taxon"].map(groups).fillna(other_label))
    wide = grouped.groupby(["station", "group"])["count"].sum().unstack("group").fillna(0)
    for group in order:
        if group not in wide:
            wide[group] = 0.0
    wide = wide[order]
    return wide.div(wide.sum(axis=1), axis=0) * 100


def load_compositions(cfg):
    """Fish and plankton composition tables, both as percentages of reads."""
    conf = cfg["edna"]

    fish = pd.read_csv(HERE / cfg["data"]["edna_fish"])
    # Correct the two mis-assigned Atlantic cod sequences (examples/edna_plot.R).
    is_cod = fish["sequence"].isin(conf["gadus_morhua_sequences"])
    fish.loc[is_cod, "scientific_name"] = "Gadus morhua"
    fish = fish.rename(columns={"ID.Number": "station", "scientific_name": "taxon"})
    fish_pct = composition(
        fish[["station", "taxon", "count"]],
        conf["fish_groups"],
        conf["fish_order"],
        conf["other_label"],
    )

    plankton = pd.read_csv(HERE / cfg["data"]["edna_plankton"])
    plankton = plankton.rename(columns={"ID.Number": "station", "Class": "taxon"})
    plankton_groups = {c: c for c in conf["plankton_classes"]}
    plankton_pct = composition(
        plankton[["station", "taxon", "count"]],
        plankton_groups,
        conf["plankton_order"],
        conf["other_label"],
    )
    return fish_pct, plankton_pct


def load_bathymetry(cfg, fjord_num):
    """Along-centreline bathymetry section, cached after the first extraction."""
    agg_method = cfg["transects"]["bathymetry"]["agg_method"]
    cache = HERE / cfg["data"]["bathymetry_cache"].format(
        fjord_num=fjord_num, agg_method=agg_method
    )
    if cache.exists():
        return xr.open_dataset(cache)

    from get_bathymetry import get_fjord_bathymetry

    section = get_fjord_bathymetry(
        fjord_num,
        fname_bedmachine6=str(HERE / cfg["data"]["bedmachine"]),
        fname_fjord=str(HERE / cfg["data"]["fjord_pickle"]),
        agg_method=agg_method,
    )
    section = section.compute().sortby("distance_to_glacier_km")
    cache.parent.mkdir(parents=True, exist_ok=True)
    section.to_netcdf(cache)
    return section


def centerline_distances(cfg, fjord_num, stations):
    """Distance from the glacier (km) per station, along the fjord centreline."""
    import geopandas as gpd
    from get_bathymetry import open_fjord_data

    fjord = open_fjord_data(fjord_num, fname_fjord=str(HERE / cfg["data"]["fjord_pickle"]))
    polygons = fjord.polygons
    points = gpd.GeoDataFrame(
        stations,
        geometry=gpd.points_from_xy(stations["lon"], stations["lat"]),
        crs=4326,
    ).to_crs(polygons.crs)
    joined = gpd.sjoin_nearest(points, polygons[["distance_m", "geometry"]], how="left")
    return (polygons["distance_m"].max() - joined["distance_m"]) / 1e3


def abbreviate(group, cfg):
    """Two-letter code for a group: from the config, else its first two letters."""
    return cfg["edna"].get("abbrev", {}).get(group, group[:2])


def _relative_luminance(color):
    """WCAG relative luminance of a colour, 0 (black) to 1 (white)."""
    r, g, b = (c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in to_rgb(color))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrasting_text_color(fill_color, label_conf):
    """Dark letters on a light fill, light letters on a dark one."""
    if _relative_luminance(fill_color) > label_conf["luminance_threshold"]:
        return label_conf["color_on_light"]
    return label_conf["color_on_dark"]


def resolve_placement(placement, station_x, station_y):
    """Config placement -> flag centre in data coords.

    ``auto`` in either slot (or as the whole value) takes the station's own
    coordinate, so the flag lines up with its marker on that axis.
    """
    if placement == "auto":
        placement = ("auto", "auto")
    x, y = placement
    return (
        station_x if x == "auto" else x,
        station_y if y == "auto" else y,
    )


def draw_flag(ax, center, size, rows, cfg):
    """Two stacked 100 % bars (fish above plankton) centred on ``center``.

    ``size`` is (width, row height, row gap) in data units, resolved from the
    fractional config values against the panel's own axis ranges.

    Segments that take up at least ``labels.min_width_pct`` % of the bar are
    annotated with their two-letter code, centred in the segment.
    """
    conf = cfg["transects"]["flags"]
    label_conf = conf["labels"]
    colors = cfg["edna"]["colors"]
    width, height, gap = size

    total_height = len(rows) * height + (len(rows) - 1) * gap
    x = center[0] - width / 2
    y = center[1] - total_height / 2

    top = y
    for row in rows:
        if not row:  # no reads for this assay at this station
            ax.add_patch(
                Rectangle(
                    (x, top),
                    width,
                    height,
                    facecolor="none",
                    edgecolor="#999999",
                    linewidth=0.6,
                    linestyle=(0, (2, 2)),
                    zorder=5,
                )
            )
            top += height + gap
            continue
        left = x
        for group, pct in row.items():
            if pct <= 0:
                continue
            segment = width * pct / 100
            ax.add_patch(
                Rectangle(
                    (left, top),
                    segment,
                    height,
                    facecolor=colors[group],
                    edgecolor=conf["edge_color"],
                    linewidth=conf["edge_width"],
                    zorder=5,
                )
            )
            if pct >= label_conf["min_width_pct"]:
                ax.text(
                    left + segment / 2,
                    top + height / 2,
                    abbreviate(group, cfg),
                    color=contrasting_text_color(colors[group], label_conf),
                    fontsize=label_conf["size"],
                    ha="center",
                    va="center",
                    zorder=7,
                    clip_on=False,
                )
            left += segment
        top += height + gap

    return x, y, x + width, top - gap  # flag bounding box


def _snap(value, low, high):
    """Snap to the near edge if ``value`` is outside [low, high], else the midpoint."""
    if value < low:
        return low
    if value > high:
        return high
    return (low + high) / 2


def draw_leader(ax, bbox, station_x, station_y, cfg):
    """Straight leader from the flag to the station dot.

    The anchor snaps to one of the flag's nine handles -- left/middle/right by
    upper/centre/lower -- picking each axis independently: the near edge when the
    station lies beyond the flag on that axis, the midpoint when it lies within.
    """
    conf = cfg["transects"]["flags"]
    x0, y0, x1, y1 = bbox
    anchor_x = _snap(station_x, x0, x1)
    anchor_y = _snap(station_y, y0, y1)  # y0 is the shallow (top) edge
    ax.plot(
        [anchor_x, station_x],
        [anchor_y, station_y],
        color=conf["leader_color"],
        lw=conf["leader_width"],
        zorder=4,
        solid_capstyle="round",
        clip_on=False,  # 2 m stations sit on the axes edge; let the line overflow
    )
    ax.scatter(
        station_x,
        station_y,
        s=conf["marker_size"],
        color=conf["leader_color"],
        zorder=6,
        clip_on=False,  # ... and let the marker draw its full circle above 0 m
    )


def plot_transect(ax, fjord_cfg, cfg, stations, fish_pct, plankton_pct, letter, show_ylabel):
    conf = cfg["transects"]
    style = cfg["style"]
    bath_conf = conf["bathymetry"]

    # -- bathymetry section ---------------------------------------------------
    section = load_bathymetry(cfg, fjord_cfg["fjord_num"])
    dist = section["distance_to_glacier_km"].values
    depth = -section["bathymetry"].values  # positive down
    window = max(1, int(round(bath_conf["smooth_km"] / np.diff(dist).mean())))
    depth = pd.Series(depth).rolling(window, center=True, min_periods=1).mean().values

    floor = fjord_cfg["ylim"][0]
    ax.axhline(0, lw=0.5, color="0.8", zorder=0)
    ax.fill_between(dist, depth, floor, color=bath_conf["fill_color"], zorder=1, linewidth=0)
    ax.plot(
        dist,
        depth,
        color=bath_conf["line_color"],
        lw=bath_conf["line_width"],
        zorder=2,
    )

    # the section is labelled in place rather than in a legend
    text_conf = bath_conf["label"]
    ax.text(
        text_conf["x"],
        text_conf["y"],
        text_conf["text"],
        transform=ax.transAxes,
        color=text_conf["color"],
        fontsize=text_conf["size"],
        ha="left",
        va="bottom",
        zorder=3,
    )

    # -- axes -----------------------------------------------------------------
    ax.set_xlim(*fjord_cfg["xlim"])
    ax.set_ylim(*fjord_cfg["ylim"])
    ax.set_yticks(fjord_cfg["yticks"])
    ax.set_xlabel(conf["xlabel"], fontsize=style["font_size"] + 1)
    if show_ylabel:
        ax.set_ylabel(conf["ylabel"], fontsize=style["font_size"] + 1)
    style_axis(ax, style)
    add_panel_label(ax, letter, conf["panel_description"].format(label=fjord_cfg["label"]), style)

    # -- stations -------------------------------------------------------------
    here = stations[stations["letter"].isin(fjord_cfg["stations"])].copy()
    if conf["distance_from_centerline"]:
        here["distance_km"] = centerline_distances(cfg, fjord_cfg["fjord_num"], here).values
    else:
        here["distance_km"] = here["letter"].map(conf["manual_distance_km"])

    # Flag geometry is a fraction of each panel's own axis ranges, so the bars
    # look the same size in both panels even though their depth ranges differ.
    xspan = abs(fjord_cfg["xlim"][1] - fjord_cfg["xlim"][0])
    yspan = abs(fjord_cfg["ylim"][1] - fjord_cfg["ylim"][0])
    size = (
        conf["flags"]["width_frac"] * xspan,
        conf["flags"]["row_height_frac"] * yspan,
        conf["flags"]["row_gap_frac"] * yspan,
    )
    for _, station in here.iterrows():
        placement = conf["flags"]["placement"].get(station["station"])
        if placement is None:
            continue
        rows = []
        for table in (fish_pct, plankton_pct):
            if station["station"] in table.index:
                rows.append(table.loc[station["station"]].to_dict())
            else:  # no reads for this station (e.g. no fish detected)
                rows.append({})
        center = resolve_placement(placement, station["distance_km"], station["depth"])
        bbox = draw_flag(ax, center, size, rows, cfg)
        draw_leader(ax, bbox, station["distance_km"], station["depth"], cfg)

    return here


# =============================================================================
# legends
# =============================================================================
def add_composition_legends(fig, cfg):
    """Fish / plankton swatch legends plus the section key, along the bottom."""
    conf = cfg["edna"]
    style = cfg["style"]
    layout = cfg["layout"]["legends"]
    colors = conf["colors"]
    y = layout["top"]

    def label(group):
        """ "Atlantic cod" -> "**At**lantic cod": the code bolded where it sits."""
        code = abbreviate(group, cfg)
        if not conf.get("legend_bold_abbrev", True):
            return group
        if group[: len(code)].lower() != code.lower():
            # a hand-written code that is not the start of the name (e.g. "Gh" for
            # Greenland halibut) has nothing to embolden, so spell it out instead
            return f"{group} ({code})"
        return rf"$\mathbf{{{group[: len(code)]}}}${group[len(code) :]}"

    def swatches(groups):
        return [
            Patch(facecolor=colors[g], edgecolor="white", linewidth=0.6, label=label(g))
            for g in groups
        ]

    # The title sits to the left of the swatches rather than above them (a
    # matplotlib legend title is always stacked), so each block is one line.
    for groups, title, dy in (
        (conf["fish_order"], "Fish", 0.0),
        (conf["plankton_order"], "Plankton", -layout["row_gap"]),
    ):
        fig.text(
            layout["left"],
            y + dy,
            title,
            fontsize=style["legend_title_size"],
            fontweight="bold",
            ha="left",
            va="center",
        )
        legend = fig.legend(
            handles=swatches(groups),
            loc="center left",
            bbox_to_anchor=(layout["entries_left"], y + dy),
            ncol=len(groups),
            frameon=False,
            fontsize=style["legend_font_size"],
            handlelength=1.2,
            handleheight=1.0,
            columnspacing=1.0,
            borderpad=0.2,
        )
        fig.add_artist(legend)


def add_landings_legend(axes, cfg):
    """Species-line key, drawn inside one of the landings panels."""
    conf = cfg["landings"]
    # Legend swatches are short, so draw them thicker than the plotted lines.
    scale = cfg["style"]["legend_line_scale"]
    handles = [
        Line2D([], [], color=color, lw=conf["line_width"] * scale, label=species)
        for species, color in conf["species"].items()
    ]
    handles.append(
        Line2D(
            [],
            [],
            color=conf["other_color"],
            lw=conf["other_width"] * scale,
            label=conf["other_label"],
        )
    )
    layout = cfg["layout"]["landings_legend"]
    ax = axes[layout["panel"]]
    ax.legend(
        handles=handles,
        loc=layout["loc"],
        bbox_to_anchor=layout["anchor"],
        ncol=layout["ncol"],
        frameon=False,
        fontsize=cfg["style"]["legend_font_size"],
        handlelength=1.8,
        columnspacing=1.8,
    )


# =============================================================================
# figure assembly
# =============================================================================
def build_figure(cfg):
    style = cfg["style"]
    plt.rcParams["font.size"] = style["font_size"]

    fig = plt.figure(figsize=cfg["output"]["figsize"])

    landings = load_landings(cfg)
    stations = load_stations(cfg)
    fish_pct, plankton_pct = load_compositions(cfg)

    # panels are lettered a, b, c, ... in the order they are created
    letters = iter("abcdefgh")

    # -- landings, one panel per district --------------------------------------
    layout = cfg["layout"]
    top = fig.add_gridspec(nrows=1, ncols=2, **layout["landings"], **layout["shared"])
    landings_axes = []
    for i, (district, label) in enumerate(cfg["landings"]["districts"].items()):
        ax = fig.add_subplot(top[0, i])
        plot_landings(ax, landings, district, label, cfg, next(letters), show_ylabel=(i == 0))
        landings_axes.append(ax)

    add_landings_legend(landings_axes, cfg)

    # -- eDNA transects, one panel per fjord -----------------------------------
    bottom = fig.add_gridspec(nrows=1, ncols=2, **layout["transects"], **layout["shared"])
    for i, fjord_cfg in enumerate(cfg["transects"]["fjords"]):
        ax = fig.add_subplot(bottom[0, i])
        plot_transect(
            ax,
            fjord_cfg,
            cfg,
            stations,
            fish_pct,
            plankton_pct,
            next(letters),
            show_ylabel=(i == 0),
        )

    add_composition_legends(fig, cfg)
    return fig


def main(config_path):
    with open(config_path) as f:
        cfg = yaml.safe_load(f)

    fig = build_figure(cfg)
    out = HERE / cfg["output"]["path"]
    fig.savefig(out, dpi=cfg["output"]["dpi"], bbox_inches="tight")
    print(f"wrote {out}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else HERE / "config.yaml")
