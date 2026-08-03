import geopandas as gpd
from shapely import MultiPolygon, Polygon

from .catchment_discharge import get_downstream_polygon_distance, xrFlwdir
from .fjord_aggregator import FjordAggregator


def get_catchment_glacier_fronts(
    fjord: FjordAggregator,
    marine_terminating_glacier_fronts: gpd.GeoDataFrame,
) -> gpd.GeoDataFrame:

    catchment = fjord.cache.get("upstream_basin_vector")
    flwdir_raster = fjord.cache.get("flwdir_raster")
    if catchment is None or flwdir_raster is None:
        raise ValueError("FjordAggregator must have 'upstream_basin_vector' and 'flwdir_raster' in its cache.")

    crs = catchment.crs
    assert crs is not None
    assert marine_terminating_glacier_fronts.crs is not None

    # create catchment polygon in fjord fronts crs
    catchment_in_fronts_crs = catchment.to_crs(marine_terminating_glacier_fronts.crs)
    # clip marine terminating fronts to catchment polygon
    glacier_fronts = marine_terminating_glacier_fronts.clip(catchment_in_fronts_crs).to_crs(crs)

    glacier_fronts = glacier_fronts.sort_values(by=["Glacier", "Year", "Day_of_Year"])

    glacier_fronts = summarize_glacier_fronts(glacier_fronts, fjord=fjord.fjord)

    glacier_fronts = get_glacier_inflow_polygons(
        glacier_fronts,
        flwdir_raster,
        fjord.polygons,
    )

    return glacier_fronts


def get_glacier_inflow_polygons(
    glacier_fronts: gpd.GeoDataFrame,
    flowdir_raster: xrFlwdir,
    fjord_polygons: gpd.GeoDataFrame,
) -> gpd.GeoDataFrame:

    points = glacier_fronts.geometry.representative_point()

    for i, row in points.items():
        assert isinstance(i, int), f"Expected integer index, got {type(i)}"
        # the code in the first part of the if statement is to catch bad DEM "events"
        # where points flow up the glacier and into another fjord and then further
        # down join the main fjord, which causes the direct distance to be small but the actual flow distance to be large
        direct_distance = fjord_polygons.distance(row)
        if (direct_distance < 1000).any():
            j = direct_distance.idxmin()
            dist = fjord_polygons.loc[j, "distance_m"]
        else:
            xy = float(row.x), float(row.y)  # type: ignore[attr-defined]
            dist = get_downstream_polygon_distance(xy, flowdir_raster, fjord_polygons)

        glacier_fronts.loc[i, "polygon_distance"] = dist

    return glacier_fronts


def summarize_glacier_fronts(
    glacier_fronts: gpd.GeoDataFrame,
    grouping_name="Glacier",
    sort_cols=("Glacier", "Year", "Day_of_Year"),
    fjord: MultiPolygon | Polygon | None = None,
    glacier_in_fjord_dist_threshold_m: float = 1500,
) -> gpd.GeoDataFrame:

    glacier_fronts = glacier_fronts.sort_values(by=list(sort_cols))
    glacier_fronts["length_m"] = glacier_fronts.geometry.length.round()

    grouped = glacier_fronts.groupby(grouping_name)

    df = grouped.agg(
        dict(
            length_m="last",
            geometry="last",
            Year="last",
        )
    )

    if fjord is not None:
        df = gpd.GeoDataFrame(df, geometry="geometry")
        df["dist_from_fjord_m"] = df.geometry.distance(fjord, align=False).round()
        df["glacier_in_main_fjord"] = df["dist_from_fjord_m"] < glacier_in_fjord_dist_threshold_m

    df = df.reset_index().rename(columns={"index": "Glacier"})

    gdf = gpd.GeoDataFrame(df, geometry="geometry", crs=glacier_fronts.crs).rename(columns=lambda s: s.lower())

    return gdf
