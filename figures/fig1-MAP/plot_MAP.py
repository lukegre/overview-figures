"""Overview map of the GreenFjord sampling programme.

Recreates ``archive/examples/fig1_overview_map_with_terrain.png`` from
``archive/examples/map.ipynb``: every sampling location from the project
spreadsheet, drawn over the GEUS 1:250 000 topographic map of south Greenland,
with the two intensively studied fjords boxed and a locator inset for context.

What is drawn
-------------
* **Ocean** -- CTD stations joined into the two fjord transects (the glacial
  Sermeliuk line and the Igaliku land-fjord line, each continuing onto the
  shelf) plus loose stations as bare dots. Stations are ordered
  nearest-neighbour so the connecting line follows the fjord rather than the
  order rows happen to sit in the sheet.
* **Human, Cryosphere, Atmosphere, Land, Biodiversity** -- one marker per site.
* Two boxed fjords, settlement names, the diffuse aerosol source region around
  Narsaq, a scale bar, a north arrow, and the locator inset.

Data flow:

    data/greenfjord_sample_locations.csv  (``data/download_sample_locations.py``)
      -> per-cluster filtering and thinning (``analysis``)  -> ocean transects + marker layers
      -> manual ``analysis.edits``
      -> drawn over the GEUS WMTS basemap  (``plot``)

Repeat visits are listed as separate rows in the spreadsheet, so each cluster is
thinned first: points within a cluster-specific distance of each other are
merged to their midpoint (see ``merge_dist_m`` in the config). ``Land`` is
instead averaged per named site. Note that the merge decides *which* rows
survive; the surviving row keeps its own ``Lat``/``Lon``, which is what gets
plotted.

All settings (``inputs``, thinning and manual edits in ``analysis``, extents,
colours, marker sizes, box and label positions and the inset in ``plot``,
``output`` formats and dpi) live in ``config_MAP.yaml`` next to this script.
The order of the marker layers (drawing and legend order) is set by
``analysis.layers``.

Notes
-----
* The basemap is a live WMTS service from GEUS, so the figure needs network
  access. cartopy can only match its tile matrix set if the projection bounds
  are narrowed to what GEUS publishes (``plot.map.projection_bounds``).
* The sampling sheet is not downloaded here; refresh it with
  ``data/download_sample_locations.py``.
* ``archive/examples/utils.py`` also has Copernicus DEM / hillshade helpers.
  They were explored as a basemap but are not used in the final figure, so
  they are not carried over here.

Run from the repository root:

    MPLCONFIGDIR="$TMPDIR/mpl" .venv/bin/python fig1-map_samples/plot_MAP.py
"""

from __future__ import annotations

from itertools import combinations
from pathlib import Path

import cartopy.crs as ccrs
import geopandas as gpd
import matplotlib.patheffects as path_effects
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from cartopy import feature
from matplotlib.patches import Ellipse
from matplotlib_map_utils.core.inset_map import inset_map
from matplotlib_map_utils.core.north_arrow import NorthArrow
from matplotlib_map_utils.core.scale_bar import ScaleBar
from shapely.geometry import LineString, Point, box

from greenfjord.config import get_script_name, read_config
from greenfjord.viz import set_paper_style

# paths and names, derived from the script name (plot_<NAME>.py)
HERE = Path(__file__).resolve().parent
NAME = get_script_name(__file__)  # MAP
FIG_STEM = f"fig_{NAME}"  # prefix of the PNG / PDF outputs

# config
cfg = read_config(HERE / f"config_{NAME}.yaml")
ana = cfg["analysis"]
plot = cfg["plot"]
output = cfg["output"]
SAMPLE_LOCATIONS = HERE / cfg["inputs"]["sample_locations"]
SAMPLE_LOCATIONS_SKIPROWS = cfg["inputs"]["sample_locations_skiprows"]
MUNICIPALITIES = HERE / cfg["inputs"]["municipalities"]
BASEMAP_WMTS_URL = cfg["inputs"]["basemap_wmts_url"]
BASEMAP_WMTS_LAYER = cfg["inputs"]["basemap_wmts_layer"]
WORK_EPSG = ana["work_epsg"]  # metric CRS for distances

