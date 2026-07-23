"""
SST data does not have to be stored on S3 bucket since it's quick to fetch for the entire
period and region. So, we download using the copernicusmarine api and then store locally.
"""

from functools import lru_cache as _lru_cache

import rioxarray  # noqa: F401

from ..config import BBOX_OCEAN as BBOX
from ..config import TIME_END, TIME_START


def get_sst_ice_dmi(fname=None, **query_kwargs):

    if fname is None:
        props = dict(
            dataset_id="cmems_obs_si_arc_phy_my_L4-DMIOI_P1D-m",
            variables=["analysed_st", "sea_ice_fraction"],
            output_dir="../data/sst_CMEMS/",
        )

        props.update(query_kwargs)
        ds = get_copernicusmarine(**props)
    else:
        import xarray as xr

        ds = xr.open_zarr(fname)

    ds = ds.rename(latitude="y", longitude="x").rio.write_crs(4326)

    return ds


def prep_data(ds):
    return ds.rename(latitude="y", longitude="x").rio.write_crs(4326)


##################################################################
### STATIC FUNCTIONS FOR ACCESSING DATA FROM COPERNICUS-MARINE ###
##################################################################


def get_copurnicasmarine_zarr(dataset_id, variables, output_dir=None, **query_kwargs):
    import pathlib

    import pandas as pd
    import xarray as xr
    from copernicusmarine.download_functions.utils import _build_filename_from_dataset
    from loguru import logger

    from .copernicusmarine import get_dataset_info

    t0 = pd.Timestamp(TIME_START) - pd.DateOffset(months=1)
    t1 = pd.Timestamp(TIME_END) + pd.DateOffset(months=2)
    W, S, E, N = BBOX

    product_id, dataset_id, zarr_url = get_dataset_info(dataset_id, service_name="arco-time-series")
    ds = xr.open_zarr(zarr_url, storage_options=dict())
    ds = ds[variables].sel(time=slice(t0, t1), latitude=slice(S, N), longitude=slice(W, E))

    fname = _build_filename_from_dataset(ds, dataset_id, "netcdf")
    ds.attrs["fname"] = fname

    if output_dir is not None:
        path = pathlib.Path(f"{output_dir}/{fname}")
        if not path.exists():
            logger.info(f"DOWNLOADING to {path}")
            ds = ds.compute()
            ds.to_netcdf(path)
        else:
            logger.info("File already exists, using local version")
            ds = xr.open_dataset(path)

    return ds


def get_copernicusmarine(dataset_id, variables, output_dir=None, **query_kwargs):
    from pathlib import Path

    import pandas as pd
    import xarray as xr
    from loguru import logger

    t0 = pd.Timestamp(TIME_START) - pd.DateOffset(months=1)
    t1 = pd.Timestamp(TIME_END) + pd.DateOffset(months=2)

    props = dict(
        dataset_id=dataset_id,
        variables=tuple(variables),
        minimum_longitude=BBOX[0],
        maximum_longitude=BBOX[2],
        minimum_latitude=BBOX[1],
        maximum_latitude=BBOX[3],
        start_datetime=t0.strftime("%Y-%m-%d"),
        end_datetime=t1.strftime("%Y-%m-%d"),
        service="arco-time-series",
    )
    props.update(query_kwargs)

    ds = _cached_dataset_opener(**props)
    ds = ds.chunk(dict(time=365, latitude=100, longitude=100))
    ds.attrs["dataset_id"] = dataset_id

    fname = _build_filename_from_dataset(ds, ds.dataset_id, "zarr")
    ds.attrs["fname"] = fname

    if output_dir is not None:
        path = Path(f"{output_dir}/{fname}")
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            logger.info(f"DOWNLOADING to {path}")
            try:
                ds = ds.resample(time="1MS").mean().load()
                ds.to_zarr(path, safe_chunks=True)
            except:
                logger.warning("Failed to write to zarr, returning xr.Dataset")
                pass
        else:
            logger.info("File already exists, using local version")
            ds = xr.open_zarr(path)

    return ds


def _build_filename_from_dataset(ds, dataset_id, file_format):
    import pandas as pd

    def format_coord(coord, axis="lat"):
        if axis == "lat":
            return f"{abs(coord):.0f}{'N' if coord >= 0 else 'S'}"
        else:
            return f"{abs(coord):.0f}{'E' if coord >= 0 else 'W'}"

    lat0 = format_coord(ds.latitude.min().item(), axis="lat")
    lat1 = format_coord(ds.latitude.max().item(), axis="lat")
    lon0 = format_coord(ds.longitude.min().item(), axis="lon")
    lon1 = format_coord(ds.longitude.max().item(), axis="lon")

    t0 = pd.Timestamp(ds.time.min().item()).strftime("%Y%m%d")
    t1 = pd.Timestamp(ds.time.max().item()).strftime("%Y%m%d")

    fname = f"{dataset_id}_{t0}-{t1}_{lat0}_{lat1}_{lon0}_{lon1}.{file_format}"
    return fname


@_lru_cache
def _cached_dataset_opener(**query_kwargs):
    import copernicusmarine

    query_kwargs["variables"] = list(query_kwargs["variables"])  # convert to list for caching
    return copernicusmarine.open_dataset(**query_kwargs)
