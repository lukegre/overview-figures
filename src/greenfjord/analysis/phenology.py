import xarray as xr


def get_persistent_periods(mask:xr.DataArray, dim='time', min_gap=60, n_iters=2, return_rolling=False):
    """Get a mask of persistent conditions, where conditions persist for at least `min_gap` days.

    Parameters
    ----------
    mask : xr.DataArray
        A boolean mask of conditions.
    dim : str, optional 
        The dimension to apply the rolling operation. Default is 'time'.
    min_gap : int, optional
        The minimum number of days the condition must persist. Default is 100.

    Returns
    -------
    mask : xr.DataArray
        A boolean mask of persistent conditions.
    """

    assert isinstance(mask, xr.DataArray), 'mask must be a xarray.DataArray'
    assert mask.dtype == bool, 'mask must be a boolean array'

    props = {dim: min_gap, 'min_periods': 1}
    mask = mask.astype('float32')
    frwd = mask.rolling(**props).max().astype(bool)
    bkwd = mask[::-1].rolling(**props).max()[::-1].astype(bool)

    out = (
        (frwd * bkwd)
        .assign_attrs(
            long_name='Persistence mask',
            description=(
                f'A mask that shows where conditions persist for at least {min_gap} '
                'days. Positive values indicate persistent conditions.'),
            iterations=mask.attrs.get('iterations', 0) + 1,
            min_gap=min_gap))
    
    if n_iters > 1:
        n_iters -= 1
        out = get_persistent_periods(out, dim=dim, min_gap=min_gap, n_iters=n_iters, return_rolling=False)

    if return_rolling:
        return xr.merge([
            out.rename('mask'), 
            frwd.rename('mask_forward'), 
            bkwd.rename('mask_backward')])
    else:
        return out.rename('mask')
    

def get_phenology_stats_single_year(mask_year: xr.DataArray, values_year: xr.DataArray=None, doy_neg_wrap=220):
    import calendar as cal

    dim = 'time'
    mask = mask_year
    vals = values_year

    assert isinstance(mask, xr.DataArray), 'mask_year must be a DataArray'
    assert mask.dtype == bool, 'mask_year must be boolean'
    
    assert dim in mask.dims, 'mask_year must have a time dimension'
    n_years = len(set(mask.time.dt.year.values.tolist()))
    assert n_years == 1, 'mask_year must be a single year'
    
    year = mask.time.isel(time=[0]).dt.year.values[0]
    n_days_per_year = 366 if cal.isleap(year) else 365
    min_days_per_year = int(n_days_per_year * 0.92)
    
    assert mask[dim].size > min_days_per_year, f'mask_year must have at least {min_days_per_year} days'

    out = xr.Dataset()
    out['season_duration'] = mask.sum(dim).assign_attrs(units='days', long_name='season duration')

    # getting start and end periods accounting for the year wrap
    diff = mask.astype(int).diff(dim)
    assert abs(diff).sum(dim).all() <= 2, 'mask_year must have a single season or less'

    out['season_start'] = (diff > 0).argmax(dim) + 1
    out['season_end'  ] = (diff < 0).argmax(dim) + 1

    # additional stats
    if vals is not None:
        out['season_count'] = vals.where(lambda x: mask).count(dim)
        out['season_mean'] = vals.where(mask).mean(dim)
        out['season_median'] = vals.where(mask).median(dim)
        out['season_min'] = vals.where(mask).min(dim)
        out['season_max'] = vals.where(mask).max(dim)

    return out


def wrap_doy(doy: xr.DataArray, wrap=220):
    """Wrap day-of-year values around a given threshold.

    Parameters
    ----------
    doy : xr.DataArray
        The day-of-year values to wrap.
    wrap : int, optional
        The threshold to wrap around. Default is day 220.
    
    Returns
    -------
    doy : xr.DataArray
        The wrapped day-of-year values.
    """
    return doy.where(lambda d: d < wrap, doy - 365)


def get_phenology_stats(da: xr.DataArray, mask: xr.DataArray, dim='time', min_gap=60, n_iters=1):
    """Get phenology statistics for a given DataArray and mask.

    Parameters
    ----------
    da : xr.DataArray
        The DataArray to calculate statistics for.
    mask : xr.DataArray
        A boolean mask of conditions.
    dim : str, optional 
        The dimension to apply the rolling operation. Default is 'time'.
    min_gap : int, optional
        The minimum number of days the condition must persist. Default is 100.

    Returns
    -------
    stats : xr.Dataset
        A dataset of phenology statistics.
    """

    assert isinstance(da, xr.DataArray), 'da must be a xarray.DataArray'
    assert isinstance(mask, xr.DataArray), 'mask must be a xarray.DataArray'
    assert mask.dtype == bool, 'mask must be a boolean array'
    assert dim in mask.dims, 'mask must have the same dimension as da'

    vals = da.rename('vals')

    mask = get_persistent_periods(mask, dim=dim, min_gap=min_gap, n_iters=n_iters)

    ds = xr.merge([vals, mask])

    groups = ds.groupby('time.year')
    stats = groups.apply(lambda ds: get_phenology_stats_single_year(ds.mask, ds.vals))

    return stats
