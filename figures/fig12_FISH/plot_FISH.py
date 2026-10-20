"""Commercial fish landings and eDNA community composition along two fjords.

Panels (a, b): commercial fish landings 2012-2024 for the Narsaq and Qaqortoq
           districts (Greenland Statistics table FIX012). Monthly landings per
           vessel type are summed to annual district totals; the focal species
           get their own line and everything else is pooled into "Other species".
Panels (c, d): eDNA community composition along the two GreenFjord 2023
           transects, drawn over the BedMachine v6 bathymetry of each fjord
           (``data/fjord_bathymetry``, read as is). Each station carries a
           two-row "flag": the top row is the MiFish (12S) fish community, the
           bottom row the EukAtara (18S) plankton community, both as 100 %
           stacked bars of read counts.

Every subplot is lettered in creation order by ``add_panel_label``: a bold
"(a)" followed by the plain description from ``panel_description`` in the
config, left-aligned above the axes.

Station distance from the glacier is measured along the fjord centreline
(``analysis.transects.distance_from_centerline``), so the dots sit on the
bathymetry section. Set that switch to false to use the hand-digitised values
in ``analysis.transects.manual_distance_km`` instead.

Notes on the data
-----------------
* MiFish reads assigned only to the genus ``Gadus`` cannot be split between
  Atlantic cod and Greenland cod at 12S resolution, so they stay in "Other".
  Only the two sequences in ``analysis.edna.gadus_morhua_sequences`` (re-assigned
  in ``archive/examples/edna_plot.R``) become *Gadus morhua*.
* Station E (``GF23_E_*``) sits in a side fjord that belongs to neither
  transect and is dropped.

All settings live in ``config_FISH.yaml``. Run from the repository root:

    MPLCONFIGDIR="$TMPDIR/mpl" .venv/bin/python figures/fig12_FISH/plot_FISH.py
"""

from __future__ import annotations

from pathlib import Path

import fjord_props as fp
import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import xarray as xr
from matplotlib.colors import to_rgb
from matplotlib.lines import Line2D
from matplotlib.offsetbox import AnchoredOffsetbox, HPacker, TextArea
from matplotlib.patches import Patch, Rectangle

from greenfjord.config import get_script_name, read_config
from greenfjord.viz import set_paper_style

# paths and names, derived from the script name (plot_<NAME>.py)
HERE = Path(__file__).resolve().parent
NAME = get_script_name(__file__)  # FISH
FIG_STEM = f"fig_{NAME}"  # prefix of the PNG / PDF outputs

# config
cfg = read_config(HERE / f"config_{NAME}.yaml")
inputs = cfg["inputs"]
ana = cfg["analysis"]
plot = cfg["plot"]
output = cfg["output"]


# =============================================================================
# shared styling
# =============================================================================
def style_axis(ax):
    """Repo-wide axis look: no top/right spines, thin grey spines, inward ticks."""
    ax.spines[["top", "right"]].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(plot["spine_color"])
        ax.spines[side].set_linewidth(plot["spine_width"])
    ax.tick_params(
        direction="in",
        width=plot["tick_width"],
        length=plot["tick_length"],
        color=plot["spine_color"],
    )


def add_panel_label(ax, letter, description):
    """Left-aligned panel label above the axes: bold "(a)" then plain description."""
    size = plot["panel_label_size"]
    parts = [TextArea(letter, textprops={"fontsize": size, "fontweight": "bold"})]
    if description:
        parts.append(TextArea(description, textprops={"fontsize": size}))

    ax.add_artist(
        AnchoredOffsetbox(
            loc="lower left",
            child=HPacker(children=parts, pad=0, sep=plot["panel_label_sep"], align="baseline"),
            pad=0,
            borderpad=0,
            frameon=False,
            bbox_to_anchor=(0, plot["panel_label_y"]),
            bbox_transform=ax.transAxes,
        )
    )


# =============================================================================
# panels (a, b) -- commercial landings
# =============================================================================
def load_landings():
    """Annual landings per district and species (tonnes)."""
    conf = ana["landings"]
    df = pd.read_csv(HERE / inputs["fish_catch"])
    df["tonnes"] = pd.to_numeric(df[conf["value_column"]].replace(conf["na_value"], np.nan))
    annual = df.groupby(["district", "species", "time"])["tonnes"].sum().unstack("species")

    focal = list(conf["species"])
    out = annual[focal].copy()
    out[conf["other_label"]] = annual.drop(columns=focal).sum(axis=1)
    return out