PLATE = ccrs.PlateCarree()


# =============================================================================
# geometry helpers (from examples/utils.py)
# =============================================================================
def to_geodataframe(df):
    """Attach point geometry built from the ``Lon``/``Lat`` columns."""
    return gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df["Lon"], df["Lat"]), crs="EPSG:4326")


def merge_adjacent(df, dist_thresh_m):
    """Collapse points closer than ``dist_thresh_m`` to their midpoint.

    Repeat visits to the same site are separate rows in the spreadsheet and
    would otherwise pile up as one indistinguishable blob of markers. Pairs are
    walked in upper-triangle order: the first row of a pair keeps the merged
    geometry and the second is dropped, so a chain of nearby points collapses
    onto the earliest of them.
    """
    df = df.to_crs(epsg=WORK_EPSG)

    dist_squareform = df["geometry"].apply(lambda x: df["geometry"].distance(x))
    near_all = dist_squareform.apply(lambda x: x < dist_thresh_m)
    near_upper_tri = near_all.where(np.triu(np.ones(near_all.shape), 1).astype(bool))

    for i, row in near_upper_tri.iterrows():
        for j, val in row.items():
            if pd.notna(val) and val and i != j and i in df.index and j in df.index:
                midpoint = LineString([df.geometry.loc[i], df.geometry.loc[j]]).centroid
                df.at[i, "geometry"] = midpoint
                df = df.drop(j)

    return df.to_crs(epsg=4326)


def sort_by_distance(df):
    """Order points nearest-neighbour, starting from the most remote one.

    Turns an unordered set of stations into something that can be drawn as a
    single line following the fjord. The start point is the station with the
    largest summed distance to all others, i.e. the far end of the transect.
    """
    df = df.to_crs(epsg=WORK_EPSG)

    dist_squareform = df["geometry"].apply(lambda x: df["geometry"].distance(x))
    geometry = df.geometry.copy(deep=True)

    start = dist_squareform.sum(axis=0).idxmax()
    sorted_idx = [start]
    point = geometry.pop(start)
    for _ in range(len(df) - 1):
        nearest = geometry.distance(point).idxmin()
        sorted_idx.append(nearest)
        point = geometry.pop(nearest)

    return df.loc[sorted_idx].to_crs(epsg=4326)


def plot_unskewed_bbox(ax, bbox, epsg, **plot_kwargs):
    """Draw a lat/lon bounding box as a rectangle in the map projection.

    Reprojecting a lat/lon box into UTM gives a slightly skewed quadrilateral;
    opposite edges are averaged so the drawn box is axis-aligned on the page,
    which is what a "region of interest" annotation should look like.
    """
    corners = gpd.GeoSeries(box(*bbox), crs="EPSG:4326").to_crs(epsg=epsg)
    br, tr, tl, bl = np.array(corners.boundary.iloc[0].xy).T[:-1]

    unskewed = [
        (bl[0] + tl[0]) / 2,  # left
        (br[1] + bl[1]) / 2,  # bottom
        (br[0] + tr[0]) / 2,  # right
        (tr[1] + tl[1]) / 2,  # top
    ]
    x, y = gpd.GeoSeries(box(*unskewed), crs=f"EPSG:{epsg}").boundary.iloc[0].xy
    ax.plot(x, y, **plot_kwargs)


