import numpy as np
import xarray as xr
from pyresample import kd_tree
from pyresample.geometry import AreaDefinition, SwathDefinition, create_area_def


def regrid_swath(
    satellite_data: xr.Dataset,
    target_area: AreaDefinition | None = None,
    target_grid: xr.Dataset | None = None,
    lat_var_name="latitude",
    lon_var_name="longitude",
    n_jobs=-1,
    **kwargs,
) -> xr.Dataset:
    """
    Regrids a swath dataset to a target grid or area using pyresample's kd_tree method.

    Parameters
    ----------
    satellite_data: xr.Dataset
        a merge of the geophysical_data and navigation_data groups from a satellite
        granule, or any similar swath dataset with lat/lon coordinates
    target_area: AreaDefinition, optional
        a pyresample AreaDefinition defining the target grid.
        If not provided, `target_grid` must be supplied.
    target_grid: xr.Dataset, optional
        an xarray Dataset with 2D lat/lon coordinates defining the target grid.
        If not provided, `target_area` must be supplied.
    lat_var_name: str, default "latitude"
        name of the latitude variable in `satellite_data`
    lon_var_name: str, default "longitude"
        name of the longitude variable in `satellite_data`
    n_jobs: int, default -1
        number of parallel jobs to run for regridding (variables run in parallel).
        Uses joblib threading for parallelization, with -1 = all available cores.
    **kwargs:
        additional keyword arguments to pass to pyresample's kd_tree.resample_nearest function.
        defaults are:
            radius_of_influence = 2000,  in meters
            fill_value = np.nan,
            epsilon = 50,  # resample_nearest precision threshold in meters
            nprocs = 1,  # number of processes for kd_tree keep to one to avoid chaotic behavior
    """

    if (target_area is None) and (target_grid is None):
        raise ValueError("You must supply either `target_area` or `target_grid`")
    elif isinstance(target_area, AreaDefinition) and (target_grid is None):
        pass
    elif isinstance(target_grid, xr.Dataset) and (target_area is None):
        target_area = create_area_from_dataset(target_grid)
    else:
        raise ValueError("You can only provide `target_area[AreaDefinition]` or `target_grid[xr.Dataset]`")

    swath = define_swath(satellite_data, lat_var_name, lon_var_name)

    data = satellite_data.drop_vars([lat_var_name, lon_var_name])

    resampled_ds = remap_dataset(data, swath, target_area, **kwargs)

    # func = joblib.delayed(remap_single_var)
    # tasks = [func(data[var], swath, target_area, **kwargs) for var in data.data_vars]
    # output = joblib.Parallel(n_jobs=n_jobs, backend="threading")(tasks)

    # resampled_ds = xr.merge(output)
    # resampled_ds.attrs = {"source_file": satellite_data.attrs.get("source", "NA")}
    # resampled_ds = resampled_ds.rio.write_crs(target_area.crs)

    return resampled_ds


def remap_dataset(data: xr.Dataset, swath_def: SwathDefinition, target_area: AreaDefinition, **kwargs) -> xr.Dataset:
    """
    Converts dataset to a datarray with multiple "bands" and remaps using pyresample's kd_tree method.
    """

    default_kwargs = {
        "radius_of_influence": 2000,  # in meters
        "fill_value": np.nan,
        "epsilon": 50,
        "nprocs": 6,
    }
    default_kwargs.update(kwargs)

    int_dtypes = [k for k, v in data.dtypes.items() if np.issubdtype(v, np.integer)]

    dims = list(data.dims)
    data_3d = data.to_array().transpose(*dims, "variable")
    variables = data_3d.coords["variable"].values
    arr = data_3d.values.astype(np.float64, casting="safe")

    resampled_3d = kd_tree.resample_nearest(
        swath_def,
        arr,
        target_area,
        **default_kwargs,
    )

    x_1d = target_area.projection_x_coords
    y_1d = target_area.projection_y_coords

    regrid_attrs = {
        "regrid_method": "kd_tree.resample_nearest",
        "regrid_radius_m": default_kwargs["radius_of_influence"],
        "regrid_threshold": default_kwargs["epsilon"],
        "regrid_resolution_m": target_area.resolution,
        "regrid_crs": target_area.crs.to_string(),
    }

    resampled_da = xr.DataArray(
        resampled_3d,
        dims=["y", "x", "variable"],
        coords={"variable": variables, "y": y_1d, "x": x_1d},
        attrs=data.attrs | regrid_attrs,
    )

    resampled_ds = resampled_da.to_dataset(dim="variable")

    for k in int_dtypes:
        resampled_ds[k] = resampled_ds[k].fillna(0).astype(np.int32)

    return resampled_ds


