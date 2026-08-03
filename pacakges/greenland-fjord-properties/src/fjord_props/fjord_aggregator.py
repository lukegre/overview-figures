import pathlib
from dataclasses import dataclass, field
from typing import Callable, Literal, Self

import geopandas as gpd
import numpy as np
import pandas as pd
import raster_vector  # noqa: F401
import rioxarray  # noqa: F401
import xarray as xr
from folium import Map
from loguru import logger
from matplotlib.axes import Axes
from matplotlib.figure import Figure
from pyproj import CRS
from shapely.geometry import (
    LineString,
    MultiLineString,
    MultiPoint,
    MultiPolygon,
    Point,
    Polygon,
)

from .catchment_discharge import xrFlwdir


class DummyContextManager:
    """A no-op context manager for when progress bars are not needed."""

    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self, *args, **kwargs):
        pass

    def __exit__(self, exc_type, exc_value, traceback):
        pass


@dataclass
class FjordAggregator:
    """
    A class to aggregate data within a fjord polygon using defined polygons along the fjord centerline.

    :param fjord: The rough fjord polygon geometry - later refined more precisely
    :param land: The land polygon geometry surrounding the fjord
    """

    fjord: Polygon
    land: Polygon | MultiPolygon
    centerline: LineString | MultiLineString
    polygons: gpd.GeoDataFrame
    ocean_marker: Point
    epsg: int
    crs: CRS
    bounds_latlon: tuple[float, float, float, float]
    interp_distance_m: float = 10_000
    props: dict = field(default_factory=dict)
    cache: dict = field(default_factory=dict, repr=False, compare=False)
    repr_plot_type: Literal["html", "static"] = "html"

    @classmethod
    def from_fjord_geom(
        cls,
        fjord: gpd.GeoDataFrame | gpd.GeoSeries,
        greenland_land_mask: gpd.GeoDataFrame,
        interp_distance_m: float = 10_000,
        fjord_inner_buffer_m: float = 250,
    ) -> Self:
        """
        Instantiates a FjordAggregator from a fjord geometry and land mask

        :param fjord: A rough fjord polygon geometry. The fjord EPGS determines the CRS for all processing
        :type fjord: gpd.GeoDataFrame
        :param greenland_land_mask: A high resolution land mask.
        :type greenland_land_mask: gpd.GeoDataFrame
        :param simplify_tolerance_m: How much to simplify the centerline (in meters) for polygon generation
        :type simplify_tolerance_m: float
        :param fjord_inner_buffer_m: How much to pad the fjord polygon inward (in meters)
        :type fjord_inner_buffer_m: float
        :return: A FjordAggregator instance.
        :rtype: FjordAggregator
        """
        from shapely.validation import make_valid

        assert fjord.crs is not None, "Fjord must have a CRS defined"
        assert greenland_land_mask.crs is not None, "Land mask must have a CRS defined"

        fjord_number = fjord.index[0] if hasattr(fjord, "index") else "unknown"
        _set_logger_details(fjord_number)

        crs_utm = fjord.estimate_utm_crs()

        epsg = {
            "fjord": fjord.crs.to_epsg(),
            "land": greenland_land_mask.crs.to_epsg(),
            "utm": crs_utm.to_epsg(),
        }

        # don't do in loop, since typing doesn't work - so keep explicit
        assert isinstance(epsg["land"], int), "Land mask CRS must have a valid EPSG code"
        assert isinstance(epsg["fjord"], int), "Fjord CRS must have a valid EPSG code"
        assert isinstance(epsg["utm"], int), "Fjord CRS must have a valid UTM EPSG code"

        # 1) convert fjord to utm
        fjord_utm = fjord.to_crs(epsg=epsg["utm"])
        # 2) buffer,  3) convert to land mask crs
        roi_land_epsg = fjord_utm.envelope.buffer(100_000, join_style="mitre").to_crs(epsg=epsg["land"])
        # 4) clip land mask,  5) convert land to utm
        land_mask_utm = greenland_land_mask.clip(roi_land_epsg).to_crs(epsg=epsg["utm"])

        if not land_mask_utm.is_valid.all():
            logger.debug("Land geometry is invalid, attempting to fix with make_valid")
            land_mask_utm = land_mask_utm.geometry.map(make_valid)

        land_geom = land_mask_utm.union_all().simplify(tolerance=50, preserve_topology=True)
        fjord_geom = fjord_utm.buffer(0).union_all()  # buffer to fix potential geometry issues
        assert isinstance(fjord_geom, Polygon), "Fjord geometry must be a Polygon"
        assert isinstance(land_geom, (Polygon, MultiPolygon)), "Land geometry must be a [Multi]Polygon"

        fjord_padded = fjord_geom.buffer(fjord_inner_buffer_m).difference(land_geom).buffer(-fjord_inner_buffer_m)
        fjord_expanded = fjord_geom.buffer(fjord_inner_buffer_m * 2, join_style="mitre").difference(land_geom).buffer(0)

        # at most, will be three lines - main centerline and two branches
        centerline = get_fjord_centerline(fjord_geom)

        # estimate the length from the centerline - does not account for branch duplication
        fjord_avg_width = fjord_padded.area / centerline.length
        # create a concave hull mask, so that we can find the ocean marker (otherwise islands may interfere)
        land_concave_hull = get_concave_hull_with_buffer(land_geom, buffer_distance_m=fjord_avg_width * 4)
        # ocean marker is where centerline is nearest to the land concave hull
        ocean_marker = get_nearest_point(centerline, land_concave_hull)
        # joins the longest two branches if multiple centerlines are present
        centerline = process_multiline(centerline, ref_point=ocean_marker)

        # compute polygons and their distance from the ocean marker
        polygons = get_fjord_length_polygons(centerline, fjord_expanded, interp_distance_m).set_crs(epsg=epsg["utm"])
        # now we update the length based on the polygon calculation
        polygons["width_est_m"] = get_polygon_widths(polygons.geometry)
        fjord_length_updated = round(gpd.GeoSeries(centerline).explode().length.nlargest(2).sum(), 2)
        fjord_area_updated = fjord_expanded.area
        fjord_width_updated = round(fjord_area_updated / fjord_length_updated)

        out = cls(
            fjord=fjord_geom,
            centerline=centerline,
            polygons=polygons.clip(fjord_padded).sort_values("distance_m"),
            land=land_geom,
            ocean_marker=ocean_marker,
            epsg=epsg["utm"],
            crs=crs_utm,
            bounds_latlon=get_bounds(fjord.to_crs(epsg=4326)),
            interp_distance_m=interp_distance_m,
            props={
                "id": fjord_number,
                "fjord_num": f"#{fjord_number}",
                "length_km": fjord_length_updated / 1e3,
                "area_km2": fjord_area_updated / 1e6,
                "width_m": fjord_width_updated,
                "num_polygons": len(polygons),
                "num_branches": len(centerline.geoms) if isinstance(centerline, MultiLineString) else 1,
            },
            cache={"fjord_padded": fjord_padded},
        )

        return out

    @classmethod
    def from_pickle(cls, path: str | pathlib.Path, with_cache: bool = True) -> Self:
        import joblib

        from .catchment_discharge import xrFlwdir  # noqa: F401

        path = str(path)

        obj = joblib.load(path)
        logger.info(f"Loaded FjordAggregator from {path}")
        if not isinstance(obj, cls):
            raise ValueError(f"Loaded object is not a {cls.__name__} instance")

        dem = obj.cache.get("flwdir_dem")
        if isinstance(dem, xr.DataArray) and with_cache:
            logger.debug("Reconstructing flow direction raster from stored DEM.")
            obj.cache["flwdir_raster"] = xrFlwdir(dem)  # type: ignore

        return obj

    def get_fjord_mask(self, target_grid: xr.DataArray) -> xr.DataArray:
        """
        Generates a fjord polygon mask on the target grid in its CRS.

        :param target_grid: A DataArray representing the target grid with [y, x] dimensions.
        :type target_grid: xr.DataArray (with CRS)
        :return: A DataArray mask with fjord polygon indices.
        :rtype: DataArray (float)
        """
        da = get_fjord_polygon_mask(
            fjord_polygons=self.polygons,
            target_grid=target_grid,
        )

        da = da.sortby(["y", "x"])

        da = da.assign_attrs(
            description=(
                "Fjord polygon index mask used for aggregation. "
                "Values correspond to the index of the fjord polygon indices."
            )
        )

        return da

    def _get_dem_for_flwdir(self, greenland_dem: xr.DataArray, buffer_dist=40_000) -> xr.DataArray:
        bath_bbox = clip_dataset_to_geom(
            greenland_dem,
            self.land.envelope.buffer(buffer_dist, join_style="mitre"),
            self.epsg,
        )

        # from here on, bath_bbox is in fjord CRS
        bath_bbox = bath_bbox.rio.reproject(f"EPSG:{self.epsg}")

        land_geom: MultiPolygon | Polygon = (
            bath_bbox.pipe(lambda x: x > 0)  # only land and not water
            .rio.write_crs(bath_bbox.rio.crs)  # reset CRS after boolean operation
            .rv.to_polygons()  # convert to gpd.GeoSeries[MultiPolygon]
            .union_all()  # get the geometry
        )

        w = self.props["width_m"] * 2  # smaller buffer + larger area for closer fit, removes spurious catchments
        coastal_mask = get_concave_hull_with_buffer(land_geom, buffer_distance_m=w, area_threshold_m2=1e7)
        bath_bbox = bath_bbox.rio.clip([coastal_mask])
        return bath_bbox

    def _get_fjord_flwdir(self, greenland_dem: xr.DataArray, buffer_dist=40_000) -> tuple[xrFlwdir, xr.DataArray]:
        bath_bbox = self._get_dem_for_flwdir(greenland_dem, buffer_dist=buffer_dist)
        flw = xrFlwdir(bath_bbox)  # type: ignore
        return flw, bath_bbox

    def get_fjord_catchment(
        self, greenland_bathymetry: xr.DataArray, buffer_dist=40_000, fjord_outlet_offset_frac=0.25
    ) -> tuple[gpd.GeoSeries, xrFlwdir]:
        """
        Get the upstream catchment area for the fjord based on bathymetry and flow direction.

        :param greenland_bathymetry: A DataArray of Greenland bathymetry (prefarrably Bed-Machine)
        :param buffer_dist: Distance to buffer the land mask for clipping bathymetry
        :param fjord_outlet_offset_frac: Fractional offset to avoid edge cases for fjord outlet point
        :return: A GeoSeries of the upstream catchment polygon and the flow direction object
        :rtype: tuple[gpd.GeoSeries, xrFlwdir]
        """

        flw_cached = self.cache.get("flwdir_raster")
        upstream_basin_vector_cached = self.cache.get("upstream_basin_vector")
        last_outlet_offset_frac = self.cache.get("catchment_outlet_offset_frac")
        buffer_dist_cached = self.cache.get("catchment_buffer_dist")

        if (
            flw_cached is not None
            and upstream_basin_vector_cached is not None
            and last_outlet_offset_frac == fjord_outlet_offset_frac
            and buffer_dist_cached == buffer_dist
        ):
            logger.debug("Using cached flow direction and upstream basin.")
            return upstream_basin_vector_cached, flw_cached

        outlet = self.centerline.interpolate(self.centerline.length * fjord_outlet_offset_frac)
        ((x, y),) = list(outlet.coords)

        flw, dem_clipped = self._get_fjord_flwdir(greenland_bathymetry, buffer_dist=buffer_dist)
        upstream_basin_raster = flw.basin_upstream(
            (x, y),
        ).astype(bool)

        basin_num_pixels = upstream_basin_raster.sum().item()
        if basin_num_pixels < 10:
            raise ValueError(f"Upstream basin too small: {basin_num_pixels} pixel[s]")

        upstream_basin_vector = upstream_basin_raster.rv.to_polygons(combine_polygons=True).geometry
        upstream_basin_vector = (
            upstream_basin_vector.explode().pipe(lambda x: x[x.area == x.area.max()]).reset_index(drop=True)
        )

        outlet = gpd.GeoSeries(outlet, crs=self.crs)

        self.cache["catchment_outlet_offset_frac"] = fjord_outlet_offset_frac
        self.cache["catchment_outlet"] = outlet
        self.cache["flwdir_raster"] = flw
        self.cache["flwdir_dem"] = dem_clipped
        self.cache["upstream_basin_vector"] = upstream_basin_vector
        self.cache["catchment_buffer_dist"] = buffer_dist

        return upstream_basin_vector, flw

    def _get_aggregated_by_polygon(self, input_data: xr.DataArray, agg_method: Callable | str = "median") -> xr.Dataset:
        """
        Aggregates the input data by fjord polygons, returning mean values per polygon.
        """

        fjord_padded = self.cache.get("fjord_padded")
        assert fjord_padded is not None, "Fjord padded polygon must be cached for aggregation."

        input_data_clipped = clip_dataset_to_geom(input_data, fjord_padded, self.epsg)
        input_data = input_data_clipped.sortby(["y", "x"])

        polygon_mask = self.get_fjord_mask(input_data)

        grouped = input_data.groupby(polygon_mask)
        if isinstance(agg_method, str):
            data = getattr(grouped, agg_method)()
        elif isinstance(agg_method, Callable):
            data = grouped.reduce(agg_method)
        else:
            raise ValueError("agg_method must be a string or callable")

        func_info = get_func_info(agg_method)
        data = data.rename(group="index")

        data["index"] = data.index.astype(int)
        data = data.reset_coords(drop=True)

        data = data.rename(input_data.name).assign_attrs(**func_info).to_dataset()

        return data

    def get_aggregated_by_distance(
        self,
        input_data: xr.DataArray,
        agg_method: str | Callable = "median",
        return_clipped_map: bool = False,
    ) -> xr.Dataset:
        """
        Creates a fjord polygon mask on the input data grid.
        """
        fjord_padded = self.cache.get("fjord_padded")

        assert isinstance(input_data, xr.DataArray), "Input data must be an xarray DataArray"
        assert fjord_padded is not None, "Fjord polygon mask has not been computed and cached."

        name = str(input_data.name)
        input_data_clipped = clip_dataset_to_geom(input_data, fjord_padded, self.epsg)
        input_data_clipped = input_data_clipped.rio.reproject("EPSG:4326")

        data = self._get_aggregated_by_polygon(input_data_clipped, agg_method=agg_method)

        data["distance"] = (
            self.polygons.distance_m.pipe(lambda x: x)  # convert to km
            .to_xarray()
            .assign_coords(index=lambda x: x.index + 1)  # match polygon index starting at 1
            .astype("float32")
            .assign_attrs(units="m", description="Distance along fjord centerline from ocean to land")
        )

        data["polygon_area"] = (
            self.polygons["area_m2"]
            .to_xarray()
            .assign_coords(index=lambda x: x.index + 1)  # match polygon index starting at 1
            .assign_attrs(units="m2", description="Area of fjord polygon")
        )

        data["polygon_width"] = (
            self.polygons["width_est_m"]
            .pipe(lambda x: x / 1000)
            .round(1)  # convert to km
            .to_xarray()
            .assign_coords(index=lambda x: x.index + 1)  # match polygon index starting at 1
            .assign_attrs(
                units="km",
                long_name="Width est.",
                description="Estimated width of fjord polygon based on polygon edge adjacent to neighboring polygons",
            )
        )

        data = (
            data.set_coords("distance")
            .swap_dims({"index": "distance"})
            .drop_vars("index")
            .sortby("distance")
            .groupby("distance")
            .mean()
        )

        if return_clipped_map:
            data[name + "_clipped"] = input_data_clipped
        return data

    def compute_polygons(self, interp_distance_m: float | None = None) -> gpd.GeoDataFrame:
        interp_distance_m = interp_distance_m or self.interp_distance_m
        polygons = get_fjord_length_polygons(self.centerline, self.fjord, interp_distance_m).set_crs(epsg=self.epsg)
        polygons["width_est_m"] = get_polygon_widths(polygons.geometry)
        return polygons

    def explore_polygons(self, column="distance_m", diagnostic: bool = False, **kwargs) -> Map:
        from . import vis

        if self.polygons is None:
            raise ValueError("Fjord polygons have not been calculated.")
        crs_web = "EPSG:3857"

        def capitalize(s):
            return s.replace("_", " ").capitalize()

        polygons = (
            self.polygons.to_crs(crs_web)
            .rename(columns=lambda s: capitalize(s))
            .rename(columns={"Geometry": "geometry"})
        )

        if "m" in kwargs:
            m = kwargs.pop("m")
        else:
            m = vis.make_tiles()

        props = dict(m=m, column=capitalize(column), cmap="viridis", legend=False, tooltip=True, name="Polygons")
        props |= kwargs
        m = polygons.explore(**props)  # type: ignore

        if diagnostic:
            nice_props = self._nice_props()
            nice_props.pop("BBox [W, S, E, N]")
            fjord_centerlines = (
                gpd.GeoSeries(self.centerline)
                .set_crs(self.crs)
                .to_crs(crs_web)
                .pipe(gpd.GeoDataFrame, geometry=0)
                .assign(**nice_props)  # type: ignore
            )

            fjord_centerlines.explore(m=m, color="red", style_kwds={"weight": 5, "stroke": True}, name="Centerline")

        m = vis.fit_bounds(m)

        return m

    def plot_polygons(self, crs="EPSG:4326", column="distance_m", land_color="#ccc", **kwargs) -> Axes:
        crs = crs.lower()
        assert crs is not None, "Fjord polygons must have a CRS defined"

        def to_geoseries(geom):
            return gpd.GeoSeries(geom, crs=self.epsg)

        polygons = self.polygons.to_crs(crs)
        land = to_geoseries(self.land.boundary).to_crs(crs)
        centerline = to_geoseries(self.centerline).to_crs(crs)
        outline = to_geoseries(self.fjord).to_crs(crs)
        ocean_marker = to_geoseries(self.ocean_marker).to_crs(crs)

        title = f"Fjord {self.props.get('fjord_num', '')} polygons colored by `{column}`"

        props = (
            dict(
                lw=0.5,
                edgecolor="w",
                cmap="viridis",
                zorder=1,
            )
            | kwargs
            | dict(column=column)
        )

        ax: Axes = polygons.plot(**props)  # type: ignore
        fig: Figure = ax.get_figure()  # type: ignore

        land.plot(ax=ax, facecolor=land_color, edgecolor=land_color, linewidth=1, zorder=1)
        centerline.plot(ax=ax, color="red", linewidth=2, zorder=1)
        outline.plot(ax=ax, facecolor="none", edgecolor="k", linewidth=0.5, zorder=1)
        ocean_marker.plot(ax=ax, color="w", markersize=70, marker="o", zorder=2, edgecolor="k")
        ocean_marker.plot(ax=ax, color="k", markersize=70, marker="+", zorder=2)

        ax.set_xlabel("Longitude")
        ax.set_ylabel("Latitude")
        ax.set_title(title, loc="left")
        ax.grid(True, linestyle="--", alpha=0.5, zorder=0)
        ax.set_axisbelow(True)
        ax.tick_params(axis="both", length=0)

        patches = ax.get_children()[0]
        fig.colorbar(patches, ax=ax, pad=0.005, label=column)  # type: ignore

        [ax.spines[s].set_color("#ccc") for s in ax.spines]

        aspect = ax.get_aspect()
        if aspect != "auto":
            height: float = fig.get_figheight()
            width = height * aspect
            fig.set_figwidth(width)

        return ax

    def to_pickle(self, sname: str | pathlib.Path, with_cache: bool = False, compression: int = 0) -> str:
        import copy
        import pathlib

        import joblib

        path = pathlib.Path(sname)
        path.parent.mkdir(parents=True, exist_ok=True)
        ext = path.suffix
        if ext == "":
            ext = ".pkl_joblib"
            path = path.with_suffix(ext)
            logger.info(f"No suffix provided, saving with suffix {ext}")
        elif not ext.endswith("pkl_joblib"):
            logger.warning(f"Saving with non-standard suffix {ext}, consider using '.pkl_joblib' for clarity")

        obj = copy.copy(self)
        cache = obj.cache
        if not with_cache:
            obj.cache = {}
            joblib.dump(obj, path, compress=compression)
            self.cache = cache
        else:
            flwdir_raster = obj.cache.pop("flwdir_raster", None)
            joblib.dump(obj, path, compress=compression)
            if flwdir_raster is not None:
                obj.cache["flwdir_raster"] = flwdir_raster

        return str(path)

    def _nice_props(self) -> dict[str, object]:

        props = self.props.copy()

        bbox = self.bounds_latlon
        bbox_nice = tuple(np.array(bbox).round(3).tolist())

        props.pop("id", None)
        nice = {
            "Fjord ID": props.pop("fjord_num", "N/A").replace("#", ""),
            "BBox [W, S, E, N]": bbox_nice,
            "CRS": self.crs,
            "Length (km)": f"{props.pop('length_km'):.1f} km",
            "Area (km²)": f"{props.pop('area_km2'):.1f} km²",
            "Width (m)": f"{props.pop('width_m'):.1f} m",
            "Num polygons": props.pop("num_polygons", "N/A"),
            "Centerline branches": props.pop("num_branches", "N/A"),
        }
        for key in props:
            value = props[key]
            key = str(key).replace("_", " ").capitalize()
            nice[key] = value

        return nice

    def __repr__(self) -> str:

        return "<FjordAggregator: " + "; ".join(f"{k}={v}" for k, v in self._nice_props().items()) + ">"

    def _repr_html_(self) -> str:
        # create a basic figure of the fjord polygons and convert to html
        import base64
        import io

        import matplotlib.pyplot as plt

        from . import vis

        if self.repr_plot_type == "static":
            ax = self.plot_polygons()
            fig = ax.get_figure()

            buf = io.BytesIO()
            fig.savefig(buf, format="png", bbox_inches="tight")  # type: ignore
            plt.close("all")
            buf.seek(0)
            img_base64 = base64.b64encode(buf.read()).decode("utf-8")

            image = f'<img src="data:image/png;base64,{img_base64}" alt="FjordAggregator plot"/>'
        elif self.repr_plot_type == "html":
            m = vis.make_tiles()
            m = self.explore_polygons(m=m, diagnostic=True)
            m = vis.finalize_map(m)
            m._children.popitem()
            image = m._repr_html_()

        info = str(self).replace("<", "").replace(">", "").replace("FjordAggregator: ", "")

        # 1. Align the first column right and the second column left
        info = info.replace("=", '</td><td style="text-align: left">')
        info = info.replace(";", '</td></tr><tr><td style="text-align: right;">')

        # 2. Define the header row with specific alignment
        header = (
            "<thead>"
            "<tr>"
            '<th style="text-align: right;">Property</th>'
            '<th style="text-align: left;">Value</th>'
            "</tr>"
            "</thead>"
        )

        # 3. Assemble the final table
        info_table = f'<table >{header}<tbody><tr><td style="text-align: right;">{info}</td></tr></tbody></table>'

        # info as HTML with line breaks where ; occurs
        info_html = info_table
        # wrap info in a div with gray background and padding
        info_html = (
            '<div style="background-color:#eeeeee; padding:10px; border-radius:5px; margin:-10px;">'
            f'<h2 style="margin:1px 0px;">Fjord Info</h2><br>{info_html}</div>'
        )
        # add some HTML styling to make it look nicer, with figure collapsable - default expanded
        image_html = f"<details open><summary>Show / Hide Plot</summary>{image}</details>"
        # wrap image in a div with some padding and border
        image_html = f'<div style="margin-top:15px;">{image_html}</div>'
        html = f"{info_html}{image_html}"
        # wrapped in div with some padding and border
        html = f'<div style="padding:10px; border:1px solid #ccc; border-radius:5px; max-width:600px;">{html}</div>'

        return html


