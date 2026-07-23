from ..config import FNAME_S3_ERA5, BBOX_OCEAN as BBOX

pretty_names = dict(
    sp='Surface pressure',
    tp='Total precipitation',
    si10='10m wind speed',
    i10fg='10m wind gust',
    hcc='High cloud cover',
    mcc='Medium cloud cover',
    lcc='Low cloud cover',
    tcc='Total cloud cover',
    cbh='Cloud base height',
    d2m='Dewpoint temperature',
    t2m='2m temperature',
)

def get_era5():
    import xarray as xr
    import warnings

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=RuntimeWarning)
        ds = xr.open_zarr(FNAME_S3_ERA5)

    ds = (
        ds
        .rename(latitude='y', longitude='x')
        .rio.write_crs(4326)
        .rio.clip_box(*BBOX)
        [list(pretty_names)]
    )
    
    for key in pretty_names:
        if key in ds:
            ds = ds.assign_attrs(**{'long_name': pretty_names[key]})

    return ds