def add_text(ax, lon, lat, label, **kwargs):
    """Map label with a white halo, so it reads over the contoured basemap."""
    conf = plot["text"]
    props = (
        dict(
            transform=PLATE,
            ha="left",
            va="center",
            fontsize=conf["font_size"],
            color=conf["color"],
            zorder=4,
            weight="bold",
        )
        | kwargs
    )

    text = ax.text(lon, lat, label, **props)
    text.set_path_effects([
        path_effects.Stroke(
            linewidth=conf["halo_width"],
            foreground=conf["halo_color"],
            alpha=conf["halo_alpha"],
        ),
        path_effects.Normal(),
    ])
    return text


# =============================================================================
# data
# =============================================================================
def load_samples():
    """The sampling spreadsheet (CSV written by ``data/download_sample_locations.py``)."""
    df = pd.read_csv(SAMPLE_LOCATIONS, skiprows=SAMPLE_LOCATIONS_SKIPROWS)
    return to_geodataframe(df)


def load_municipal_borders():
    """Interior borders between the listed municipalities (coastline excluded).

    Two municipalities share edges where they meet; intersecting their outlines
    keeps just those, so the dashed line never runs along the coast.
    """
    conf = ana["municipalities"]
    gdf = gpd.read_file(MUNICIPALITIES).set_index(conf["name_field"])
    shapes = gdf.loc[conf["names"], "geometry"]

    borders = []
    for (_, a), (_, b) in combinations(shapes.items(), 2):
        shared = a.boundary.intersection(b.boundary)
        if shared.length > 0:
            borders.append(shared)
    return borders


def _startswith_any(series, prefixes):
    """True where the string starts with any of ``prefixes``."""
    filled = series.fillna("")
    mask = pd.Series(False, index=series.index)
    for prefix in prefixes:
        mask |= filled.str.startswith(prefix)
    return mask


def transect_index(ocean, cryosphere, transect_cfg, shelf_cfg):
    """Row labels belonging to one ocean transect."""
    mask = _startswith_any(ocean["Location"], transect_cfg["location_prefixes"])

    # Shelf stations are shared between the two lines and split by Station ID.
    is_shelf = _startswith_any(ocean["Location"], [shelf_cfg["location_prefix"]])
    is_land_line = _startswith_any(ocean["Station ID"], [shelf_cfg["land_fjord_station_prefix"]])
    if transect_cfg["shelf"] == "match":
        mask |= is_shelf & is_land_line
    elif transect_cfg["shelf"] == "other":
        mask |= is_shelf & ~is_land_line

    index = set(ocean.index[mask])
    if transect_cfg.get("include_cryosphere_ctd"):
        index |= set(cryosphere.index[cryosphere["Type"] == "CTD"])
    return sorted(index)


def build_ocean(df):
    """The two fjord transects (ordered along-track) and the leftover stations.

    Returns a list of ``(GeoDataFrame, transect key, draw_line)`` in drawing order.
    """
    conf = ana["ocean"]
    ocean = df[df["Cluster"] == conf["cluster"]]
    cryosphere = df[df["Cluster"] == _cluster_name("cryosphere")]

    layers = []
    claimed = set()
    for transect in conf["transects"]:
        index = transect_index(ocean, cryosphere, transect, conf["shelf"])
        claimed |= set(index)
        track = merge_adjacent(sort_by_distance(df.loc[index]), transect["merge_dist_m"])
        layers.append((track, transect["key"], True))

    other = merge_adjacent(df.loc[ocean.index.difference(claimed)], conf["other"]["merge_dist_m"])
    # Drawn first so the transect lines sit on top of the loose stations.
    return [(other, None, False)] + layers


def _cluster_name(layer_key):
    """The spreadsheet ``Cluster`` value for a marker layer key."""
    for layer in ana["layers"]:
        if layer["key"] == layer_key:
            return layer["cluster"]
    raise KeyError(layer_key)