def plot_landings(ax, landings, district, label, letter, show_ylabel):
    conf = plot["panels"]["landings"]
    other_label = ana["landings"]["other_label"]
    df = landings.loc[district]
    years = df.index.astype(int)

    for species in ana["landings"]["species"]:
        ax.plot(years, df[species], color=conf["species_colors"][species], lw=conf["line_width"])
    ax.plot(years, df[other_label], color=conf["other_color"], lw=conf["other_width"])

    ax.set_xlim(years.min(), years.max())
    ax.set_xticks(conf["xticks"])
    ax.set_ylim(*conf["ylim"])
    ax.set_yticks(conf["yticks"])
    if show_ylabel:
        ax.set_ylabel(conf["ylabel"], fontsize=plot["style"]["font.size"])
    style_axis(ax)
    add_panel_label(ax, letter, conf["panel_description"].format(district=label))


# =============================================================================
# panels (c, d) -- eDNA composition
# =============================================================================
def _station_letter(station_id):
    """``GF23_B_355m_edna`` -> ``B``."""
    return station_id.split("_")[1]


def load_stations():
    """One row per eDNA station: letter, sampling depth, lat/lon."""
    plankton = pd.read_csv(HERE / inputs["edna_plankton"])
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


def load_compositions():
    """Fish and plankton composition tables, both as percentages of reads."""
    conf = ana["edna"]
    panel = plot["panels"]["edna"]

    fish = pd.read_csv(HERE / inputs["edna_fish"])
    # Correct the two mis-assigned Atlantic cod sequences (archive/examples/edna_plot.R).
    is_cod = fish["sequence"].isin(conf["gadus_morhua_sequences"])
    fish.loc[is_cod, "scientific_name"] = "Gadus morhua"
    fish = fish.rename(columns={"ID.Number": "station", "scientific_name": "taxon"})
    fish_pct = composition(
        fish[["station", "taxon", "count"]],
        conf["fish_groups"],
        panel["fish_order"],
        conf["other_label"],
    )

    plankton = pd.read_csv(HERE / inputs["edna_plankton"])
    plankton = plankton.rename(columns={"ID.Number": "station", "Class": "taxon"})
    plankton_groups = {c: c for c in conf["plankton_classes"]}
    plankton_pct = composition(
        plankton[["station", "taxon", "count"]],
        plankton_groups,
        panel["plankton_order"],
        conf["other_label"],
    )
    return fish_pct, plankton_pct


def load_bathymetry(fjord_num):
    """Along-centreline BedMachine section from the shared dataset (variables
    ``bathymetry`` in m and ``distance_to_glacier_km``, sorted by distance)."""
    path = inputs["bathymetry"].format(
        agg_method=ana["transects"]["bathymetry_agg_method"], fjord_num=fjord_num
    )
    return xr.open_dataset(HERE / path)


def centerline_distances(fjord_num, stations):
    """Distance from the glacier (km) per station, along the fjord centreline."""
    fjord = fp.FjordAggregator.from_pickle(str(HERE / inputs["fjord_pickle"].format(fjord_num=fjord_num)))
    polygons = fjord.compute_polygons(interp_distance_m=ana["transects"]["centerline_grid_m"])
    points = gpd.GeoDataFrame(
        stations,
        geometry=gpd.points_from_xy(stations["lon"], stations["lat"]),
        crs=4326,
    ).to_crs(polygons.crs)
    joined = gpd.sjoin_nearest(points, polygons[["distance_m", "geometry"]], how="left")
    return (polygons["distance_m"].max() - joined["distance_m"]) / 1e3


def abbreviate(group):
    """Two-letter code for a group: from the config, else its first two letters."""
    return plot["panels"]["edna"]["abbrev"].get(group, group[:2])


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


