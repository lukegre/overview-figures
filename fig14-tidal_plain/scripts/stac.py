import xarray as xr
from loguru import logger
from functools import lru_cache


URL_PLANETARY_COMPUTER = "https://planetarycomputer.microsoft.com/api/stac/v1"


def search_stac_items(collection, bbox, url=URL_PLANETARY_COMPUTER, **kwargs)->list:
    import planetary_computer
    import pystac_client

    catalog = pystac_client.Client.open(
        url=url,
        modifier=planetary_computer.sign_inplace)

    search = catalog.search(
        collections=[collection],
        bbox=bbox, 
        **kwargs)

    items = search.item_collection()

    return items


@lru_cache
def get_elevation(
        bbox: tuple,
        epsg=32623,  # UTM zone 23N
        res=30, 
    )->xr.DataArray:
    """
    Downloads near infrared and red bands for glacier tracking to be used for the NDSInw

    """
    import stackstac

    collection = "cop-dem-glo-30"
    assets = ['data']
    names = ['elevation']

    items = search_stac_items(
        collection=collection,
        bbox=bbox)
    
    da = stackstac.stack(
        items, 
        assets=assets, 
        epsg=epsg, 
        bounds_latlon=bbox,
        chunksize=2048,
        resolution=res).assign_coords(band=names)
    logger.debug(f"Found {len(items)} stack items")
            
    return da.isel(band=0, drop=True).mean('time', keep_attrs=True).compute()


@lru_cache
def get_esri_land_mask(bbox: tuple, res=30, epsg=32623):
    import stackstac
    import pandas as pd

    current_year = pd.Timestamp.now().year
    last_year = current_year - 1
    
    items = search_stac_items(
        collection="io-lulc",
        bbox=bbox)
    assets = ['data']
    names = ['land_use_cover']

    da = stackstac.stack(
        items, 
        assets=assets, 
        epsg=epsg, 
        bounds_latlon=bbox,
        chunksize=2048,
        resolution=res).assign_coords(band=names)
    logger.debug(f"Found {len(items)} stack items")
            
    return da.isel(band=0, drop=True).isel(time=0).compute()


@lru_cache
def get_sentinel2(
        bbox: tuple, 
        datetime: str,
        assets=['B04', 'B03', 'B02', 'B8A', 'B11', 'SCL'],
        max_cloud_cover: int=10,
        epsg: int=32623,  # UTM zone 23N
        res: int=10,  # sentinel-2-l2a resolution
    )->xr.DataArray:
    import stackstac

    collection = "sentinel-2-l2a"

    items = search_stac_items(
            collection=collection,
            bbox=bbox,
            datetime=datetime,
            query={"eo:cloud_cover": {"lt": max_cloud_cover}})
    
    da = stackstac.stack(
        items, 
        assets=assets, 
        epsg=epsg, 
        bounds_latlon=bbox,
        chunksize=2048,
        resolution=res)
    logger.debug(f"Found {len(items)} stack items")

    logger.info(f"Selected {da.time.size} scenes, combining bands {assets} at {res}m resolution")
    da = da.pipe(s2_harmonize_to_old).pipe(s2_rescale).compute()
    
    return da


def s2_harmonize_to_old(data):
    """
    Harmonize new Sentinel-2 data to the old baseline.

    Parameters
    ----------
    data: xarray.DataArray
        A DataArray with four dimensions: time, band, y, x

    Returns
    -------
    harmonized: xarray.DataArray
        A DataArray with all values harmonized to the old
        processing baseline.
    """
    import datetime

    logger.info("Harmonizing data to old baseline (if after 2022)")

    cutoff = datetime.datetime(2022, 1, 25)
    offset = 1000

    bands = [
        "B01", "B02", "B03", "B04",
        "B05", "B06", "B07", "B08", 
        "B8A", "B09", "B10", "B11", "B12"]

    # Select the old data before the cutoff
    old = data.sel(time=slice(cutoff))  # single value in slice = stop

    # select the bands that need to be procesed - union of band list and data bands
    to_process = list(set(bands) & set(data.band.data.tolist()))

    # select the new data after the cutoff for bands that don't need to be processed
    new = data.sel(time=slice(cutoff, None)).drop_sel(band=to_process)

    # select the new data after the cutoff for bands that need to be processed
    new_harmonized = data.sel(time=slice(cutoff, None), band=to_process).clip(offset)
    new_harmonized -= offset

    new = xr.concat([new, new_harmonized], "band").sel(band=data.band.data.tolist())

    harmonized = xr.concat([old, new], dim="time")

    return harmonized


def s2_rescale(data: xr.DataArray, factor=1e-4)->xr.DataArray:
    """
    Rescale the Sentinel-2 data to the original range.

    Args:
        da (xr.DataArray): The Sentinel-2 data.
        factor (float): The factor to multiply the data by.

    Returns:
        xr.DataArray: The rescaled data.
    """
    logger.info("Rescaling data to original range [0, 1]")

    bands = [
        "B01", "B02", "B03", "B04",
        "B05", "B06", "B07", "B08", 
        "B8A", "B09", "B10", "B11", "B12"]
    
    # select the bands that need to be procesed - union of band list and data bands
    to_process = list(set(bands) & set(data.band.data.tolist()))
    
    old_order = data.band.data.tolist()

    new = data.sel(band=to_process) * factor
    old = data.drop_sel(band=to_process)

    rescaled = xr.concat([old, new], "band").sel(band=old_order)

    return rescaled


# Get Landsat scenes
def get_landsat(
        bbox: tuple, 
        datetime: str,
        assets=['red', 'green', 'blue', 'nir08', 'swir16', 'qa_pixel'], 
        max_cloud_cover: int=10,
        epsg: int=32623,  # UTM zone 23N
        res: int=30,  # Landsat resolution
    )->xr.DataArray:
    """
    Downloads Landsat Collection 2 Level 2 surface reflectance data.
    
    Args:
        bbox: Bounding box in lat/lon coordinates (west, south, east, north)
        datetime: Date range in format 'YYYY-MM-DD/YYYY-MM-DD'
        assets: List of bands to download
        max_cloud_cover: Maximum cloud cover percentage allowed
        epsg: Output projection EPSG code
        res: Output resolution in meters
        
    Returns:
        xr.DataArray: Combined Landsat scenes
    """
    import stackstac
    from loguru import logger

    collection = "landsat-c2-l2"

    items = search_stac_items(
            collection=collection,
            bbox=bbox,
            datetime=datetime,
            query={"eo:cloud_cover": {"lt": max_cloud_cover}})
    
    da = stackstac.stack(
        items, 
        assets=assets, 
        epsg=epsg, 
        bounds_latlon=bbox,
        chunksize=2048,
        resolution=res)
    logger.debug(f"Found {len(items)} stack items")

    logger.info(f"Selected {da.time.size} scenes, combining bands {assets} at {res}m resolution")
    
    return da