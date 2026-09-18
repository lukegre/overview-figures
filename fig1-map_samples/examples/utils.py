import geopandas as gpd
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import pandas as pd
from shapely.geometry import Point, LineString

GOOGLE_TERRAIN = dict(tiles='http://mt0.google.com/vt/lyrs=p&hl=en&x={x}&y={y}&z={z}', attr='Google')
GOOGLE_SATELLITE = dict(tiles='http://mt0.google.com/vt/lyrs=s&hl=en&x={x}&y={y}&z={z}', attr='Google')


def merge_adjacent_latlon(df, dist_thresh_m=1000):
    """
    Merge adjacent latlon points in the dataframe if 
    the distance between them is less than dist_thresh_m

    Parameters
    ----------
    df : GeoDataFrame
        GeoDataFrame with 'geometry' column
    dist_thresh_m : float, optional
        Distance threshold in meters, by default 300
    """
    import numpy as np

    df.to_crs(epsg=32624, inplace=True)

    dist_squareform = df['geometry'].apply(lambda x: df['geometry'].distance(x))
    near_all = dist_squareform.apply(lambda x: x < dist_thresh_m)
    near_upper_tri = near_all.where(np.triu(np.ones(near_all.shape), 1).astype(bool))

    for i, row in near_upper_tri.iterrows():
        for j, val in row.items():
            if val == True and i != j and i in df.index and j in df.index:
                loc_A = df.geometry.loc[i]
                loc_B = df.geometry.loc[j]
                new_loc = LineString([loc_A, loc_B]).centroid
                df.at[i, 'geometry'] = new_loc
                df = df.drop(j)

    df.to_crs(epsg=4326, inplace=True)
    
    return df


def geopoins_to_linestring(df):
    """
    Convert GeoDataFrame with 'geometry' column containing
    Point geometries to a LineString geometry

    Parameters
    ----------
    df : GeoDataFrame
        GeoDataFrame with 'geometry' column

    Returns
    -------
    GeoDataFrame
        GeoDataFrame with 'geometry' column containing
        LineString geometry
    """
    from shapely.geometry import LineString

    crs = df.crs

    linestring = gpd.GeoSeries(
        data=LineString(df.geometry.values),
        crs=crs).to_frame(name='geometry')
    
    info = get_col_value_if_unique(df)
    for k, v in info.items():
        linestring.loc[0, k] = v
    
    return linestring


def get_col_value_if_unique(df):
    """
    Returns a series that contains the value of the column
    if the value is unique, otherwise that column will not 
    be included in the series
    """
    out = pd.Series()
    for col in df.columns:
        if len(df[col].unique()) == 1:
            out[col] = df[col].unique()[0]

    out = out.dropna()
    return out


def sort_by_distances(df):
    """
    Sort the GeoDataFrame by distances between points

    Parameters
    ----------
    df : GeoDataFrame
        GeoDataFrame with 'geometry' column containing
        Point geometries

    Returns
    -------
    GeoDataFrame
        GeoDataFrame with 'geometry' column containing
        Point geometries sorted by distances
    """

    df.to_crs(epsg=32624, inplace=True)

    dist_squareform = df['geometry'].apply(lambda x: df['geometry'].distance(x))
    point0 = dist_squareform.sum(axis=0).idxmax()
    
    sorted_idx = [point0]
    geometry = df.geometry.copy(deep=True)
    point = geometry.pop(point0)

    for i in range(len(df)-1):
        dist = geometry.distance(point)
        sorted_idx.append(dist.idxmin())
        point = geometry.pop(sorted_idx[-1])
    
    # print(sorted_idx)
    return df.loc[sorted_idx].to_crs(epsg=4326)


def plot_square_bbox(ax, bbox, align=False, **plot_kwargs):
    """
    Plot a bounding box on the map

    Parameters
    ----------
    ax : GeoAxes
        GeoAxes object
    bbox : tuple
        Bounding box coordinates (minx, maxx, miny, maxy)
    align : bool, optional
        Align the bounding box to the map, by default False
    plot_kwargs : dict, optional
        Keyword arguments for the plot function, by default {}
    
    Returns
    -------
    GeoSeries
        GeoSeries object containing the bounding box geometry
    """
    from shapely.geometry import box as Box
    import numpy as np

    epsg = ax.projection.to_epsg()

    bounds_skew = gpd.GeoSeries(Box(*bbox), crs='EPSG:4326').to_crs(epsg=epsg)
    bounds_skew = np.array(bounds_skew.boundary.iloc[0].xy).T[:-1]
    br, tr, tl, bl = bounds_skew

    bottom = (br[1] + bl[1]) / 2
    top = (tr[1] + tl[1]) / 2
    left = (bl[0] + tl[0]) / 2
    right = (br[0] + tr[0]) / 2

    new_bbox = [left, bottom, right, top] 
    arr = gpd.GeoSeries(Box(*new_bbox), crs='EPSG:32624').boundary[0].xy
    arr = np.array(arr)
    ax.plot(arr[0], arr[1], **plot_kwargs)


def get_map_bounds_latlon(ax, map_epsg=3857):
    from shapely import geometry
    import numpy as np
    
    bbox = np.array(ax.get_extent())[[0, 2, 1, 3]]
    geoseries = gpd.GeoSeries(geometry.box(*bbox), crs=f'EPSG:{map_epsg}').to_crs(epsg=4326)
    bbox_tuple = geoseries.total_bounds
    return bbox_tuple


def add_text(ax, x, y, text, **kwargs):
    import matplotlib.patheffects as path_effects

    props = dict(
        transform=ccrs.PlateCarree(), 
        ha='left', 
        va='center', 
        fontsize=6, 
        color='k', 
        zorder=4, 
        weight='bold') | kwargs

    text = ax.text(
        x, y, text, **props)
    text.set_path_effects([path_effects.Stroke(linewidth=0.8, foreground='white', alpha=0.6), path_effects.Normal()])

    return text


def get_copernicus_dem(bbox, epsg=32624):
    import planetary_computer
    import pystac_client
    import stackstac

    collection_name = 'cop-dem-glo-90'
    
    catalog_url = 'https://planetarycomputer.microsoft.com/api/stac/v1'
    client = pystac_client.Client.open(catalog_url, modifier=planetary_computer.sign_inplace)
    result = client.search(
        collections=[collection_name],
        bbox=bbox)
    
    items = result.item_collection()

    da = (
        stackstac.stack(items, epsg=epsg, bounds_latlon=bbox, resolution=90)
        .mean('time')
        .isel(band=0)
        .rename(collection_name.replace('-', '_'))
        .drop_vars([
            'proj:epsg',
            'proj:shape',
        ])
        .rio.write_crs(f'epsg:{epsg}')
    )

    return da


def calc_hillshade(dem):
    from xdem import DEM

    xdem = DEM.from_xarray(dem.compute())
    xdem_hillshade = xdem.hillshade(azimuth=165)
    da_hillshade = xdem_hillshade.to_xarray().isel(band=0).compute()

    return da_hillshade