def get_func_info(func: Callable | str) -> dict[str, object]:
    """Return a small description of an aggregation function for xarray attrs.

    Kept intentionally minimal (name + optional basic partial kwargs).
    """
    from functools import partial

    if isinstance(func, str):
        return {"agg_func": func}

    # Unwrap functools.partial to get the underlying callable and (simple) kwargs.
    kwargs: dict[str, object] = {}
    base = func
    while isinstance(base, partial):
        if base.keywords:
            kwargs.update(base.keywords)
        base = base.func  # type: ignore[assignment]

    name = getattr(base, "__name__", None)
    if not name:
        name = type(base).__name__

    info: dict[str, object] = {"agg_func": name}

    # Only keep simple scalar kwargs (attrs should remain serialisable)
    for k, v in kwargs.items():
        if v is None or isinstance(v, (str, int, float, bool)):
            info[f"agg_func_param__{k}"] = v

    return info


def get_nearest_point(line: MultiLineString | LineString, polygon: Polygon) -> Point:
    if isinstance(line, MultiLineString):
        points = []
        for segment in line.geoms:
            point = get_nearest_point(segment, polygon)
            points.append(point)
    else:
        points = [Point(c) for c in line.coords]

    outline = polygon.exterior
    dists = [outline.distance(c) for c in points]
    idx = np.argmin(dists)
    return points[idx]


