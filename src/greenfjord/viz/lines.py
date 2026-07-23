import matplotlib.pyplot as plt
import pandas as pd
import pathlib
from typing import Tuple
import xarray as xr

STYLE = pathlib.Path(__file__).parent / 'lineplot.mplstyle'


def plot_monthly_mean_timeseries(da, mpl_style=STYLE):
    from ..analysis.trends import detrend

    assert da.ndim == 1, 'DataArray must have only one dimension'
    assert 'time' in da.dims, 'DataArray must have a time dimension'

    da_mon = da.resample(time='1MS').mean()
    
    last_month = da_mon.time.dt.month[-1]
    first_year = int(da_mon.time.dt.year[0])
    last_year = int(da_mon.time.dt.year[-1])
    last_full_year = last_year if last_month == 12 else last_year - 1
    da_mon_clipped = da_mon.sel(time=slice(f'{first_year}-01-01', f'{last_full_year}-12-31'))

    da_min = da_mon_clipped.roll(time=6).resample(time='1YS').min()
    da_max = da_mon_clipped.resample(time='1YS').max().assign_coords(time=lambda x: x.time.values + pd.Timedelta('170D'))
    da_smooth = (
        da_mon
        .rolling(time=24, center=True).mean()
        .rolling(time=12, center=True).mean())
    
    with plt.style.context(mpl_style):
        fig, ax = plt.subplots()

        da_mon.plot(lw=0.5, color='k', ax=ax, alpha=0.4)
        ax.axhline(da_mon.mean(), color='k', lw=0.5, ls=':')

        da_smooth.plot(lw=3, color='k', ax=ax)
        da_min.plot(lw=0.5, color='k', ax=ax)
        da_max.plot(lw=0.5, color='k', ax=ax)

        da_min_2sigma = da_min.pipe(detrend).std() * 2
        da_max_2sigma = da_max.pipe(detrend).std() * 2
        x = da_mon.time.max() + pd.Timedelta('250D')
        
        # plot a bar that shows the standard deviation of da_min and da_max 
        # at the last time step centred on the average of each respectively
        xlim = ax.get_xlim()
        w = (xlim[1] - xlim[0]) * 0.015
        props = dict(width=w, color='k', alpha=0.2, zorder=2)
        ax.bar(x, da_min_2sigma, bottom=da_min[-1] - da_min_2sigma / 2, **props)
        ax.bar(x, da_max_2sigma, bottom=da_max[-1] - da_max_2sigma / 2, **props)

        props = dict(va='center', ha='left', zorder=3)
        sigma = r'$\sigma$'
        ax.text(x + pd.Timedelta('400D'), da_min[-1], s=f'2{sigma} = {float(da_min_2sigma):.01f}', **props)
        ax.text(x + pd.Timedelta('400D'), da_max[-1], s=f'2{sigma} = {float(da_max_2sigma):.01f}', **props)
        ax.set_xlim(da.time.min(), da.time.max() + pd.Timedelta('400D'))

        ax.set_xlabel('')
        ax.set_ylabel(da.name)

    return fig, ax


def plot_line_envelope(da_avg: xr.DataArray, da_std: xr.DataArray, **kwargs):
    
    ax = kwargs.get('ax', None)
    if ax is None:
        fig, ax = plt.subplots()
        kwargs['ax'] = ax
    else:
        fig = ax.get_figure()

    props = dict(
        lw=0.5,
        alpha=0.8,
    )
    props.update(kwargs)
    
    line = da_avg.plot.line(**props)[0]
    
    d0 = da_avg.dims[0]
    x = da_avg[d0]
    upper = da_avg + da_std
    lower = da_avg - da_std
    props_envelope = dict(color=line.get_color(), alpha=0.2)
    ax.fill_between(x, upper, lower, **props_envelope)

    ax.set_xlabel('')
    ax.set_title('')

    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

    return fig, ax