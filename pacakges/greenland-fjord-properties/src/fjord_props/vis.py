import folium

# example of useage: gdf.explore(**shp.GOOGLE_TERRAIN)
TILES = [
    dict(
        name="Google Terrain",
        tiles="http://mt0.google.com/vt/lyrs=p&hl=en&x={x}&y={y}&z={z}",
        attr="Google",
    ),
    dict(
        name="Google Satellite",
        tiles="http://mt0.google.com/vt/lyrs=s&hl=en&x={x}&y={y}&z={z}",
        attr="Google",
    ),
    dict(
        name="Esri Satellite",
        tiles="http://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attr="Esri",
    ),
    # dict(name="CartoDB Light", tiles="cartodbpositron"),
    dict(name="CartoDB Dark", tiles="cartodbdark_matter"),
    dict(name="OpenStreetMap", tiles="openstreetmap"),
]


def finalize_map(m: folium.Map) -> folium.Map:
    """
    Finalize a folium map by adding a layer control and fitting the bounds

    Parameters
    ----------
    m : folium.Map
        The map to finalize

    Returns
    -------
    folium.Map
    """

    m = fit_bounds(m)
    make_tiles(m)
    folium.LayerControl(collapsed=False).add_to(m)

    return m


def fit_bounds(m: folium.Map) -> folium.Map:
    """
    Fit the bounds of a folium map to its contents

    Parameters
    ----------
    m : folium.Map
        The map to fit the bounds of

    Returns
    -------
    folium.Map
    """

    m.fit_bounds(get_bonuds_from_folium_map(m))
    return m


def make_tiles(m=None, tiles: list[dict] = TILES):
    """
    Add default tiles to a folium map or create a map if not provided

    Parameters
    ----------
    m : Union[None, folium.Map]
        The map to add the tiles to. If None, a new map is created.
    tiles: list[dict]
        A list of dictionaries with the keys 'name', 'tiles', and 'attr'
        following the format of folium.TileLayer

    Returns
    -------
    folium.Map
    """

    if m is None:
        m = folium.Map(tiles=None)

    for tile in tiles:
        folium.TileLayer(**tile).add_to(m)

    return m


def get_bonuds_from_folium_map(m: folium.Map) -> list[list[float]]:
    import folium.features
    import numpy as np

    all_bounds = []
    for name in m._children:
        child = m._children[name]
        if isinstance(child, folium.features.GeoJson):
            data = child.data
            w, s, e, n = data["bbox"]
            w, s, e, n = [float(a) for a in [w, s, e, n]]
            bounds = [w, s, e, n]
            all_bounds.append(bounds)

    if all_bounds:
        w, s, e, n = np.array(all_bounds).T
        w, s, e, n = w.min(), s.min(), e.max(), n.max()
        return [[s, w], [n, e]]

    return m.get_bounds()  # type: ignore