def clip_dataset_to_geom(
    data: xr.DataArray,
    geom: gpd.GeoSeries | Polygon | MultiPolygon,
    geom_epsg: CRS | str | int | None = None,
    only_bbox: bool = False,
) -> xr.DataArray:
    """
    An efficient way to clip large DataArrays
    by first clipping to the bounding box of the geometry,
    then clipping to the geometry itself.
    """

    assert data.rio.crs is not None, "Input data must have a CRS defined"

    if geom_epsg is None:
        if isinstance(geom, gpd.GeoSeries):
            assert geom.crs is not None, "Geometry GeoSeries must have a CRS defined"
            geom_epsg = geom.crs.to_epsg()
        else:
            raise ValueError("geom_epsg must be provided if geom is not a GeoSeries")
    elif isinstance(geom_epsg, CRS):
        geom_epsg = geom_epsg.to_epsg()
    elif isinstance(geom_epsg, str):
        geom_epsg = int(geom_epsg.replace("EPSG:", ""))
    elif isinstance(geom_epsg, int):
        pass
    else:
        raise ValueError("geom_epsg must be a CRS, str, or int")

    if isinstance(geom, (Polygon, MultiPolygon)):
        geom_with_crs = gpd.GeoSeries([geom], crs=f"EPSG:{geom_epsg}")
    elif isinstance(geom, gpd.GeoSeries):
        geom_with_crs = geom
    else:
        raise ValueError("Geometry must be a Polygon, MultiPolygon, or GeoSeries")

    geom_in_data_crs = geom_with_crs.to_crs(data.rio.crs)

    bounds = geom_in_data_crs.total_bounds.tolist()

    data = data.rio.clip_box(*bounds)
    if only_bbox:
        return data
    else:
        return data.rio.clip(geom_in_data_crs.geometry)


