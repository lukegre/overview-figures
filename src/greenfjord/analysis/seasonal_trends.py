from typing import Callable

import pandas as pd
import xarray as xr

from .trends import theilsen_mannkendall


def preprocess_data(da_in, clip_time=True):
    """
    Resamples the time dimensions so that the shape of the dataset is (year, season, ...)

    Note that the start and end times are taken from config.TIME_START and config.TIME_END

    Parameters
    ----------
    da_in : xarray.DataArray
        The input data array

    Returns
    -------
    xarray.DataArray
        The resampled data array
    """
    from ..config import TIME_END, TIME_START

    t0 = pd.Timestamp(TIME_START).year
    t1 = pd.Timestamp(TIME_END).year

    da_seas = da_in.resample(time="QS-DEC").mean()

    year = da_seas.time.dt.year
    season = da_seas.time.dt.season

    da_out = (
        da_seas.assign_coords(year=("time", year.data), season=("time", season.data))
        .set_index(time=("year", "season"))
        .unstack("time")
        .sel(season=["MAM", "JJA", "SON", "DJF"])
        .transpose("year", "season", ...)
    )

    if clip_time:
        da_out = da_out.sel(year=slice(t0, t1))

    return da_out


def get_n_pixels(trend_output):
    return (
        trend_output.sel(parameter="pvalue", drop=True)
        .count(dim=["x", "y"])
        .drop_vars("spatial_ref", errors="ignore")
    )


def get_significant_slope(trend_output, threshold=0.05):
    pvalue = trend_output.sel(parameter="pvalue", drop=True)
    slope = trend_output.sel(parameter="slope", drop=True)

    slope_significant = slope.where(pvalue < threshold).drop_vars("spatial_ref", errors="ignore")

    return slope_significant


def get_n_significant(
    trend_output, agg_dim=["x", "y"], threshold=0.05, as_fraction=False, return_dataframe=False
):
    pvalue = trend_output.sel(parameter="pvalue", drop=True)

    significant = pvalue < threshold
    n_significant = significant.sum(dim=agg_dim)

    drop = ["spatial_ref", "parameter"]
    n_significant = n_significant.drop_vars(drop, errors="ignore")

    if as_fraction:
        n_pixels = get_n_pixels(trend_output)
        n_significant = n_significant / n_pixels

    if not return_dataframe:
        return n_significant
    else:
        return n_significant.to_dataframe().T.round(3)


def get_significant_trend_direction_pos_neg(trend_output, agg_dim=["x", "y"]):

    n_pixels = get_n_pixels(trend_output)
    slope = get_significant_slope(trend_output)

    pos_count = slope.where(slope > 0).count(dim=agg_dim)
    neg_count = slope.where(slope < 0).count(dim=agg_dim)

    pos_frac = (pos_count / n_pixels).to_dataframe().T
    neg_frac = (neg_count / n_pixels).to_dataframe().T

    return pos_frac, neg_frac


def plot_significant_trend_direction_pos_neg(
    sig_trend_frac_pos, sig_trend_frac_neg, mpl_style="_mpl-gallery"
):
    import matplotlib.pyplot as plt
    import seaborn as sns

    from ..config import TIME_END, TIME_START

    t0 = pd.Timestamp(TIME_START).year
    t1 = pd.Timestamp(TIME_END).year

    with plt.style.context(mpl_style):
        sns.set_palette("tab10")

        fig, ax = plt.subplots(figsize=(6, 5), dpi=140)

        props = dict(
            color=["C0", "C2", "C3", "C1"], ax=ax, stacked=True, zorder=2, lw=1, edgecolor="w"
        )
        ax = (-sig_trend_frac_neg).plot.barh(**props, alpha=0.5)
        ax = (+sig_trend_frac_pos).plot.barh(**props)
        ax.legend(
            ncol=2, frameon=False, fontsize="small", loc="upper left", title="Negative | Positive"
        )

        ax.axvline(0, color="k", lw=0.5)

        ax.set_xlim(-2, 4)
        ax.grid(axis="x", which="both", lw=0.5, color="0.9", zorder=1)
        ax.set_xlabel("Significant trends\n[fraction negative | fraction positive]")

        title = f"Pixel fraction of significant positive and negative\ntrends in Greenfjord domain for each season [{t0}-{t1}]"
        ax.set_title(title, ha="left", x=0.01)

        fig.metadata = dict(
            title=title,
            source="ERA5 monthly data from CDS resampled to seasonal data",
            period=f"{t0}-{t1}",
            description=(
                "The plot shows the fraction of significant positive and negative trends in the Greenfjord land domain for each season. "
                "This was calculated using Sen's slope estimator and the ordinary Mann-Kendall test (alpha=0.95). "
                "The Theil-Sen slopes are calculated as the median of all possible slopes between two points. "
                "The Mann-Kendall test is a non-parametric test for monotonic trends, i.e., non-linear trends are also detected. "
                f"Trends were calculated for the period {t0}-{t1}. "
                f"The AOI has a pixel size of 48 at 0.25° x 0.25° pixel sizes. "
            ),
        )

    return fig, ax