def remap_single_var(
    data: xr.DataArray, swath_def: SwathDefinition, target_area: AreaDefinition, **kwargs
) -> xr.DataArray:

    default_kwargs = {
        "radius_of_influence": 2000,  # in meters
        "fill_value": np.nan,
        "epsilon": 50,
        "nprocs": 1,
    }
    default_kwargs.update(kwargs)

    input_dtype = data.dtype

    data_2d = data.values.astype(np.float64)
    resampled_2d = kd_tree.resample_nearest(
        swath_def,
        data_2d,
        target_area,
        **default_kwargs,
    )
    if np.issubdtype(input_dtype, np.integer):
        missing = np.isnan(resampled_2d)
        resampled_2d[missing] = 0
        resampled_2d = resampled_2d.astype(input_dtype)

    x_1d = target_area.projection_x_coords
    y_1d = target_area.projection_y_coords

    regrid_attrs = {
        "regrid_method": "kd_tree.resample_nearest",
        "regrid_radius_m": default_kwargs["radius_of_influence"],
        "regrid_threshold": default_kwargs["epsilon"],
        "regrid_resolution_m": target_area.resolution,
        "regrid_crs": target_area.crs.to_string(),
    }

    resampled_da = xr.DataArray(
        resampled_2d,
        dims=["y", "x"],
        coords={"y": y_1d, "x": x_1d},
        name=data.name,
        attrs=data.attrs | regrid_attrs,
    )

    return resampled_da


def define_swath(
    satellite_data: xr.Dataset,
    lat_var_name="latitude",
    lon_var_name="longitude",
) -> SwathDefinition:

    lat2d = satellite_data[lat_var_name].values.astype(np.float64)
    lon2d = satellite_data[lon_var_name].values.astype(np.float64)
    swath_def = SwathDefinition(lons=lon2d, lats=lat2d)

    return swath_def


def create_area_from_bbox(
    bbox: tuple[float, float, float, float], projection: str, resolution: float
) -> AreaDefinition:

    width = int((bbox[2] - bbox[0]) // resolution + 1)
    height = int((bbox[3] - bbox[1]) // resolution + 1)

    area_def = create_area_def(
        area_id="my_area",
        projection=projection,
        shape=(height, width),
        area_extent=bbox,
    )

    return area_def


def create_area_from_dataset(dataset: xr.Dataset) -> AreaDefinition:

    assert dataset.rio.crs is not None, "Dataset must have a CRS (via rioxarray)"

    bbox = dataset.rio.bounds()
    proj = dataset.rio.crs.to_string()
    res_m = dataset.rio.resolution()[0]

    return create_area_from_bbox(bbox, proj, res_m)

    ...


def create_dataset_from_area(area_def: AreaDefinition) -> xr.Dataset:
    # Create an empty dataset with the target area's dimensions

    x_1d = area_def.projection_x_coords
    y_1d = area_def.projection_y_coords

    dataset = xr.Dataset(coords={"y": y_1d, "x": x_1d})
    dataset = dataset.rio.write_crs(area_def.crs)

    return dataset


def polygon_to_raster_mask(polygon, da_target):
    """
    Convert a Shapely polygon to a binary mask that matches the grid of an xarray.DataArray.

    Parameters
    ----------
    polygon : shapely.geometry.Polygon or geopandas.GeoDataFrame
        The polygon to convert to a raster mask.
    da_target : xr.DataArray
        The target grid to match the mask to (spatial dimensions must be 'x' and 'y').

    Returns
    -------
    mask_da : xr.DataArray
        A boolean DataArray with the mask on the target grid.
    """
    import geopandas as gpd
    import rasterio
    from rasterio.features import rasterize
    from shapely.geometry import mapping

    if isinstance(polygon, (gpd.GeoSeries, gpd.GeoDataFrame)):
        polygon = polygon.union_all()

    # Get the spatial dimensions of the data array
    if "x" in da_target.dims and "y" in da_target.dims:
        x, y = "x", "y"
    else:
        raise ValueError("Data array must have 'x' and 'y' dimensions")

    # make sure lat is descending, otherwise upside down coords
    da_target = da_target.sortby("y", ascending=False)

    # Define the transformation from pixel coordinates to geographical coordinates
    transform = rasterio.transform.from_bounds(
        min(da_target[x].values),
        min(da_target[y].values),
        max(da_target[x].values),
        max(da_target[y].values),
        len(da_target[x]),
        len(da_target[y]),
    )

    # Rasterize the polygon
    mask = rasterize(
        [mapping(polygon)],
        out_shape=(len(da_target[y]), len(da_target[x])),
        transform=transform,
        fill=0,
        out=None,
        all_touched=True,
        dtype=np.uint8,
    )

    # Create a DataArray from the mask
    mask_da = (
        xr.DataArray(mask, dims=(y, x), coords={y: da_target[y], x: da_target[x]}).interp_like(da_target).astype(bool)
    )

    return mask_da