def draw_flag(ax, center, size, rows):
    """Two stacked 100 % bars (fish above plankton) centred on ``center``.

    ``size`` is (width, row height, row gap) in data units, resolved from the
    fractional config values against the panel's own axis ranges.

    Segments that take up at least ``labels.min_width_pct`` % of the bar are
    annotated with their two-letter code, centred in the segment.
    """
    conf = plot["panels"]["transects"]["flags"]
    label_conf = conf["labels"]
    colors = plot["panels"]["edna"]["colors"]
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
                    edgecolor=conf["empty_edge_color"],
                    linewidth=conf["empty_edge_width"],
                    linestyle=(0, tuple(conf["empty_dashes"])),
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
                    abbreviate(group),
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


def draw_leader(ax, bbox, station_x, station_y):
    """Straight leader from the flag to the station dot.

    The anchor snaps to one of the flag's nine handles -- left/middle/right by
    upper/centre/lower -- picking each axis independently: the near edge when the
    station lies beyond the flag on that axis, the midpoint when it lies within.
    """
    conf = plot["panels"]["transects"]["flags"]
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


def plot_transect(ax, fjord, stations, fish_pct, plankton_pct, letter, show_ylabel):
    """One fjord long-section: bathymetry, axes, and the station flags.

    ``fjord`` merges the station list from ``analysis.transects.fjords`` with
    the panel settings from ``plot.panels.transects.fjords``.
    """
    ana_conf = ana["transects"]
    conf = plot["panels"]["transects"]
    bath_conf = conf["bathymetry"]

    # -- bathymetry section ---------------------------------------------------
    with load_bathymetry(fjord["fjord_num"]) as section:
        dist = section["distance_to_glacier_km"].values
        depth = -section["bathymetry"].values  # positive down
    window = max(1, int(round(ana_conf["bathymetry_smooth_km"] / np.diff(dist).mean())))
    depth = pd.Series(depth).rolling(window, center=True, min_periods=1).mean().values

    floor = fjord["ylim"][0]
    ax.axhline(0, lw=conf["sea_level_width"], color=conf["sea_level_color"], zorder=0)
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
    ax.set_xlim(*fjord["xlim"])
    ax.set_ylim(*fjord["ylim"])
    ax.set_yticks(fjord["yticks"])
    ax.set_xlabel(conf["xlabel"], fontsize=conf["axis_label_size"])
    if show_ylabel:
        ax.set_ylabel(conf["ylabel"], fontsize=conf["axis_label_size"])
    style_axis(ax)
    add_panel_label(ax, letter, conf["panel_description"].format(label=fjord["label"]))

    # -- stations -------------------------------------------------------------
    here = stations[stations["letter"].isin(fjord["stations"])].copy()
    if ana_conf["distance_from_centerline"]:
        here["distance_km"] = centerline_distances(fjord["fjord_num"], here).values
    else:
        here["distance_km"] = here["letter"].map(ana_conf["manual_distance_km"])

    # Flag geometry is a fraction of each panel's own axis ranges, so the bars
    # look the same size in both panels even though their depth ranges differ.
    flags = conf["flags"]
    xspan = abs(fjord["xlim"][1] - fjord["xlim"][0])
    yspan = abs(fjord["ylim"][1] - fjord["ylim"][0])
    size = (
        flags["width_frac"] * xspan,
        flags["row_height_frac"] * yspan,
        flags["row_gap_frac"] * yspan,
    )
    for _, station in here.iterrows():
        placement = flags["placement"].get(station["station"])
        if placement is None:
            continue
        rows = []
        for table in (fish_pct, plankton_pct):
            if station["station"] in table.index:
                rows.append(table.loc[station["station"]].to_dict())
            else:  # no reads for this station (e.g. no fish detected)
                rows.append({})
        center = resolve_placement(placement, station["distance_km"], station["depth"])
        bbox = draw_flag(ax, center, size, rows)
        draw_leader(ax, bbox, station["distance_km"], station["depth"])

    return here


