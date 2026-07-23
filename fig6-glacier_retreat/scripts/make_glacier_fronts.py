"""
Glacier fronts figure (Qalerallit Sermia, South Greenland).

Recreates ``glacier-fronts.png``: the traced glacier-front outlines for every
available year (1973 -> 2023), drawn over a true-colour Sentinel-2 summer scene.
Each front is coloured by year with ``inferno_r`` (earliest = light/yellow,
latest = dark), so the colour ramp reads as the terminus retreating through time.

Data (all local, in ``glacier_i16n6104w4669/``):
  - glacier_i16n6104w4669-landsat_l1-1973_1985-handdrawn_v2.shp
        hand-drawn front polygons for the three oldest years (1973, 1981, 1985).
  - glacier_i16n6104w4669_poly-manually_adjusted.gpkg
        automatically traced + manually adjusted front polygons, 1992 -> 2024.
  - glacier_i16n6104w4669_sentinel2-truecolor-2024-08.tif  (basemap)
        processed true-colour Sentinel-2 scene used as the backdrop. Created on
        first run by downloading from the Microsoft Planetary Computer, then
        cached here so subsequent runs are fully offline. Delete it to refetch.

This is a self-contained port of notebook ``4_qalerallit_glacier.ipynb`` /
``src.viz.plot_outlines_with_sentinel_scene``; no project ``src`` package needed.
It is imported by ``../plot_glacier_retreat.py`` (right panel) and can also be run
standalone to regenerate the individual ``examples/glacier-fronts.png``.

Run:
    ../../.venv/bin/python scripts/make_glacier_fronts.py
"""

from __future__ import annotations

import os
import warnings
from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import pandas as pd
import rioxarray  # noqa: F401  (registers the .rio accessor)
import xarray as xr

warnings.filterwarnings("ignore")

# --------------------------------------------------------------------------- #
# CONFIG
# --------------------------------------------------------------------------- #
# data lives in ../data relative to this script (folder was reorganised 2026-07)
_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = _ROOT / "data" / "glacier_i16n6104w4669"
SHP_OLD = DATA_DIR / "glacier_i16n6104w4669-landsat_l1-1973_1985-handdrawn_v2.shp"
GPKG_NEW = DATA_DIR / "glacier_i16n6104w4669_poly-manually_adjusted.gpkg"
WATER = DATA_DIR / "glacier_i16n6104w4669_water.gpkg"
BASEMAP_TIF = DATA_DIR / "glacier_i16n6104w4669_sentinel2-truecolor-2024-08.tif"

OUT_FIG = _ROOT / "examples" / "glacier-fronts.png"

EPSG = 32623  # UTM zone 23N (native CRS of all the vector data)
BBOX_OFFSET = (0, -0.04, 0, 0.03)  # lon/lat padding around the fronts [degrees]
DROP_YEAR = 2024  # last outline dropped (partial / mismatched trace)
CLIP_TOP_Y = 6_772_000  # clip boundaries above this northing (drops ice-cap edge)
MIN_LINE_LEN = 10_000  # keep only front segments longer than this [m]

# Sentinel-2 basemap acquisition (only used if BASEMAP_TIF is missing)
S2_YEAR, S2_MONTH = 2024, 8
S2_MAX_CLOUD = 10
S2_NORM_DENOM = 7000  # reflectance scaling before histogram equalisation

DPI = 200


# --------------------------------------------------------------------------- #
# OUTLINES
# --------------------------------------------------------------------------- #
def load_fronts():
    """Load every glacier-front outline as year-indexed boundary lines.

    Combines the hand-drawn (1973-1985) and traced (1992-2024) fronts, clips
    them to a common rectangle, drops the incomplete last year, and reduces each
    polygon to its single longest boundary line (the terminus arc).
    """
    df_old = gpd.read_file(SHP_OLD)
    df_new = gpd.read_file(GPKG_NEW)

    # shared clip rectangle: union of both extents, but with the southern edge
    # pulled up to the traced data and trimmed 700 m on each side / 3 km south.
    bounds = df_old.dissolve().union(df_new.dissolve()).bounds
    bounds.loc[0, "miny"] = df_new.dissolve().bounds["miny"].values
    bounds = bounds.values.squeeze().tolist()
    bounds[0] += 700
    bounds[2] -= 700
    bounds[1] -= 3000

    df = (
        pd.concat([df_old, df_new], ignore_index=True)
        .dropna(axis=1, how="any")  # drops the all-null 'good_data...' column
        .set_index("year")
    )
    df["geometry"] = df.clip_by_rect(*bounds)
    df = df.drop(index=DROP_YEAR)

    # polygon -> boundary line, clipped, keeping only the longest segment
    lines = (
        df.boundary.clip_by_rect(bounds[0], bounds[1], bounds[2], CLIP_TOP_Y)
        .apply(_longest_line)
    )
    return gpd.GeoDataFrame(geometry=lines, crs=df.crs)


