import geopandas as gpd
from shapely.geometry import MultiPolygon, Polygon

from .fjord_aggregator import FjordAggregator
from .load_data import load_fjord_names


def get_fjord_names(
    fjord: Polygon | MultiPolygon,
    fjord_crs: str,
    fjord_names: gpd.GeoDataFrame,
    area_threshold_pct: float = 2,
) -> gpd.GeoDataFrame:

    fjord_names = fjord_names.to_crs(fjord_crs)

    df = fjord_names.clip(fjord)
    df["area_m2"] = df.area
    df["pct_cover"] = (df.area / fjord.area * 100).round(1)

    df = df[df["pct_cover"] > area_threshold_pct]

    df = df.sort_values("pct_cover", ascending=False)

    return df


def set_fjord_names(fjord: FjordAggregator, fjord_names_filename: str) -> FjordAggregator:

    greenland_fjord_names = load_fjord_names(fjord_names_filename)
    fjord_names = get_fjord_names(fjord.fjord, f"EPSG:{fjord.crs.to_epsg()}", greenland_fjord_names)

    n_fjords = len(fjord_names)
    if n_fjords == 0:
        return fjord

    fjord_names_list = ", ".join(fjord_names.placename_official.values)

    fjord.props["Fjord names"] = fjord_names_list

    fjord = set_polygon_names(fjord, fjord_names_filename)

    return fjord


def set_polygon_names(fjord: FjordAggregator, fjord_names_filename: str) -> FjordAggregator:
    greenland_fjord_names = load_fjord_names(fjord_names_filename)
    fjord_names = get_fjord_names(
        fjord.fjord, str(fjord.crs), greenland_fjord_names, area_threshold_pct=0
    )

    polygons = fjord.polygons
    polygons.loc[:, "official_name[s]"] = ""
    for _, fjord_name in fjord_names.iterrows():
        assert "geometry" in fjord_name, ""
        geom = fjord_name.geometry
        name = fjord_name.placename_official
        poly_idxs = polygons.clip(geom).index.values
        existing_name = polygons.loc[poly_idxs, "official_name[s]"]
        updated_name = existing_name.apply(lambda s, name=name: ", ".join(filter(None, [s, name])))
        polygons.loc[poly_idxs, "official_name[s]"] = updated_name
    fjord.polygons = polygons
    return fjord
