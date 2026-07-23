import pandas as pd
import xarray as xr
from functools import lru_cache


def tide_analysis(tide_height: xr.DataArray, ndays:int=30)->dict:
    from scipy import signal

    # get times for present and past 30 days
    time = tide_height.time.to_index()
    t1 = time[-1]
    t0 = t1 - pd.DateOffset(days=ndays)

    da = tide_height.sel(time=slice(t0, t1))
    da_smooth = da.rolling(time=12, center=True, min_periods=1).mean()

    peaks = signal.find_peaks(da_smooth, distance=24, width=5)[0]
    valleys = signal.find_peaks(-da_smooth, distance=24, width=5)[0]
    high_tides = da.isel(time=peaks)
    low_tides = da.isel(time=valleys)

    # high_tides and low_tides may have different lengths
    # make sure they have the same length
    if high_tides.time.size > low_tides.time.size:
        high_tides = high_tides.isel(time=slice(0, low_tides.time.size))
    elif high_tides.time.size < low_tides.time.size:
        low_tides = low_tides.isel(time=slice(0, high_tides.time.size))
    # assert the outcome is correct
    assert low_tides.time.size == high_tides.time.size

    tide_amp = xr.DataArray(
        high_tides.values - low_tides.values,
        dims='time',
        coords={'time': high_tides.time})
    tide_amp_smooth = (
        tide_amp
        .rolling(time=3, center=True, min_periods=1).mean()
        .rolling(time=3, center=True, min_periods=1).mean()
        .rolling(time=3, center=True, min_periods=1).mean())
    
    peaks = signal.find_peaks(tide_amp_smooth)[0] + 1
    valleys = signal.find_peaks(-tide_amp_smooth)[0] 
    spring_tides = high_tides.sel(time=tide_amp.isel(time=peaks).time, method='nearest')
    neap_tides = high_tides.sel(time=tide_amp.isel(time=valleys).time, method='nearest')

    ds = xr.Dataset()
    ds['tides'] = da
    ds['high_tides'] = high_tides.rename(time='time_high')
    ds['low_tides'] = low_tides.rename(time='time_low')
    ds['tidal_range'] = tide_amp.rename(time='time_high')
    ds['spring_tides'] = spring_tides.rename(time='time_spring')
    ds['neap_tides'] = neap_tides.rename(time='time_neap')

    seconds_since = lambda x: (t1 - x.time.to_index().max()).total_seconds()
    ds.attrs['days_since_last_spring_tide'] = seconds_since(spring_tides) / 86400
    ds.attrs['days_since_last_neap_tide'] = seconds_since(neap_tides) / 86400
    ds.attrs['hours_since_last_high_tide'] = seconds_since(high_tides) / 3600
    ds.attrs['hours_since_last_low_tide'] = seconds_since(low_tides) / 3600
    ds.attrs['tidal_range_latest_meters'] = tide_amp.isel(time=-1).item()

    if ds.attrs['hours_since_last_high_tide'] > 12.1:
        ds.attrs['hours_since_last_high_tide'] -= 12.0833
    if ds.attrs['hours_since_last_low_tide'] > 12.1:
        ds.attrs['hours_since_last_low_tide'] -= 12.0833

    gradient = da_smooth.diff('time')
    recent_gradient = gradient.isel(time=slice(-5, None)).mean().item()
    ds.attrs['tidal_phase'] = 'flood' if recent_gradient > 0 else 'ebb'

    since_high = ds.attrs['hours_since_last_high_tide']
    since_low = ds.attrs['hours_since_last_low_tide']
    txt = "Tide is " + ds.attrs['tidal_phase'] + 'ing.'

    if since_high < since_low:
        txt += f' Hours since last high tide: {since_high:.1f}'
    else:
        txt += f' Hours since last low tide: {since_low:.1f}'
    ds.attrs['summary'] = txt

    return ds


def get_tide_height(years:list)->pd.Series:
    ser = pd.concat([get_tide_height_single_year(year) for year in years], axis=0)
    da = ser.to_xarray().rename(datetime='time').rename('tide_height')
    da = da.resample(time='5min').mean()
    
    return da


@lru_cache
def get_tide_height_single_year(year:int)->pd.Series:
    flist_all = download_tide_data(year)
    flist = _get_flist_variable(flist_all, 'qaqo', 'height.txt')
    height = pd.concat([read_tide_height_txt(f) for f in flist], axis=0)
    height_5min = height.resample('5min').mean()
    return height_5min


def download_tide_data(year, dest_dir='../data/'):
    # Can't find how i found these links. But the offcial channel to get this data is 
    # https://uhslc.soest.hawaii.edu/data/, but this is only from 2005 onward
    try:
        url = f'ftp://ftp.space.dtu.dk/pub/Sealevel/{year}.ZIP'
        flist = _download_data(url)
    except:
        url = f'ftp://ftp.space.dtu.dk/pub/Sealevel/{year}.zip'
        flist = _download_data(url)

    return flist


def _download_data(url):
    import pooch

    name = url.split('/')[-1].lower()
    fname = f'dtu_sealevel_{name}'
    flist = pooch.retrieve(
        url=url, 
        known_hash=None,
        path='../data/tide_data/',
        fname=fname,
        processor=pooch.Unzip())
    
    return flist


def _get_flist_variable(flist_all, villiage_prefix='qaqo', variable='height.txt'):
    flist = sorted([
        f for f in flist_all 
        if (
            (villiage_prefix in f) 
            and 
            (f.endswith(variable))
        )])
    
    return flist


def read_tide_height_txt(fname:str) -> pd.Series:
    df = pd.read_fwf(fname, header=None, names=['date', 'time', 'height', 'flag'])
    series = (
        df
        .assign(datetime=lambda x: pd.to_datetime(x['date'] + ' ' + x['time']))
        .set_index('datetime')
        .where(lambda x: x['flag'] == 1)
        .dropna()
        .drop(columns=['flag', 'date', 'time'])
        .height)
    
    return series