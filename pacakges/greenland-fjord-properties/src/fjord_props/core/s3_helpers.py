from typing import Any

import fsspec
import geopandas as gpd


def read_generic(path: str, opener, **kwargs) -> Any:
    assert isinstance(path, str), "`path` must be a string"

    fname = fsspec.open_local(path)
    assert isinstance(fname, str), "expected a single local file path, but got something else"

    out = opener(fname, **kwargs)
    return out


def read_s3_gpkg(path_gpkg: str, **kwargs) -> gpd.GeoDataFrame:
    """Open a GeoPackage file from local or remote storage."""
    return read_generic(path_gpkg, gpd.read_file, **kwargs)


def read_s3_tif(path_tif: str, **kwargs) -> gpd.GeoDataFrame:
    import rioxarray

    return read_generic(path_tif, rioxarray.open_rasterio, **kwargs)