# =============================================================================
# legends
# =============================================================================
def add_composition_legends(fig):
    """Fish / plankton swatch legends along the bottom, one line each."""
    edna = plot["panels"]["edna"]
    layout = plot["layout"]["legends"]
    swatch = plot["swatch_legend"]
    titles = plot["legend_titles"]
    colors = edna["colors"]
    y = layout["top"]

    def label(group):
        """ "Atlantic cod" -> "**At**lantic cod": the code bolded where it sits."""
        code = abbreviate(group)
        if not edna["legend_bold_abbrev"]:
            return group
        if group[: len(code)].lower() != code.lower():
            # a hand-written code that is not the start of the name (e.g. "Gh" for
            # Greenland halibut) has nothing to embolden, so spell it out instead
            return f"{group} ({code})"
        return rf"$\mathbf{{{group[: len(code)]}}}${group[len(code) :]}"

    def swatches(groups):
        return [
            Patch(
                facecolor=colors[g],
                edgecolor=swatch["edge_color"],
                linewidth=swatch["edge_width"],
                label=label(g),
            )
            for g in groups
        ]

    # The title sits to the left of the swatches rather than above them (a
    # matplotlib legend title is always stacked), so each block is one line.
    for groups, title, dy in (
        (edna["fish_order"], titles["fish"], 0.0),
        (edna["plankton_order"], titles["plankton"], -layout["row_gap"]),
    ):
        fig.text(
            layout["left"],
            y + dy,
            title,
            fontsize=plot["legend_title_size"],
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
            fontsize=plot["legend_font_size"],
            handlelength=swatch["handlelength"],
            handleheight=swatch["handleheight"],
            columnspacing=swatch["columnspacing"],
            borderpad=swatch["borderpad"],
        )
        fig.add_artist(legend)


def add_landings_legend(axes):
    """Species-line key, drawn inside one of the landings panels."""
    conf = plot["panels"]["landings"]
    landings = ana["landings"]
    # Legend swatches are short, so draw them thicker than the plotted lines.
    scale = plot["legend_line_scale"]
    handles = [
        Line2D([], [], color=conf["species_colors"][species], lw=conf["line_width"] * scale, label=species)
        for species in landings["species"]
    ]
    handles.append(
        Line2D(
            [],
            [],
            color=conf["other_color"],
            lw=conf["other_width"] * scale,
            label=landings["other_label"],
        )
    )
    layout = plot["layout"]["landings_legend"]
    ax = axes[layout["panel"]]
    ax.legend(
        handles=handles,
        loc=layout["loc"],
        bbox_to_anchor=layout["anchor"],
        ncol=layout["ncol"],
        frameon=False,
        fontsize=plot["legend_font_size"],
        **plot["line_legend"],
    )


# =============================================================================
# figure assembly
# =============================================================================
def build_figure():
    fig = plt.figure(figsize=plot["figsize"])

    landings = load_landings()
    stations = load_stations()
    fish_pct, plankton_pct = load_compositions()

    # panels are lettered a, b, c, ... in the order they are created
    letters = iter("abcdefgh")
    layout = plot["layout"]

    # -- landings, one panel per district --------------------------------------
    top = fig.add_gridspec(nrows=1, ncols=2, **layout["landings"], **layout["shared"])
    landings_axes = []
    for i, (district, label) in enumerate(ana["landings"]["districts"].items()):
        ax = fig.add_subplot(top[0, i])
        plot_landings(ax, landings, district, label, next(letters), show_ylabel=(i == 0))
        landings_axes.append(ax)

    add_landings_legend(landings_axes)

    # -- eDNA transects, one panel per fjord -----------------------------------
    panel_fjords = {f["fjord_num"]: f for f in plot["panels"]["transects"]["fjords"]}
    bottom = fig.add_gridspec(nrows=1, ncols=2, **layout["transects"], **layout["shared"])
    for i, transect in enumerate(ana["transects"]["fjords"]):
        fjord = {**transect, **panel_fjords[transect["fjord_num"]]}
        ax = fig.add_subplot(bottom[0, i])
        plot_transect(
            ax,
            fjord,
            stations,
            fish_pct,
            plankton_pct,
            next(letters),
            show_ylabel=(i == 0),
        )

    add_composition_legends(fig)
    return fig


def main() -> None:
    set_paper_style(plot.get("style"))

    fig = build_figure()
    for fmt in output["formats"]:
        fig.savefig(HERE / f"{FIG_STEM}.{fmt}", dpi=output["dpi"], bbox_inches="tight")


if __name__ == "__main__":
    main()
