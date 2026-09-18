"""Overview map of the GreenFjord sampling programme (Fig. 1).

Recreates ``examples/fig1_overview_map_with_terrain.png`` from
``examples/map.ipynb``: every sampling location from the project spreadsheet,
drawn over the GEUS 1:250 000 topographic map of south Greenland, with the two
intensively studied fjords boxed and a locator inset for context.

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

Repeat visits are listed as separate rows in the spreadsheet, so each cluster is
thinned first: points within a cluster-specific distance of each other are
merged to their midpoint (see ``merge_dist_m`` in the config). ``Land`` is
instead averaged per named site. Note that the merge decides *which* rows
survive; the surviving row keeps its own ``Lat``/``Lon``, which is what gets
plotted.

Everything adjustable -- extents, colours, marker sizes, box and label
positions, the inset, the two manual location edits -- lives in
``config.yaml``. Run with::

    uv run python plot_overview_map.py [config.yaml]

Notes
-----
* The basemap is a live WMTS service from GEUS, so the figure needs network
  access. cartopy can only match its tile matrix set if the projection bounds
  are narrowed to what GEUS publishes (``map.projection_bounds``).
* The sampling sheet is downloaded once and cached under ``data/``; delete the
  cache or set ``data.use_cache: false`` to refresh it.
* ``examples/utils.py`` also has Copernicus DEM / hillshade helpers. They were
  explored as a basemap but are not used in the final figure, so they are not
  carried over here.
"""

from __future__ import annotations

import sys
from pathlib import Path

import cartopy.crs as ccrs
import geopandas as gpd
import matplotlib.patheffects as path_effects
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yaml
from cartopy import feature
from matplotlib.patches import Ellipse
from matplotlib_map_utils.core.inset_map import inset_map
from matplotlib_map_utils.core.north_arrow import NorthArrow
from matplotlib_map_utils.core.scale_bar import ScaleBar
from shapely.geometry import LineString, Point, box

HERE = Path(__file__).parent
PLATE = ccrs.PlateCarree()


# =============================================================================
# geometry helpers (from examples/utils.py)
# =============================================================================
def to_geodataframe(df):
    """Attach point geometry built from the ``Lon``/``Lat`` columns."""
    return gpd.GeoDataFrame(
        df, geometry=gpd.points_from_xy(df["Lon"], df["Lat"]), crs="EPSG:4326"
    )


def merge_adjacent(df, dist_thresh_m, work_epsg=32624):
    """Collapse points closer than ``dist_thresh_m`` to their midpoint.

    Repeat visits to the same site are separate rows in the spreadsheet and
    would otherwise pile up as one indistinguishable blob of markers. Pairs are
    walked in upper-triangle order: the first row of a pair keeps the merged
    geometry and the second is dropped, so a chain of nearby points collapses
    onto the earliest of them.
    """
    df = df.to_crs(epsg=work_epsg)

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


def sort_by_distance(df, work_epsg=32624):
    """Order points nearest-neighbour, starting from the most remote one.

    Turns an unordered set of stations into something that can be drawn as a
    single line following the fjord. The start point is the station with the
    largest summed distance to all others, i.e. the far end of the transect.
    """
    df = df.to_crs(epsg=work_epsg)

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


def add_text(ax, lon, lat, label, cfg, **kwargs):
    """Map label with a white halo, so it reads over the contoured basemap."""
    conf = cfg["text"]
    props = dict(
        transform=PLATE,
        ha="left",
        va="center",
        fontsize=conf["font_size"],
        color=conf["color"],
        zorder=4,
        weight="bold",
    ) | kwargs

    text = ax.text(lon, lat, label, **props)
    text.set_path_effects(
        [
            path_effects.Stroke(
                linewidth=conf["halo_width"],
                foreground=conf["halo_color"],
                alpha=conf["halo_alpha"],
            ),
            path_effects.Normal(),
        ]
    )
    return text


