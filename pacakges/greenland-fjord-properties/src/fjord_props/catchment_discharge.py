from functools import wraps
from typing import Protocol

import geopandas as gpd
import numpy as np
import pandas as pd
import pyflwdir
import xarray as xr
from matplotlib.axes import Axes
from matplotlib.figure import Figure


class FlwdirMethods(Protocol):
    def snap(self, **kwargs) -> xr.DataArray: ...
    def stream_order(self, **kwargs) -> xr.DataArray: ...
    def basins(self, **kwargs) -> xr.DataArray: ...
    def upstream_area(self, **kwargs) -> xr.DataArray: ...
    def subbasins_streamorder(self, **kwargs) -> xr.DataArray: ...


class xrFlwdir(FlwdirMethods):
    """
    A wrapper around pyflwdir to work with xarray DataArrays.
    """

    def __init__(self, dem: xr.DataArray):
        """
        Wraps pyflwdir to handle xarray DataArrays.
        :param da: xarray.DataArray containing flow direction data
        :param ftype: The flow direction type ('d8', 'ldd', etc.)
        """
        self.dem = dem
        self.mask = None
        self.template = dem.drop_attrs()

        # Initialize the pyflwdir core engine with the raw values
        # Note: pyflwdir expects a 2D numpy array
        self.flw = pyflwdir.from_dem(
            data=self.dem.values,
            nodata=self.dem.rio.nodata,
            transform=self.dem.rio.transform(),
            latlon=self.dem.rio.crs.is_geographic,
        )

        # List of pyflwdir methods to wrap from FlwdirMethods
        funcs_to_wrap = [name for name in FlwdirMethods.__dict__.keys() if not name.startswith("_")]

        for func_name in funcs_to_wrap:
            method = getattr(self.flw, func_name)
            wrapped_method = self._wrap_method(method)
            setattr(self, func_name, wrapped_method)

    def _try_wrap_result(self, data, name="result"):
        """Helper to convert a numpy array back into a Geo-referenced DataArray"""
        try:
            return xr.DataArray(
                data=data,
                coords=self.template.coords.drop_vars(["spatial_ref", "mapping"], errors="ignore"),
                dims=self.template.dims,
                name=name,
            ).rio.write_crs(self.dem.rio.crs)
        except Exception:
            return data

    def _wrap_method(self, method):
        @wraps(method)
        def wrapper(*args, **kwargs):
            # We call the pyflwdir method, then wrap the numpy result
            data = method(*args, **kwargs)
            result = self._try_wrap_result(data, name=method.__name__)
            if isinstance(result, tuple):
                return tuple([self._try_wrap_result(r) for r in result])
            return result

        return wrapper

    def basin_upstream(self, xy: tuple[float, float], stream_order_thresh: int | None = None, **kwargs) -> xr.DataArray:
        """
        Get the upstream basin for a given point.
        :param xy: Tuple of (x, y) coordinates
        :return: xarray.DataArray of the upstream basin
        """
        stream_order_thresh = int(stream_order_thresh or self.stream_order().max().item())
        stream_order_mask = self.stream_order() >= stream_order_thresh

        basins = self.basins(xy=xy, streams=stream_order_mask)

        return self._try_wrap_result(basins, name="upstream_basin")

    def downstream(self, xy: tuple[float, float]) -> gpd.GeoSeries:
        """
        Get the downstream point for a given coordinate.
        :param xy: Tuple of (x, y) coordinates
        :return: GeoSeries containing the downstream points
        """
        idx = self.flw.path(xy=xy)[0][0]
        x, y = self.flw.xy(idx)
        points = gpd.GeoSeries.from_xy(x, y)
        return points


def get_fjord_discharge(
    fname_fw_discharge: str,
    catchment: gpd.GeoSeries,
    flw: xrFlwdir,
    polygons: gpd.GeoDataFrame,
    source_name: str | None = None,
) -> tuple[xr.DataArray, gpd.GeoDataFrame]:

    df_discharge = get_catchment_discharge(fname_fw_discharge, catchment)

    ds_discharge, stations = get_discharge_along_fjord(df_discharge, polygons, flw)
    df_discharge = df_discharge.loc[stations]

    if source_name is not None:
        index = df_discharge.index.to_numpy()
        updated_index = tuple(map(lambda x: (source_name,) + x, index))
        names_idx = ["source"] + list(df_discharge.index.names)
        df_discharge.index = pd.MultiIndex.from_tuples(updated_index, names=names_idx)

        name_ds = f"discharge_{source_name}"
        ds_discharge = ds_discharge.rename(name_ds)

    return ds_discharge, df_discharge


def get_discharge_along_fjord(
    df_discharge: pd.DataFrame,
    fjord_polygons: gpd.GeoDataFrame,
    flwdir: xrFlwdir,
) -> tuple[xr.DataArray, np.ndarray]:
    assert fjord_polygons.crs is not None, "Fjord polygons must have a CRS defined"

    crs = fjord_polygons.crs.to_string()
    station_coords = df_discharge.geometry.to_crs(crs).groupby("station").first().get_coordinates()

    for station in station_coords.index:
        xy = station_coords.loc[station]
        dist = get_downstream_polygon_distance(
            station_xy=xy,
            flw=flwdir,
            fjord_polygons=fjord_polygons,
        )
        if dist is None:
            continue
        else:
            df_discharge.loc[station, "distance"] = dist

    df_discharge = df_discharge.dropna(subset=["distance"])
    stations = df_discharge.reset_index().station.unique()

    discharge = (
        df_discharge.groupby(["distance", "month"])
        .discharge.sum()
        .to_xarray()
        .sortby("distance")
        .astype("float32")
        .transpose("month", "distance")
        .assign_attrs(
            units="m^3/s",
            long_name="Freshwater discharge",
            description="Freshwater discharge along the fjord, aggregated from stations within the catchment",
        )
    )

    return discharge, stations


