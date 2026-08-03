from functools import lru_cache

import geopandas as gpd
import numpy as np
import pandas as pd
import rioxarray as rxr
import xarray as xr
from loguru import logger
from munch import Munch


def load_greenland_data(cat: dict) -> Munch:
    """
    Load various Greenland datasets based on the provided catalog.

    :param cat: A dictionary containing file paths for different datasets.
    :return: A Munch object containing loaded datasets.
    """
    cat_frozen = frozenset(cat.items())
    return _load_greenland_data_cached(cat_frozen)


@lru_cache
def _load_greenland_data_cached(cat_frozen: frozenset) -> Munch:
    cat = dict(cat_frozen)

    data = Munch(
        dem=load_bedmachine_dem(cat["bedmachine_tif"]).rename("bath"),
        chl_count=load_arctic_ocean_color(cat["chla_arctic_zarr"]).chl_count,
        tur_count=load_arctic_ocean_color(cat["turbidity_arctic_zarr"]).tur_count,
        chl=load_arctic_ocean_color(cat["chla_arctic_zarr"]).chl,
        tur=load_arctic_ocean_color(cat["turbidity_arctic_zarr"]).tur,
        spm=load_arctic_ocean_color(cat["turbidity_arctic_zarr"]).spm,
        pace_chl=load_pace_oci(cat["chla_pace_zarr"]).chlor_a,
        pace_chl_count=load_pace_oci(cat["chla_pace_zarr"]).chlor_a_count,
        pace_poc=load_pace_oci(cat["chla_pace_zarr"]).poc,
        pace_carbon_phyto=load_pace_oci(cat["chla_pace_zarr"]).carbon_phyto,
        pace_par_count=load_pace_oci(cat["par_pace_zarr"]).par_day_planar_above_count,
        pace_par_planabv=load_pace_oci(cat["par_pace_zarr"]).par_day_planar_above,
        pace_par_planblw=load_pace_oci(cat["par_pace_zarr"]).par_day_planar_below,
        pace_par_scalblw=load_pace_oci(cat["par_pace_zarr"]).par_day_scalar_below,
        ice=load_seaice_monthly(cat["seaice_dmi_monthly_zarr"]).ice,
        fish=load_fishing_effort(cat["fishing_effort_zarr"]).fish,
        glaciers=load_glacier_fronts(cat["marine_glacier_fronts_shp"]),
    )

    logger.success("Finished loading datasets.")

    for key in data:
        if isinstance(data[key], xr.DataArray):
            assert hasattr(data[key], "name"), f"Dataset {key} does not have a 'name' attribute."
    return data


def camelcase_to_underscore(s: str) -> str:
    """transforms CamelCase to camel_case"""
    import re

    return "_".join(re.sub("([a-z0-9])([A-Z])", r"\1_\2", s).lower().split())


def load_fjord_names(fname: str) -> gpd.GeoDataFrame:
    logger.debug(f"Loading fjord names from {fname}")

    df = gpd.read_file(fname)
    df = df.filter(regex="PlacenameOfficial|PlacenameDanish|EditDate|geometry")
    df = df.rename(columns=camelcase_to_underscore)
    latlon = df.geometry.to_crs("EPSG:4326").centroid
    df["lat"] = latlon.y
    df["lon"] = latlon.x
    df["area_m2"] = df.area
    df["edit_date"] = pd.to_datetime(df.edit_date, unit="ms")

    return df


def load_glacier_fronts(fname: str) -> gpd.GeoDataFrame:
    logger.debug(f"Loading glacier fronts from {fname}")
    return gpd.read_file(fname)


def load_fishing_effort(fname: str) -> xr.Dataset:
    logger.debug(f"Loading fishing effort data from {fname}")
    ds = xr.open_zarr(fname, chunks="auto")
    crs = ds.spatial_ref.crs_wkt
    ds = ds.rio.write_crs(crs).rio.reproject(crs)
    ds = ds.rename(time="year", fishing_effort_hours_per_km2="fish")
    ds.fish.attrs["long_name"] = "Fishing effort"
    ds.fish.attrs["units"] = "hours per km^2"
    ds = ds.chunk("auto").persist()
    return ds


@lru_cache(maxsize=4)
def load_pace_oci(fname: str) -> xr.Dataset:
    """Load PACE OCI L2 zarr (EPSG:3413, x/y coords in metres)."""
    logger.debug(f"Loading PACE OCI data from {fname}")
    ds = xr.open_zarr(fname, chunks="auto")
    time = ds.time.values.astype("datetime64[M]").astype("datetime64[ns]")
    ds = ds.assign_coords(time=time)
    ds = ds.rio.write_crs("EPSG:3413")
    return ds


@lru_cache(maxsize=4)
def load_arctic_ocean_color(fname: str) -> xr.Dataset:
    logger.debug(f"Loading Arctic Ocean Color data from {fname}")
    ds = xr.open_zarr(fname, chunks="auto")
    ds = ds.rio.write_crs("EPSG:6931")
    ds = ds.rename({k: k.lower() for k in ds.data_vars})
    return ds


def load_seaice_monthly(fname: str) -> xr.Dataset:
    logger.debug(f"Loading Sea Ice data from {fname}")
    ds = xr.open_zarr(fname).pipe(lambda ds: ds.rio.write_crs(ds.spatial_ref.crs_wkt))
    ds = ds.rename(sic="ice", sod="sod")
    ds.ice.attrs["long_name"] = "Sea ice concentration"
    ds.ice.attrs["units"] = "percent"
    ds.sod.attrs["long_name"] = "State of development"
    ds.sod.attrs["units"] = "category"
    return ds


def load_bedmachine_dem(fname: str) -> xr.DataArray:
    logger.debug(f"Loading Bedmachine DEM from {fname}")
    ds = rxr.open_rasterio(fname, chunks={})
    assert isinstance(ds, xr.DataArray)
    ds = (
        ds.isel(band=0, drop=True)
        .rename("bath")
        .rename(mapping="spatial_ref")
        .rio.set_spatial_dims(x_dim="x", y_dim="y")
        .rio.write_crs(ds.rio.crs, grid_mapping_name="spatial_ref")
        .astype("float32")
        .rio.set_nodata(np.nan)
    )
    ds.attrs["long_name"] = "Bedmachine DEM"
    ds.attrs["units"] = "meters"

    return ds
