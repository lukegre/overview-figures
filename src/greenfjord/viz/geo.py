_LEAFLET_DEFAULTS = dict()
GOOGLE_TERRAIN = dict(
    tiles="http://mt0.google.com/vt/lyrs=p&hl=en&x={x}&y={y}&z={z}",
    attr="Google",
    **_LEAFLET_DEFAULTS,
)
GOOGLE_SATELLITE = dict(
    tiles="http://mt0.google.com/vt/lyrs=s&hl=en&x={x}&y={y}&z={z}",
    attr="Google",
    **_LEAFLET_DEFAULTS,
)


def plot_map_subplots(
    da, axis=0, dim=None, suptitle="", plot_type="imshow", land_color="0.95", **kwargs
):

    if dim is None:
        dim = da.dims[axis]

    props = dict(
        col=dim,
        col_wrap=2,
        robust=True,
        cbar_kwargs=dict(
            pad=0.03,
        ),
    )

    props.update(kwargs)
    fg = getattr(da.plot, plot_type)(**props)

    fg.set_titles(template="{value}", maxchar=50)
    fg.set_xlabels("Longitude", size="medium")
    fg.set_ylabels("Latitude", size="medium")

    cbar = fg.cbar
    cbar_label = cbar.ax.get_ylabel() if cbar.orientation == "vertical" else cbar.ax.get_xlabel()

    cbar.set_label(cbar_label.replace("\n", " "))

    [add_coastline(ax, land_kwargs=dict(facecolor=land_color)) for ax in fg.axs.flat]

    p = fg.axs.flat[0].get_position()
    fg.fig.text(p.x0, p.y1 + 0.03, suptitle + "\n", ha="left", va="bottom", fontsize="medium")

    fg.fig.metadata = dict(title=suptitle)

    return fg


def plot_map(da, ax=None, land_color="#cccccc", plot_type="imshow", **kwargs_imshow):
    from matplotlib.pyplot import subplots

    props = dict(robust=True, rasterized=True, zorder=1, cbar_kwargs=dict(pad=0.03))

    if ("size" not in kwargs_imshow) and kwargs_imshow.get("ax", None) is None:
        fig, ax = subplots(dpi=150, figsize=[8, 5])
        props["ax"] = ax

    props.update(kwargs_imshow)

    if not props.get("add_colorbar", True):
        # logger.debug('removing colorbar properties since add_colorbar is False')
        props["cbar_kwargs"] = None

    img = getattr(da.plot, plot_type)(**props)
    ax = img.axes
    fig = ax.figure

    bbox = da.rio.bounds()
    add_coastline(ax, land_kwargs=dict(facecolor=land_color))

    if hasattr(da, "name"):
        fig.fname = f"{da.name}.png"

    ax.set_ylim(bbox[1], bbox[3])
    ax.set_xlim(bbox[0], bbox[2])

    for spine in ax.spines.values():
        spine.set_visible(True)
        spine.set_linewidth(0.5)
        spine.set_color("k")
        spine.set_zorder(5)

    return fig, ax, img


def add_coastline(ax, epsg=4326, land_kwargs={}, coast_kwargs={}):
    import geopandas as gpd
    from cartopy import feature
    from loguru import logger

    xlim = ax.get_xlim()
    ylim = ax.get_ylim()
    dx = max(xlim) - min(xlim)
    dy = max(ylim) - min(ylim)

    bbox = [min(xlim), min(ylim), max(xlim), max(ylim)]

    min_res = min(dx, dy)
    if min_res < 40:
        feature_land = feature.LAND.with_scale("10m")
    elif min_res < 80:
        feature_land = feature.LAND.with_scale("50m")
    else:
        feature_land = feature.LAND.with_scale("110m")

    logger.debug(f"Using coastal resolution {feature_land.scale}")
    geoms = feature_land.geometries()
    df = gpd.GeoSeries([k for k in geoms], crs=f"EPSG:{epsg}").to_crs(epsg=epsg).clip_by_rect(*bbox)

    land_props = dict(facecolor="k", zorder=1, edgecolor="k", lw=0.3)
    land_props.update(land_kwargs)

    logger.debug(f"Adding land to map with properties: {land_props}")
    df.plot(ax=ax, **land_props)

    ax.set_ylim(bbox[1], bbox[3])
    ax.set_xlim(bbox[0], bbox[2])