def get_fjord_polygon_mask(fjord_polygons: gpd.GeoDataFrame, target_grid: xr.DataArray) -> xr.DataArray:
    assert target_grid.rio.crs is not None, "Target grid must have a CRS defined"
    assert fjord_polygons.crs is not None, "Fjord geometry must have a CRS defined"

    crs_target = target_grid.rio.crs.to_epsg()

    fjord_polygons = fjord_polygons.to_crs(epsg=crs_target)
    fjord_mask = fjord_polygons.rv.to_raster(target_grid).where(lambda x: x)

    return fjord_mask


def get_fjord_centerline(fjord_geom: Polygon, **kwargs) -> LineString | MultiLineString:
    """
    Docstring for get_fjord_centerline

    :param fjord_geom: Fjord geometry that is a single Polygon
    :type fjord_geom: Polygon
    :param kwargs: Additional keyword arguments to pass to the pygeoops.centerline function
    :return: Centerline of the fjord geometry
    :rtype: LineString | MultiLineString
    """
    from pygeoops import centerline

    props = (
        dict(
            densify_distance=-0.5,
            min_branch_length=-1.5,
            simplifytolerance=1,
            extend=False,
        )
        | kwargs
    )

    num_lines = 4
    while num_lines > 3:
        fjord_centerline: LineString | MultiLineString = centerline(fjord_geom, **props)  # type: ignore
        if isinstance(fjord_centerline, LineString):
            break
        elif isinstance(fjord_centerline, MultiLineString):
            num_lines = len(fjord_centerline.geoms)
            props["min_branch_length"] -= 0.5  # increase min branch length to reduce branches
            if num_lines > 3:
                logger.debug(
                    f"Centerline produced {num_lines} lines, "
                    f"increasing min_branch_length to {props['min_branch_length']}"
                )

    return fjord_centerline


