import numpy as np
import xarray as xr
from loguru import logger
from functools import lru_cache as _lru_cache
from ..config import BBOX_OCEAN as BBOX


@_lru_cache
def get_gebco(compute=False):
    from ..config import FNAME_S3_GEBCO

    ds = xr.open_zarr(FNAME_S3_GEBCO)
    ds = (
        ds
        .rename(lat='y', lon='x')
        .rio.write_crs('EPSG:4326')
        .sel(y=slice(BBOX[1], BBOX[3]), x=slice(BBOX[0], BBOX[2]))
    )

    da = ds.elevation.rename('bathymetry')

    if compute:
        da = da.compute()

    return da


@_lru_cache
def get_dist2coast(compute=False):
    from ..config import FNAME_S3_DIST2COAST

    ds = xr.open_zarr(FNAME_S3_DIST2COAST)
    ds = (
        ds
        .rename(lat='y', lon='x', dist='dist2coast')
        .sortby('y', ascending=True)
        .sortby('x')
        .rio.write_crs('EPSG:4326')
        .sel(
            y=slice(BBOX[1], BBOX[3]), 
            x=slice(BBOX[0], BBOX[2])))

    da = ds.dist2coast
    da.attrs = {**da.attrs, **ds.attrs}

    if compute:
        da = da.compute()

    return da


def get_nao_index_monthly(flavour:str='CPC'):
    import pandas as pd

    if flavour.lower() == 'jones':
        url = "https://psl.noaa.gov/data/correlation/jonesnao.data"
        start = 1948
        end = 2022
    elif flavour.lower() == 'cpc':
        start = 1950
        end = pd.Timestamp.now().year
        url = "https://www.cpc.ncep.noaa.gov/products/precip/CWlink/pna/norm.nao.monthly.b5001.current.ascii.table"
    else:
        raise ValueError(f"Unknown NAO flavour: {flavour}, should be 'CPC' or 'Jones'")
    
    df = pd.read_csv(url, sep='\s+', skiprows=1, header=None, na_values=-99.99, nrows=end-start+1)
    df.columns = ['year'] + list(range(1, 13))

    df = df.set_index('year').stack()
    df.index.names = 'year', 'month'
    dates = (
        df.index
        .to_frame()
        .astype(str)
        .assign(month=lambda x: x.month.str.zfill(2))
        .sum(axis=1)
        .pipe(lambda x: pd.to_datetime(x, format='%Y%m')))

    df = df.to_frame(name='NAO')
    df['time'] = dates.values.squeeze()
    nao = df.reset_index(drop=True).set_index('time')['NAO']

    nao = nao.to_xarray()
    nao.attrs['source'] = url

    return nao


def get_ocean_regions(da_like=None, shelf_depth_limit=-500, closing_radius=5, min_hole_pixel_size=10000, return_figure=False):
    import xarray as xr
    import xarray_raster_vector as xrv  # noqa - imported for morphological accessors
    from skimage.morphology.footprints import disk

    boundsEW = -44.3
    boundsNS = 61
    boundsNS = -47.8

    names = [
        'Near-shore\n(< 4 km from coast)\n(not used)', 
        f'Oceanic\n(> {-shelf_depth_limit} m deep)', 
        f'Southwest\n(> {boundsNS}°E, < {boundsEW}°E)', 
        f'Central western\n(< {boundsNS}°E)', 
        f'South Eastern\n(> {boundsEW}°E)']

    if da_like is not None:
        assert da_like is None or isinstance(da_like, xr.DataArray), 'da_like must be a DataArray'
        assert len(da_like.dims) == 2, 'da_like must be a 2D DataArray with dimensions lat and lon'

        y, x = list(da_like.dims)
        da_like = da_like.rename({y: 'y', x: 'x'}).rio.write_crs(4326)
    
    # bathymetry
    bath_da = get_gebco(compute=True)
    dist_da = get_dist2coast(compute=True).rio.reproject_match(bath_da)

    shelf = (
        (bath_da > shelf_depth_limit)  # must be shallower than given depth
        & 
        (dist_da > 4)     # must be at least 4 km from coast
        & 
        (dist_da.y > 56))  # must be north of 56N
    
    open_ocean = (
        (bath_da < shelf_depth_limit)  # must be deeper than given depth
        & 
        (dist_da > 10))  # must be at least 10 km from coast

    lon = bath_da.x

    shelf_sw = shelf & (lon < boundsEW) & (lon  < boundsNS)
    shelf_nw = shelf & (lon < boundsEW) & (lon >= boundsNS)
    shelf_e = shelf & (lon >= boundsEW)
    layers = [open_ocean, shelf_nw, shelf_sw, shelf_e]

    mask = xr.DataArray(
        data=np.zeros(bath_da.shape, dtype=int),
        dims=bath_da.dims,
        coords=bath_da.coords,
        name='region')
    
    for i, da in enumerate(layers):
        da = (
            da
            .astype(bool)
            .morph.binary_closing(footprint=disk(closing_radius))
            .morph.remove_small_holes(area_threshold=min_hole_pixel_size))
        
        mask = mask.where(~da, float(i+1))
        
    mask = (
        mask
        .rio.write_crs("epsg:4326")
        .assign_attrs(
            long_name="Oceanic regions",
            units="no units",
            description=(
                "Oceanic regions defined by bathymetry and distance "
                "to coast. Created for GreenFjord Project."),
            names=names,
            shelf_depth_limit=shelf_depth_limit,
            boundsEW=boundsEW,
            boundsNS=boundsNS,
            cleaning_closing_footprint=f"disk(radius={closing_radius})",
            cleaning_small_holes_threshold=min_hole_pixel_size))
    
    if da_like is not None:
        logger.info('Reprojecting mask to match da_like')
        mask = mask.rio.reproject_match(da_like)

    if return_figure:
        return mask, _plot_ocean_region_map(mask)
    
    return mask


def _plot_ocean_region_map(da, **kwargs):
    import numpy as np
    from ..viz.geo import plot_map

    da = da.where(lambda x: x > 0)
    x, y = da.x.isel(x=-120), da.y.isel(y=-2)
    da.loc[y, x] += 1

    x, y = da.x.isel(x=-121), da.y.isel(y=-2)
    da.loc[y, x] += 2
    
    vmax = da.loc[y, x].item() + 1

    props = dict(aspect=1.5, size=4, levels=np.arange(0.5, vmax), colors=['C0', 'C1', 'C2', 'C3', 'C4', 'none'], plot_type='contourf', cbar_kwargs=dict(drawedges=True, aspect=10))
    props.update(kwargs)
    fig, ax, img = plot_map(da, **props)
    
    ax.set_aspect(2)
    ax.set_title(f'Regional mask')

    img.colorbar.set_ticks(np.mgrid[1:vmax])
    labels = (da.names[1:] + ['Ice sheet', 'GreenFjord'])
    img.colorbar.set_ticklabels(labels)
    img.colorbar.set_label('')
    img.colorbar.ax.tick_params(length=0)

    fig.metadata = dict(
        title='Ocean regions in the GreenFjord domain',
        description=(
            'Regions are defined based on bathymetry and distance to coast. '
            'Shelf is defined as bathymetry > -500 m and distance to coast > 4 km. '
            'Open ocean is defined as bathymetry < -500 m and distance to coast > 10 km.'),
        data_source='https://www.gebco.net/data_and_products/gridded_bathymetry_data/',
        func='src.clusters.ocean.ocean_mask',
    )
    
    return fig, ax, img