def build_marker_layer(df, layer_cfg):
    """One thinned GeoDataFrame for a marker cluster."""
    sub = df[df["Cluster"] == layer_cfg["cluster"]]

    if "include_types" in layer_cfg:
        sub = sub[sub["Type"].isin(layer_cfg["include_types"])]
    if "exclude_types" in layer_cfg:
        sub = sub[~sub["Type"].isin(layer_cfg["exclude_types"])]
    if "exclude_location_prefixes" in layer_cfg:
        sub = sub[~_startswith_any(sub["Location"], layer_cfg["exclude_location_prefixes"])]

    if layer_cfg.get("group_by_location"):
        # One dot per named site, at the mean of its samples; the site name
        # becomes the row label so `edits` can address it.
        return sub[["Lat", "Lon", "Location"]].groupby("Location").mean().pipe(to_geodataframe)

    return merge_adjacent(sub, layer_cfg["merge_dist_m"])


def apply_edits(layers):
    """Hand-added and hand-removed sites (see ``analysis.edits`` in the config)."""
    for edit in ana["edits"].get("add", []):
        df = layers[edit["layer"]]
        df.loc[edit["id"], ["Lat", "Lon", "geometry"]] = [
            edit["lat"],
            edit["lon"],
            Point(edit["lon"], edit["lat"]),
        ]
    for edit in ana["edits"].get("drop", []):
        df = layers[edit["layer"]]
        layers[edit["layer"]] = df.drop(index=edit["id"], errors="ignore")
    return layers


# =============================================================================
# map layers
# =============================================================================
def make_projection():
    """UTM 24N, with bounds narrowed to the GEUS WMTS tile matrix set."""
    proj = ccrs.epsg(plot["map"]["epsg"])
    proj.bounds = tuple(plot["map"]["projection_bounds"])
    return proj


def plot_ocean(ax, ocean_layers):
    conf = plot["ocean"]
    handles = []
    for track, key, draw_line in ocean_layers:
        (line,) = ax.plot(
            track["Lon"],
            track["Lat"],
            transform=PLATE,
            color=conf["color"],
            lw=conf["line_width"] if draw_line else 0,
            marker=conf["marker"],
            ms=conf["marker_size"],
            zorder=2,
        )
        if key == conf["legend_transect"]:
            line.set_label(conf["label"])
            handles.append(line)
    return handles


def plot_markers(ax, marker_layers):
    """Draw the marker layers in the order of ``analysis.layers``."""
    conf = plot["markers"]
    handles = []
    for layer in ana["layers"]:
        layer_cfg = conf["layers"][layer["key"]]
        df = marker_layers[layer["key"]]
        (line,) = ax.plot(
            df["Lon"],
            df["Lat"],
            transform=PLATE,
            label=layer_cfg["label"],
            marker=layer_cfg["marker"],
            ms=conf["base_size"] * layer_cfg["size_scale"],
            color=layer_cfg["color"],
            lw=0,
            mew=conf["edge_width"],
            mec=conf["edge_color"],
            zorder=3,
        )
        handles.append(line)
    return handles


def plot_highlight_boxes(ax, epsg):
    conf = plot["highlight_boxes"]
    lw = conf["line_width"]
    for box_cfg in conf["boxes"]:
        plot_unskewed_bbox(
            ax, box_cfg["bbox"], epsg, color=conf["edge_color"], lw=lw, alpha=conf["edge_alpha"]
        )
        plot_unskewed_bbox(
            ax, box_cfg["bbox"], epsg, color=box_cfg["color"], lw=lw * conf["inner_width_scale"]
        )
        add_text(ax, *box_cfg["label_lonlat"], box_cfg["label"])


def plot_atmosphere_area(ax):
    """Nested translucent ellipses, fading outwards, plus a dashed outline."""
    conf = plot["atmosphere_area"]
    center = tuple(conf["center_lonlat"])
    radii = np.linspace(0, conf["max_radius"], conf["n_rings"])

    for radius in radii:
        ax.add_artist(
            Ellipse(
                center,
                width=radius * conf["aspect"],
                height=radius,
                color=conf["color"],
                alpha=conf["alpha"],
                transform=PLATE,
                zorder=1,
            )
        )

    outline = conf["outline"]
    ax.add_artist(
        Ellipse(
            center,
            width=radii[-1] * conf["aspect"],
            height=radii[-1],
            transform=PLATE,
            fc="none",
            color=conf["color"],
            lw=outline["line_width"],
            ls=outline["line_style"],
            alpha=outline["alpha"],
            zorder=1,
        )
    )