def get_concave_hull_with_buffer(
    polygons: MultiPolygon | Polygon, buffer_distance_m: float, area_threshold_m2: float = 1e7
) -> Polygon:
    w = buffer_distance_m

    if isinstance(polygons, MultiPolygon):
        polygons = MultiPolygon([g for g in polygons.geoms if g.area > area_threshold_m2])

    buffered_polygon = polygons.simplify(w / 2).buffer(w).buffer(-w)

    if isinstance(buffered_polygon, MultiPolygon):
        buffered_polygon = get_largest_polygon(buffered_polygon)

    return buffered_polygon


def get_largest_polygon(polygons: MultiPolygon) -> Polygon:
    area = [p.area for p in polygons.geoms]
    idx = np.argmax(area)
    return polygons.geoms[idx]


def get_bounds(fjord_geom: gpd.GeoSeries | gpd.GeoDataFrame) -> tuple[float, float, float, float]:
    w, s, e, n = tuple(fjord_geom.to_crs(epsg=4326).total_bounds.tolist())
    return (w, s, e, n)


def get_fjord_length_polygons(
    centerline_geom: LineString | MultiLineString,
    mask: MultiPolygon | Polygon,
    polygon_interval_m: float = 5000,
) -> gpd.GeoDataFrame:
    c = MultiLineString([centerline_geom]) if isinstance(centerline_geom, LineString) else centerline_geom

    if c.length < polygon_interval_m:
        logger.debug(
            f"Centerline length {c.length:.1f} m is less than polygon interval "
            f"{polygon_interval_m} m, reducing interval to half the centerline length."
        )
        polygon_interval_m = c.length / 2

    branches = list(c.geoms)
    trunk = branches[0]
    trunk_distances = np.arange(0, trunk.length, polygon_interval_m)
    trunk_points = [trunk.interpolate(d) for d in trunk_distances]

    points = trunk_points.copy()
    distances = trunk_distances.tolist().copy()
    for branch in branches[1:]:
        dist_buffer = trunk.length % polygon_interval_m
        dist_buffer = round(polygon_interval_m - dist_buffer if dist_buffer > 0 else 0)
        branch_distances = np.arange(dist_buffer, branch.length, polygon_interval_m)
        branch_points = [branch.interpolate(d) for d in branch_distances]
        true_distances = (round(trunk.length) + branch_distances).tolist()
        points.extend(branch_points)
        distances.extend(true_distances)

    points = gpd.GeoSeries(points)

    voronoi = points.voronoi_polygons()
    polygon_geoms = voronoi.clip(mask)

    polygon_order = [point.distance(polygon_geoms).argmin().item() for point in points]
    if len(set(polygon_order)) != len(polygon_geoms):
        logger.debug("Polygon order must be unique for each point")
    polygon_geoms = polygon_geoms.iloc[polygon_order].reset_index(drop=True)  # type: ignore

    polygon_areas = polygon_geoms.geometry.area.rename("area_m2")
    polygon_dists = pd.Series(distances, index=polygon_geoms.index, name="distance_m")
    polygon_info = pd.concat([polygon_areas, polygon_dists], axis=1).round()

    polygons = gpd.GeoDataFrame(polygon_info, geometry=polygon_geoms).drop_duplicates(subset="geometry")

    return polygons


