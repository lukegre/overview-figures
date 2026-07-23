import xarray as xr


def calc_seas_cycle(ds):

    if isinstance(ds, xr.DataArray):
        ds = ds.to_dataset()

    grp = ds.groupby('time.dayofyear')

    ds_sc = xr.Dataset()
    ds_sc['average'] = grp.mean('time').to_array()
    ds_sc['stdev'] = grp.std('time').to_array()
    ds_sc = ds_sc.to_array('metric').to_dataset(dim='variable')

    for key in ds_sc.data_vars:
        ds_sc[key].attrs.update(ds.attrs)

    return ds_sc


def smooth_seas_clim(ds, window=11):
    
    doy = ds.dayofyear.values.tolist()
    n = len(doy)
    doy3 = doy * 3

    ds_padded = ds.sel(dayofyear=doy3)
    ds_rolled = ds_padded.rolling(dayofyear=window, center=True).mean()
    ds_subset = ds_rolled.isel(dayofyear=slice(n, 2*n-1))

    return ds_subset


def make_smooth_seas_cycle(da, smooth_window=21):

    da = smooth_seas_clim(da, window=smooth_window)
        
    avg = da.sel(metric='average')
    std = da.sel(metric='stdev')

    upper = avg + std
    lower = avg - std

    return avg, upper, lower


def get_seasonal_data(da_in):
    from tqdm.dask import TqdmCallback as ProgressBar
    
    da = (
        da_in
        .resample(time='1QS-DEC').mean()
        .pipe(stack_quarterly_seasons)
    )
    
    y0 = da.isel(year=0).count()
    y1 = da.isel(year=1).count()
    yn = da.isel(year=-1).count()
    
    if y0 < y1:
        da = da.isel(year=slice(1, None))

    if yn < y1:
        da = da.isel(year=slice(None, -1))
    
    with ProgressBar():
        da = da.compute()

    return da


def stack_quarterly_seasons(da_quarterly: xr.DataArray):
    
    grp = da_quarterly.groupby('time.season')
    new_dim_name = 'season'
    out = []
    for name, data in grp:
        data = data.expand_dims(**{new_dim_name:[name]})
        data = data.assign_coords(time=lambda x: x.time.dt.year)
        out.append(data)


    out = (
        xr.concat(out, new_dim_name)
        .sel(season=['DJF', 'MAM', 'JJA', 'SON'])
        .transpose(new_dim_name, *da_quarterly.dims)
        .rename(time='year')
    )

    return out