# =============================================================================
# data
# =============================================================================
def load_samples(cfg):
    """The sampling spreadsheet, cached verbatim after the first download."""
    conf = cfg["data"]
    cache = HERE / conf["cache"]

    if not (conf.get("use_cache", True) and cache.exists()):
        import urllib.request

        cache.parent.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(conf["url"], cache)

    df = pd.read_csv(cache, skiprows=conf["skiprows"])
    return to_geodataframe(df)


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
    is_land_line = _startswith_any(
        ocean["Station ID"], [shelf_cfg["land_fjord_station_prefix"]]
    )
    if transect_cfg["shelf"] == "match":
        mask |= is_shelf & is_land_line
    elif transect_cfg["shelf"] == "other":
        mask |= is_shelf & ~is_land_line

    index = set(ocean.index[mask])
    if transect_cfg.get("include_cryosphere_ctd"):
        index |= set(cryosphere.index[cryosphere["Type"] == "CTD"])
    return sorted(index)


def build_ocean(df, cfg):
    """The two fjord transects (ordered along-track) and the leftover stations.

    Returns a list of ``(GeoDataFrame, label, draw_line)`` in drawing order.
    """
    conf = cfg["ocean"]
    ocean = df[df["Cluster"] == conf["cluster"]]
    cryosphere = df[df["Cluster"] == _cluster_name(cfg, "cryosphere")]

    layers = []
    claimed = set()
    for transect in conf["transects"]:
        index = transect_index(ocean, cryosphere, transect, conf["shelf"])
        claimed |= set(index)
        track = merge_adjacent(
            sort_by_distance(df.loc[index]), transect["merge_dist_m"]
        )
        layers.append((track, transect["label"], True))

    other = merge_adjacent(
        df.loc[ocean.index.difference(claimed)], conf["other"]["merge_dist_m"]
    )
    # Drawn first so the transect lines sit on top of the loose stations.
    return [(other, None, False)] + layers


def _cluster_name(cfg, layer_key):
    """The spreadsheet ``Cluster`` value for a marker layer key."""
    for layer in cfg["markers"]["layers"]:
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
        return (
            sub[["Lat", "Lon", "Location"]]
            .groupby("Location")
            .mean()
            .pipe(to_geodataframe)
        )

    return merge_adjacent(sub, layer_cfg["merge_dist_m"])


def apply_edits(layers, cfg):
    """Hand-added and hand-removed sites (see ``edits`` in the config)."""
    for edit in cfg["edits"].get("add", []):
        df = layers[edit["layer"]]
        df.loc[edit["id"], ["Lat", "Lon", "geometry"]] = [
            edit["lat"],
            edit["lon"],
            Point(edit["lon"], edit["lat"]),
        ]
    for edit in cfg["edits"].get("drop", []):
        df = layers[edit["layer"]]
        layers[edit["layer"]] = df.drop(index=edit["id"], errors="ignore")
    return layers


# =============================================================================
# map layers
# =============================================================================
def make_projection(cfg):
    """UTM 24N, with bounds narrowed to the GEUS WMTS tile matrix set."""
    proj = ccrs.epsg(cfg["map"]["epsg"])
    proj.bounds = tuple(cfg["map"]["projection_bounds"])
    return proj


def plot_ocean(ax, ocean_layers, cfg):
    conf = cfg["ocean"]
    handles = []
    for track, label, draw_line in ocean_layers:
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
        if label:
            line.set_label(label)
            handles.append(line)
    return handles


def plot_markers(ax, marker_layers, cfg):
    conf = cfg["markers"]
    handles = []
    for layer_cfg in conf["layers"]:
        df = marker_layers[layer_cfg["key"]]
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


def plot_highlight_boxes(ax, cfg, epsg):
    conf = cfg["highlight_boxes"]
    lw = conf["line_width"]
    for box_cfg in conf["boxes"]:
        plot_unskewed_bbox(
            ax, box_cfg["bbox"], epsg, color=conf["edge_color"], lw=lw, alpha=conf["edge_alpha"]
        )
        plot_unskewed_bbox(
            ax, box_cfg["bbox"], epsg, color=box_cfg["color"], lw=lw * conf["inner_width_scale"]
        )
        add_text(ax, *box_cfg["label_lonlat"], box_cfg["label"], cfg)


