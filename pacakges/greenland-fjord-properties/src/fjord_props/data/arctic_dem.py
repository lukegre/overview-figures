import numpy as np
import pystac_client
import stackstac
from loguru import logger

URL_CATALOG = "https://stac.pgc.umn.edu/api/v1/"
VALID_COLLECTIONS = (
    "arcticdem-mosaics-v4.1-32m",
    "arcticdem-mosaics-v4.1-10m",
    "arcticdem-mosaics-v4.1-2m",
)


def get_arctic_dem(
    bbox_latlon: tuple[float, float, float, float],
    resolution: int = 50,
    assets: tuple[str] = ("dem",),
    epsg: int = 3413,
):
    possible_resolutions = np.array((2, 10, 32))
    appropriate_res = resolution > possible_resolutions
    if np.any(appropriate_res):
        res_m = possible_resolutions[appropriate_res].max()
    else:
        res_m = possible_resolutions.min()

    collection = f"arcticdem-mosaics-v4.1-{res_m}m"

    logger.info(f"Using ArcticDEM collection: {collection} for requested resolution: {resolution} m")

    items = get_items(bbox_latlon, collection)
    arctic_dem_stack = (
        items_to_xarray(items=items, bbox_latlon=bbox_latlon, assets=assets, resolution=resolution)
        .isel(band=0)
        .mean(dim="time")
    )

    if epsg != 3413:
        arctic_dem_stack = arctic_dem_stack.rio.reproject(f"EPSG:{epsg}")

    return arctic_dem_stack


def get_client():
    client = pystac_client.Client.open(URL_CATALOG)
    return client


def get_items(bbox_latlon: tuple[float, float, float, float], collection: str = "arcticdem-mosaics-v4.1-10m"):
    assert collection in VALID_COLLECTIONS, f"Collection {collection} is not valid. Choose from {VALID_COLLECTIONS}."

    client = get_client()
    results = client.search(
        collections=[collection],
        bbox=bbox_latlon,
    )
    items = results.item_collection()
    return items


def items_to_xarray(items, bbox_latlon: tuple[float, float, float, float], assets=("dem",), resolution: int = 50):
    epsg = 3413  # ArcticDEM native projection

    arctic_dem_stack = stackstac.stack(
        items,
        assets=list(assets),
        epsg=epsg,
        bounds_latlon=bbox_latlon,
        resolution=resolution,
    )

    arctic_dem_stack = arctic_dem_stack.rio.write_crs(f"EPSG:{epsg}")

    return arctic_dem_stack