def _longest_line(multiline, thresh=MIN_LINE_LEN):
    """Return the single longest line ( > thresh metres) of a (multi)line."""
    parts = gpd.GeoSeries(multiline).explode(index_parts=True)
    return parts[parts.length > thresh].iloc[0]


# --------------------------------------------------------------------------- #
# BASEMAP (Sentinel-2 true colour, cached locally)
# --------------------------------------------------------------------------- #
def load_basemap(bbox_wgs84):
    """Load the cached true-colour Sentinel-2 scene, downloading it if absent."""
    if os.path.exists(BASEMAP_TIF):
        da = rioxarray.open_rasterio(BASEMAP_TIF).astype("float64")
        return da.assign_coords(band=["red", "green", "blue"])

    print(f"{BASEMAP_TIF} not found - downloading Sentinel-2 scene ...")
    da = _download_sentinel2(bbox_wgs84)
    da.rio.to_raster(BASEMAP_TIF)
    print(f"cached basemap -> {BASEMAP_TIF}")
    return da


def _download_sentinel2(bbox):
    """Fetch + process a true-colour Sentinel-2 median scene for the bbox.

    Median composite of the cloud-filtered scenes, scaled to reflectance,
    clipped to [0, 1] and histogram-equalised for display contrast.
    """
    import planetary_computer
    import pystac_client
    import stackstac
    from skimage import exposure

    catalog = pystac_client.Client.open(
        "https://planetarycomputer.microsoft.com/api/stac/v1",
        modifier=planetary_computer.sign_inplace,
    )
    items = catalog.search(
        collections=["sentinel-2-l2a"],
        bbox=bbox,
        datetime=f"{S2_YEAR:04d}-{S2_MONTH:02d}-01/{S2_YEAR:04d}-{S2_MONTH:02d}-28",
        query={"eo:cloud_cover": {"lt": S2_MAX_CLOUD}},
    ).item_collection()

    da = stackstac.stack(
        items,
        assets=["B04", "B03", "B02"],  # red, green, blue
        epsg=EPSG,
        bounds_latlon=bbox,
        chunksize=2048,
        resolution=10,
    ).assign_coords(band=["red", "green", "blue"])
    da = da.sel(
        time=(da.time.dt.year.isin([S2_YEAR]) & da.time.dt.month.isin([S2_MONTH]))
    ).compute()

    da = (da.median("time") / S2_NORM_DENOM).clip(0, 1)
    da = xr.apply_ufunc(exposure.equalize_hist, da)
    return da.rio.write_crs(EPSG).rio.set_spatial_dims(x_dim="x", y_dim="y")


# --------------------------------------------------------------------------- #
# FIGURE
# --------------------------------------------------------------------------- #
def make_figure(fronts, basemap):
    cmap = plt.cm.inferno_r.resampled(len(fronts))

    img = basemap.plot.imshow(vmin=0, vmax=1, size=10, aspect=0.9)
    ax = img.axes
    ax.set_aspect("equal")

    fronts.plot(ax=ax, colors=cmap.colors, lw=2.5, alpha=0.7)
    ax.set_title("")
    ax.set_xlabel("x-coordinates [meters]")
    ax.set_ylabel("y-coordinates [meters]")

    fig = img.figure
    fig.set_figheight(6)
    fig.set_figwidth(7)
    fig.set_dpi(DPI)

    fig.savefig(OUT_FIG, bbox_inches="tight", dpi=DPI)
    print(f"wrote {OUT_FIG}")
    return fig, ax


if __name__ == "__main__":
    fronts = load_fronts()
    bbox = fronts.dissolve().to_crs("EPSG:4326").bounds.values.tolist()[0]
    bbox = tuple(b + off for b, off in zip(bbox, BBOX_OFFSET))
    basemap = load_basemap(bbox)
    make_figure(fronts, basemap)
