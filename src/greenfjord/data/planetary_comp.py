def get_catalog():
    import planetary_computer
    import pystac_client
    
    catalog = pystac_client.Client.open(
        "https://planetarycomputer.microsoft.com/api/stac/v1",
        modifier=planetary_computer.sign_inplace)
    
    return catalog


def get_items(collection, catalog=None, **query):
    from loguru import logger

    if catalog is None:
        catalog = get_catalog()
        
    search = catalog.search(collections=[collection], **query)
    items = list(search.items())

    logger.info(f"Returned {len(items)} items")

    return items


def get_pc_data(collection, bbox, start_date, end_date, max_cloud_cover=None, epsg=32623, res=30, bands=None):
    import stackstac
    
    if max_cloud_cover is not None:
        query = {"eo:cloud_cover": {"lt": max_cloud_cover}}
    else:
        query = {}
    items = get_items(
        collection=collection,
        bbox=bbox,
        datetime=f"{start_date}/{end_date}",
        query=query,
    )
    
    da = stackstac.stack(
        items, 
        assets=bands, 
        epsg=epsg, 
        bounds_latlon=bbox,
        chunksize=2048,
        resolution=res)
    
    da = da.rio.write_crs(f"epsg:{epsg}")
    
    return da