def get_downstream_polygon_distance(
    station_xy: tuple[float, float],
    flw: xrFlwdir,
    fjord_polygons: gpd.GeoDataFrame,
) -> float | None:
    flowline = flw.downstream(station_xy)
    mask = fjord_polygons.union_all()

    intersections = flowline.intersects(mask)
    if not intersections.any():
        return None

    idx_first_intersection = intersections.cumsum().pipe(lambda x: x[x == 1].index[0])
    nearest_point = flowline.iloc[idx_first_intersection]
    polygon_index = int(fjord_polygons.distance(nearest_point).nsmallest(1).index[0])
    polygon_distance = float(fjord_polygons.distance_m.iloc[polygon_index])

    return polygon_distance


def discharge_dataset_to_dataframe(
    ds: xr.Dataset, x_name: str, y_name: str, crs: str = "EPSG:4326", drop_vars=("discharge",)
) -> gpd.GeoDataFrame:
    df = ds.drop_vars(list(drop_vars)).to_dataframe()
    geom = gpd.points_from_xy(df[x_name], df[y_name], crs=crs)
    data = df.drop(columns=[x_name, y_name])
    gdf = gpd.GeoDataFrame(data, geometry=geom).reset_index()
    return gdf


def select_catchment_discharge_stations(ds_discharge: xr.Dataset, catchment: gpd.GeoSeries) -> xr.Dataset:
    crs = "EPSG:4326"

    lat_name = "coast_lat" if "coast_lat" in ds_discharge.coords else "source_lat"
    lon_name = "coast_lon" if "coast_lon" in ds_discharge.coords else "source_lon"

    df = discharge_dataset_to_dataframe(ds_discharge, lon_name, lat_name)
    geom = catchment.to_crs(crs)

    subset = df.clip(geom)
    stations = subset.station.unique()

    ds_subset = ds_discharge.sel(station=stations)

    return ds_subset


def get_catchment_discharge_dataset(fname_fw_discharge: str, catchment: gpd.GeoSeries) -> xr.Dataset:
    ds_discharge_all_stations = xr.open_dataset(fname_fw_discharge)
    ds_discharge_catchment = select_catchment_discharge_stations(ds_discharge_all_stations, catchment)

    if ds_discharge_catchment.station.size == 0:
        raise ValueError("No discharge stations found within the catchment")

    if "coast_lat" in ds_discharge_catchment.coords:
        renames = {"coast_lat": "lat", "coast_lon": "lon"}
    else:
        renames = {"source_lat": "lat", "source_lon": "lon"}

    ds_discharge = (
        ds_discharge_catchment.mean("model")
        .rename(renames)
        .set_coords(["lat", "lon"])
        .drop_vars(["source_lat", "source_lon", "coast_lat", "coast_lon", "coast_id"], errors="ignore")
        .squeeze("source", drop=True)
    )

    assert isinstance(ds_discharge, xr.Dataset), "Merged discharge is not an xarray Dataset"

    return ds_discharge


def get_catchment_discharge(fname_fw_discharge: str, catchment: gpd.GeoSeries) -> gpd.GeoDataFrame:
    ds_discharge = get_catchment_discharge_dataset(fname_fw_discharge, catchment=catchment)

    df_discharge = ds_discharge.to_dataframe()
    geom = gpd.GeoSeries.from_xy(df_discharge.lon, df_discharge.lat, crs="EPSG:4326")
    gdf_discharge = gpd.GeoDataFrame(df_discharge.drop(columns=["lon", "lat"]), geometry=geom)

    return gdf_discharge


def plot_catchment(
    dem_greenland: xr.DataArray,
    catchment: gpd.GeoSeries,
    fjord_geom: gpd.GeoSeries,
    outflow_xy: gpd.GeoSeries,
    crs="EPSG:4326",
) -> tuple[Figure, Axes]:
    from .fjord_aggregator import clip_dataset_to_geom

    dem_crs = dem_greenland.rio.crs.to_epsg()
    dem_bbox = clip_dataset_to_geom(dem_greenland, catchment.buffer(40_000).to_crs(dem_crs), dem_crs, only_bbox=True)

    dem_bbox = dem_bbox.rio.reproject(crs).where(lambda x: x > -9999)
    catchment = catchment.to_crs(crs)
    fjord_geom = fjord_geom.to_crs(crs)
    outflow_xy = outflow_xy.to_crs(crs)

    ax = catchment.boundary.plot(color="k", lw=0.4)
    dem_bbox.plot.imshow(
        ax=ax,
        cmap="terrain",
        robust=True,
        center=False,
        vmin=-250,
        vmax=950,
        alpha=0.5,
        cbar_kwargs={"label": "Elevation (m)"},
    )
    fjord_geom.plot(ax=ax, edgecolor="black", facecolor="none", lw=1)
    outflow_xy.plot(ax=ax, color="red", markersize=50, marker="o", label="Outflow Point", zorder=4)

    ax.set_title("")
    ax.set_title("DEM-calculated catchment Area", loc="left")

    figure: Figure = ax.get_figure()  # type: ignore

    return figure, ax