def calc_trend_start_sensitivity(
    ds_in, trend_func: Callable = theilsen_mannkendall, min_years=15, step_size=2, **kwargs
):
    """
    Calculate the sensitivity of the trend to the start year

    Parameters
    ----------
    ds_in : xarray.DataArray / xarray.Dataset
        The input data array
    trend_func : callable
        The function to calculate the trend
    start_year : int
        The start year
    end_year : int
        The end year
    n_years : int, optional
        The number of years to calculate the trend for, by default 10

    Returns
    -------
    xarray.DataArray
        The sensitivity of the trend to the start year
    """

    t0 = ds_in.year.min().item()
    t1 = ds_in.year.max().item() + 1

    trends = []
    for start_year in range(t0, t1 - min_years, step_size):
        print(start_year, end=": ")
        for end_year in range(start_year + min_years, t1, step_size):
            print(end_year, end=" ")
            subset = ds_in.sel(year=slice(start_year, end_year))
            # NOTE: Dataset.apply/map never keeps the attrs that trend_func assigns
            # (e.g. "method"). With keep_attrs=True/None it copies the *original*
            # variable attrs over the result; with False it drops them entirely.
            # So we build the Dataset from per-variable trend_func calls instead,
            # which preserves each variable's returned attrs.
            if isinstance(subset, xr.Dataset):
                subset_trend = xr.Dataset(
                    {key: trend_func(subset[key], dim="year") for key in subset.data_vars}
                )
            else:
                subset_trend = trend_func(subset, dim="year")
            subset_trend = subset_trend.expand_dims(start_year=[start_year], end_year=[end_year])
            trends += [subset_trend]
        print("")

    trends = xr.combine_by_coords(trends, combine_attrs="override")

    if isinstance(trends, xr.Dataset):
        for key in trends.data_vars:
            trends[key] = trends[key].assign_attrs(ds_in[key].attrs)
            if "units" in ds_in[key].attrs:
                trends[key].attrs["units"] = f"{ds_in[key].attrs['units']} / year"

    return trends


def plot_trend_start_sensitivity(trend_sens_output: xr.DataArray, **kwargs):
    import seaborn as sns
    from matplotlib import pyplot as plt

    da = trend_sens_output

    slopes = da.sel(parameter="slope").to_series().unstack()
    pvals = da.sel(parameter="pvalue").to_series().unstack()
    sig = (pvals < 0.05).astype(str).replace("True", "•").replace("False", "")

    # capitalize first letter of each word
    name = f"{da.attrs['long_name']}".title()
    unit = f"{da.attrs['units']}"
    method = da.attrs["method"].split("_")
    method_slope = method[0].capitalize()
    method_test = method[1].capitalize()

    cbar_name = f"{name} [{unit}]"
    ax_name = f"Season: {da.season.item().upper()}\n{name}\n{method_slope} slopes\n• significant with {method_test}"

    if "ax" not in kwargs:
        fig, ax = plt.subplots(figsize=[5.5, 4], dpi=150)

    props = dict(
        cmap="RdBu_r",
        center=0,
        annot=sig,
        fmt="",
        annot_kws=dict(fontsize=12, weight="bold"),
        square=True,
        linewidths=0.1,
        zorder=2,
        cbar_kws=dict(pad=0.02, label=cbar_name, location="left"),
    )
    ax = sns.heatmap(slopes, **(props | kwargs))

    # remove ticks by setting tick length to 0
    ax.xaxis.set_ticks_position("top")
    ax.xaxis.set_label_position("top")
    ax.yaxis.set_ticks_position("right")
    ax.yaxis.set_label_position("right")

    ax.set_ylabel("Start year")
    ax.set_xlabel("End year")

    ax.tick_params(axis="x", length=0, rotation=90)
    ax.tick_params(axis="y", length=0, rotation=0)

    ax.text(
        0,
        0,
        ax_name,
        weight=800,
        size="medium",
        ha="left",
        va="bottom",
        transform=ax.transAxes,
        fontdict=dict(family="monospace"),
    )

    fig = ax.get_figure()
    fig.tight_layout()

    return fig, ax


def add_slope_sig_as_param(ds):
    slope_sig = (
        ds.sel(parameter="slope")
        .where(ds.sel(parameter="pvalue") < 0.05)
        .expand_dims(parameter=["slope_sig005"])
    )
    ds = xr.concat([ds, slope_sig], dim="parameter")
    return ds


def era5_seasonal_trends_to_excel_ready_dataframe(
    ds, reorder_levels=["season", "variable", "parameter"]
):

    df = (
        ds.pipe(add_slope_sig_as_param)
        .to_dataframe()
        .rename_axis(columns="variable")
        .stack(future_stack=True)
        .reorder_levels(reorder_levels)
        .sort_index()
        .unstack("season")
    )

    if isinstance(ds, xr.Dataset):
        rename = {k: f"{ds[k].long_name} [{ds[k].units}]" for k in ds}
        df = df.rename(index=rename)

    return df