def get_polygon_width_along_edges(
    poly: Polygon,
    poly_before: None | Polygon,
    poly_after: None | Polygon,
) -> float:
    """
    Get the width of a polygon along its edges, by averaging the distance to the previous and next polygons.
    If there is no previous or next polygon, we just use the distance to the other one.
    """
    if poly_before is None:
        poly_before = Polygon()
    if poly_after is None:
        poly_after = Polygon()

    points = gpd.GeoSeries(poly.boundary).extract_unique_points().item()
    assert isinstance(points, MultiPoint), "Expected a MultiPoint geometry"

    edge_a = gpd.GeoSeries(poly_before.intersection(points)).explode()
    edge_b = gpd.GeoSeries(poly_after.intersection(points)).explode()

    len_a = edge_a.shift(1).distance(edge_a).max()
    len_b = edge_b.shift(1).distance(edge_b).max()

    len_avg = np.nanmean([len_a, len_b])

    assert isinstance(len_avg, float), "Expected a float value for the average length"

    return len_avg


def get_polygon_widths(polygons: gpd.GeoSeries) -> pd.Series:
    """
    Get the width of each polygon by averaging the distance to the previous and next polygons.
    """

    def geoesries_to_polygon(geom):
        if isinstance(geom, Polygon):
            return geom
        elif isinstance(geom, MultiPolygon):
            return get_largest_polygon(geom)
        else:
            raise ValueError("Expected a Polygon or MultiPolygon geometry")

    widths = pd.Series(index=polygons.index, dtype=float)
    for i in range(polygons.size):
        poly = geoesries_to_polygon(polygons.iloc[i])
        poly_before = geoesries_to_polygon(polygons.iloc[i - 1]) if i > 0 else None
        poly_after = geoesries_to_polygon(polygons.iloc[i + 1]) if i < len(polygons) - 1 else None
        width = get_polygon_width_along_edges(poly, poly_before, poly_after)
        widths.iloc[i] = width
    widths = widths.round(0)
    return widths