def plot_inset_municipalities(small, conf, land_color):
    """Dashed municipal borders and the Kujalleq label on the locator inset."""
    for border in load_municipal_borders():
        for line in getattr(border, "geoms", [border]):
            small.plot(
                *line.xy,
                transform=PLATE,
                color=conf["color"],
                lw=conf["line_width"],
                ls=conf["line_style"],
                alpha=conf["alpha"],
            )

    label = conf["label"]
    small.text(
        *label["lonlat"],
        label["text"],
        transform=PLATE,
        fontsize=label["font_size"],
        alpha=label["alpha"],
        ha="center",
        va="center",
        zorder=5,
        # opaque land-coloured patch so the label is not crossed by the coastline
        bbox=dict(facecolor=land_color, alpha=1, pad=label["bbox_pad"], edgecolor="none"),
    )


def add_legend(ax, handles):
    conf = plot["legend"]
    legend = ax.legend(
        handles,
        [h.get_label() for h in handles],
        ncol=conf["ncol"],
        fontsize=conf["font_size"],
        loc=conf["loc"],
        bbox_to_anchor=tuple(conf["anchor"]),
        framealpha=conf["frame_alpha"],
        edgecolor=conf["edge_color"],
    )
    legend.get_frame().set_linewidth(conf["frame_width"])

    # The inset is a separate axes and is drawn after the main one, so an
    # axes-level legend can end up underneath it. Re-parenting the legend to the
    # figure with a high zorder keeps it on top wherever the inset is placed; it
    # stays anchored to the main axes, so `plot.legend.anchor` is unaffected.
    legend.remove()
    legend.set_zorder(100)
    ax.figure.add_artist(legend)


def add_scale_bar_and_arrow(ax, proj):
    sb_conf = plot["scale_bar"]
    scale_bar = ScaleBar(
        size=sb_conf["size"],
        location=sb_conf["location"],
        bar={"projection": proj, "max": sb_conf["max_km"]},
        labels={"labels": ["", ""]},  # only the total length is labelled
        units={"label": sb_conf["label"]},
        text={"fontsize": sb_conf["font_size"]},
    )

    na_conf = plot["north_arrow"]
    north_arrow = NorthArrow(
        size=na_conf["size"],
        rotation={"crs": proj, "reference": "center"},  # grid north at the map centre
        location=na_conf["location"],
        label=False,
        base={"linewidth": na_conf["line_width"]},
        aob={"bbox_to_anchor": tuple(na_conf["anchor"]), "bbox_transform": ax.transAxes},
        shadow=False,
    )

    ax.add_artist(scale_bar)
    ax.add_artist(north_arrow)


def add_inset_background(ax, conf):
    """Plain panel in the main map's top-left corner for the inset to sit on."""
    # `inset_map` makes its axes a child of `ax` (zorder 99), so the panel must
    # be one too, just below it. Like the inset, its inch size is converted to
    # axes fractions from the main axes' size at the time it is added.
    fig = ax.get_figure()
    bbox = ax.get_window_extent().transformed(fig.dpi_scale_trans.inverted())
    width, height = conf["size"][0] / bbox.width, conf["size"][1] / bbox.height
    panel = ax.inset_axes([0, 1 - height, width, height], zorder=98)
    panel.patch.set_alpha(conf.get("alpha", 1))
    panel.set_facecolor(conf["color"])
    panel.set_xticks([])
    panel.set_yticks([])
    for spine in panel.spines.values():
        spine.set_edgecolor(conf["edge_color"])
        spine.set_linewidth(conf["line_width"])