def plot_atmosphere_area(ax, cfg):
    """Nested translucent ellipses, fading outwards, plus a dashed outline."""
    conf = cfg["atmosphere_area"]
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


def add_legend(ax, handles, cfg):
    conf = cfg["legend"]
    legend = ax.legend(
        handles,
        [h.get_label() for h in handles],
        ncol=conf["ncol"],
        fontsize=conf["font_size"],
        loc=conf["loc"],
        bbox_to_anchor=tuple(conf["anchor"]),
        framealpha=1,
        edgecolor=conf["edge_color"],
    )
    legend.get_frame().set_linewidth(conf["frame_width"])

    # The inset is a separate axes and is drawn after the main one, so an
    # axes-level legend can end up underneath it. Re-parenting the legend to the
    # figure with a high zorder keeps it on top wherever the inset is placed; it
    # stays anchored to the main axes, so `legend.anchor` is unaffected.
    legend.remove()
    legend.set_zorder(100)
    ax.figure.add_artist(legend)


def add_scale_bar_and_arrow(ax, cfg, proj):
    sb_conf = cfg["scale_bar"]
    scale_bar = ScaleBar(
        size=sb_conf["size"],
        location=sb_conf["location"],
        bar={"projection": proj, "max": sb_conf["max_km"]},
        labels={"labels": ["", ""]},  # only the total length is labelled
        units={"label": sb_conf["label"]},
        text={"fontsize": sb_conf["font_size"]},
    )

    na_conf = cfg["north_arrow"]
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


def add_inset(ax, cfg):
    """Locator map of south Greenland with the main extent marked in red."""
    conf = cfg["inset"]
    w, e, s, n = cfg["map"]["extent"]

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
    small.add_feature(
        feature.LAND.with_scale(coast["resolution"]), facecolor=conf["land_color"]
    )
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
            color="k",
            lw=0.5,
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

    return small


# =============================================================================
# figure assembly
# =============================================================================
def build_figure(cfg):
    df = load_samples(cfg)

    ocean_layers = build_ocean(df, cfg)
    marker_layers = apply_edits(
        {
            layer["key"]: build_marker_layer(df, layer)
            for layer in cfg["markers"]["layers"]
        },
        cfg,
    )

    proj = make_projection(cfg)
    fig, ax = plt.subplots(
        subplot_kw={"projection": proj},
        figsize=cfg["output"]["figsize"],
        dpi=cfg["output"]["dpi"],
    )

    handles = plot_ocean(ax, ocean_layers, cfg)
    handles += plot_markers(ax, marker_layers, cfg)
    plot_highlight_boxes(ax, cfg, cfg["map"]["epsg"])
    add_legend(ax, handles, cfg)

    base = cfg["basemap"]
    ax.add_wmts(base["url"], layer_name=base["layer"], zorder=1)

    for place in cfg["place_names"]:
        add_text(ax, *place["lonlat"], place["text"], cfg, weight="normal")

    # The WMTS request is made for the current extent, so set it before the
    # padding is applied and the aerosol blob (which reaches past the coast) is
    # added.
    ax.set_extent(cfg["map"]["extent"], crs=PLATE)
    plot_atmosphere_area(ax, cfg)

    ax.set_title("")
    ax.set_aspect("equal")
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_xlabel("")
    ax.set_ylabel("")
    ax.spines["geo"].set_linewidth(cfg["map"]["spine_width"])

    add_scale_bar_and_arrow(ax, cfg, proj)

    padded = [a + b for a, b in zip(cfg["map"]["extent"], cfg["map"]["extent_pad"])]
    ax.set_extent(padded, crs=PLATE)

    add_inset(ax, cfg)
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