def process_multiline(lines: LineString | MultiLineString, ref_point: Point) -> MultiLineString:
    from functools import partial

    set_line_start_near_ocean = partial(set_line_origin_near_point, point=ref_point)

    if isinstance(lines, LineString):
        return MultiLineString([set_line_start_near_ocean(lines)])

    n_lines = len(lines.geoms)

    lines_df = gpd.GeoDataFrame(geometry=gpd.GeoSeries(lines)).explode()
    lines_df["length"] = lines_df.geometry.length
    lines_df["dist_to_ref"] = lines_df.geometry.distance(ref_point)
    lines_df = lines_df.sort_values(["dist_to_ref", "length"], ascending=[True, False])

    # two lines - main trunk, second trunk in narrow section - return longest line only
    if n_lines == 2:
        trunk = lines_df.iloc[0].geometry
        return MultiLineString([set_line_start_near_ocean(trunk)])

    # three branches - main trunk with two branches - return all branches reversed appropriately
    elif n_lines == 3:
        lines_out = [set_line_start_near_ocean(lines_df.iloc[0].geometry)]
        lines_out += [set_line_origin_near_point(lines_df.iloc[i].geometry, lines_out[0]) for i in range(1, 3)]
        return MultiLineString(lines_out)

    else:
        raise ValueError(
            "Cannot handle more than 3 line segments in the centerline. "
            f"Found {n_lines} segments. Something went wrong during centerline generation."
        )


def set_line_origin_near_point(line: LineString, point: Point | LineString) -> LineString:
    start_dist = line.interpolate(0).distance(point)
    end_dist = line.interpolate(line.length).distance(point)
    if end_dist < start_dist:
        line = line.reverse()
    return line


def _set_logger_details(fjord_number: int | str):
    """adjusts the logger so that the fjord number is included in log messages for easier debugging when processing multiple fjords"""
    import sys

    from .core import cfg

    fjord_number = int(str(fjord_number).replace("#", ""))

    format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{line: >4}</cyan> | "
        f"<yellow>Fjord {fjord_number:03d}</yellow> - "
        "<level>{message}</level>"
    )
    logger.remove()  # remove default logger
    logger.add(sys.stdout, format=format, level="INFO")  # add new logger with fjord number in format
    logger.add(
        cfg.ROOT_DIR / "log_process_fjords.log", level="SUCCESS", format=format
    )  # add new logger with fjord number in format