def add_inset(ax):
    """Locator map of south Greenland with the main extent marked in red."""
    conf = plot["inset"]
    w, e, s, n = plot["map"]["extent"]

    background = conf.get("background", {})
    if background.get("show", False):
        add_inset_background(ax, background)

    small = inset_map(
        ax=ax,
        location=conf["location"],
        pad=tuple(conf["pad"]),
        size=conf["size"],
        xticks=[],
        yticks=[],
        projection=ccrs.Stereographic(**conf["projection"]),
    )

    coast = conf["coastline"]
    small.coastlines(
        resolution=coast["resolution"],
        color=coast["color"],
        lw=coast["line_width"],
        alpha=coast["alpha"],
    )
    small.add_feature(feature.LAND.with_scale(coast["resolution"]), facecolor=conf["land_color"])
    small.set_facecolor("none")
    small.spines["geo"].set_lw(0)
    small.set_extent(conf["extent"], crs=PLATE)

    small.add_geometries(
        geoms=[box(w, s, e, n)],
        crs=PLATE,
        facecolor="none",
        edgecolor=conf["extent_box"]["edge_color"],
        lw=conf["extent_box"]["line_width"],
    )

    style = conf["place_style"]
    for name, (lon, lat) in conf["places"].items():
        small.plot(
            lon,
            lat,
            marker=style["marker"],
            markersize=style["marker_size"],
            color=style["marker_color"],
            lw=style["marker_line_width"],
            transform=PLATE,
        )
        small.text(
            lon + style["label_offset_lon"],
            lat,
            name,
            transform=PLATE,
            fontsize=style["font_size"],
            alpha=style["alpha"],
            va="center",
            # opaque patch so the label is not crossed by the coastline
            bbox=dict(facecolor=conf["land_color"], pad=0, edgecolor="none"),
        )

    plot_inset_municipalities(small, conf["municipalities"], conf["land_color"])
    return small


# =============================================================================
# figure assembly
# =============================================================================
def build_figure():
    df = load_samples()

    ocean_layers = build_ocean(df)
    marker_layers = apply_edits({layer["key"]: build_marker_layer(df, layer) for layer in ana["layers"]})

    proj = make_projection()
    fig, ax = plt.subplots(
        subplot_kw={"projection": proj},
        figsize=plot["figsize"],
        dpi=output["dpi"],
    )

    handles = plot_ocean(ax, ocean_layers)
    handles += plot_markers(ax, marker_layers)
    plot_highlight_boxes(ax, plot["map"]["epsg"])
    add_legend(ax, handles)

    ax.add_wmts(BASEMAP_WMTS_URL, layer_name=BASEMAP_WMTS_LAYER, zorder=1)

    for place in plot["place_names"]:
        add_text(ax, *place["lonlat"], place["text"], weight="normal")

    # The WMTS request is made for the current extent, so set it before the
    # padding is applied and the aerosol blob (which reaches past the coast) is
    # added.
    ax.set_extent(plot["map"]["extent"], crs=PLATE)
    plot_atmosphere_area(ax)

    ax.set_title("")
    ax.set_aspect("equal")
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_xlabel("")
    ax.set_ylabel("")
    ax.spines["geo"].set_linewidth(plot["map"]["spine_width"])

    add_scale_bar_and_arrow(ax, proj)

    padded = [a + b for a, b in zip(plot["map"]["extent"], plot["map"]["extent_pad"])]
    ax.set_extent(padded, crs=PLATE)

    add_inset(ax)
    return fig


def main() -> None:
    set_paper_style(plot.get("style"))
    fig = build_figure()
    for fmt in output["formats"]:
        out = HERE / f"{FIG_STEM}.{fmt}"
        fig.savefig(out, dpi=output["dpi"], bbox_inches="tight")
        print(f"wrote {out}")


if __name__ == "__main__":
    main()
