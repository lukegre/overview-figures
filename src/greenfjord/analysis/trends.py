import numpy as np
import scipy.stats
import xarray as xr

from .utils import _copy_xrattrs


@_copy_xrattrs
def theilsen_mannkendall(
    x: xr.Dataset,
    y: xr.Dataset | None = None,
    dim="time",
    alpha=0.95,
    nan_policy="propagate",
    variant="c",
    kendaltau_method="auto",
):
    """Compute the Theil-Sen estimator and Mann-Kendall test for monotonic trends.

    Args:
        x (xarray object): Independent variable.
        y (xarray object, optional): Dependent variable. If None, y = x, and x = x[dim]
        dim (str, optional): Dimension to apply the Theil-Sen estimator and Mann-Kendall test over.
        alpha (float, optional): Confidence level for the Theil-Sen estimator. Defaults to 0.95.
        nan_policy (str, optional): Policy to use when handling nans. Defaults to 'propagate'.

            * 'none', 'propagate': If a NaN exists anywhere on the given dimension, return nans for that whole dimension.
            * 'raise': If a NaN exists at all in the datasets, raise an error.
            * 'omit', 'drop': If a NaN exists in `x` or `y`, drop that index and compute the slope without it.

        variant (str, optional): The method used to compute the Kendall tau. Defaults to 'c'.
        kendaltau_method (str, optional): The method used to compute the p-value of the Kendall tau. Defaults to 'auto'.

    Returns:
        xarray object: Slope, intercept, p-value, Kendall tau, upper bound of the slope, and lower bound of the slope.
        These 6 parameters are added as a new dimension "parameter".
    """
    from scipy.stats import kendalltau, theilslopes

    def mannkendall_wrapper(x, y):
        x, y = _handle_nans(x, y, nan_policy)

        if (nan_policy in ["omit", "drop"]) and (x.size == 0):
            return np.full(5, np.nan)

        slope, intercept, upper, lower = theilslopes(y, x, alpha=alpha)
        tau, pvalue = kendalltau(x, y, variant=variant, method=kendaltau_method)

        return np.array([slope, intercept, pvalue, tau, upper, lower])

    assert dim in x.dims, f"Dimension {dim} not found in DataArray"

    if y is None:
        Y = x
        X = x[dim]
    else:
        X = x
        Y = y

    parameters = "slope intercept pvalue tau slope_upper_bound slope_lower_bound".split()
    attrs = dict(
        method="theilsen_mannkendall",
        alpha=alpha,
        nan_policy=nan_policy,
        variant=variant,
        kendaltau_method=kendaltau_method,
        **x.attrs,
        **y.attrs if y is not None else {},
    )

    results = xr.apply_ufunc(
        mannkendall_wrapper,
        X,
        Y,
        input_core_dims=[[dim], [dim]],
        output_core_dims=[["parameter"]],
        vectorize=True,
        dask_gufunc_kwargs=dict(output_sizes={"parameter": len(parameters)}),
        dask="parallelized",
        output_dtypes=["float64"],
    )

    results = (
        results.assign_coords(parameter=parameters)
        .assign_attrs(**attrs)
        .transpose("parameter", ...)
    )

    return results


@_copy_xrattrs
def linregress_pearson(x: xr.Dataset, y: xr.Dataset = None, dim="time", nan_policy="propagate"):
    """From https://github.com/bradyrx/esmtools
    Vectorized applciation of ``scipy.stats.linregress``.

    .. note::

        This function will try to infer the time freqency of sampling if ``x`` is in
        datetime units. The final slope and standard error will be returned in the
        original units per that frequency (e.g. SST per year). If the frequency
        cannot be inferred (e.g. because the sampling is irregular), it will return in
        the original units per day (e.g. SST per day).

    Args:
        x (xarray object): Independent variable (predictor) for linear regression.
            If ``y`` is ``None``, treat ``x`` as the dependent variable and remove
            slope over ``dim``.
        y (xarray object, optional): Dependent variable (predictand) for linear
            regression. If ``None``, treat ``x`` as the predictand.
        dim (str, optional): Dimension to apply linear regression over.
            Defaults to "time".
        nan_policy (str, optional): Policy to use when handling nans. Defaults to
            "none".

            * 'none', 'propagate': If a NaN exists anywhere on the given dimension,
                return nans for that whole dimension.
            * 'raise': If a NaN exists at all in the datasets, raise an error.
            * 'omit', 'drop': If a NaN exists in `x` or `y`, drop that index and
                compute the slope without it.

    Returns:
        xarray object: Slope, intercept, correlation, p value, and standard error for
            the linear regression. These 5 parameters are added as a new dimension
            "parameter".

    """
    import warnings

    def _linregress(x, y, nan_policy):
        x, y = _handle_nans(x, y, nan_policy)
        # This catches cases where a given grid cell is full of nans, like in
        # land masking.
        if (nan_policy in ["omit", "drop"]) and (x.size == 0):
            return np.full(5, np.nan)
        else:
            m, b, r, p, e = scipy.stats.linregress(x, y)
            # Multiply slope and standard error by factor. If time indices were
            # converted to numeric units, this gets them back to the original units.
            return np.array([m, b, r, p, e])

    if y is None:
        Y = x
        X = x[dim]
    else:
        X = x
        Y = y

    parameters = "slope intercept rvalue pvalue stderr".split()

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=FutureWarning)
        results = xr.apply_ufunc(
            _linregress,
            X,
            Y,
            nan_policy,
            vectorize=True,
            dask="parallelized",
            input_core_dims=[[dim], [dim], []],
            output_core_dims=[["parameter"]],
            output_dtypes=["float64"],
            output_sizes={"parameter": 5},
        )

    results = (
        results.assign_coords(parameter=parameters)
        .assign_attrs(nan_policy=nan_policy, method="linregress_pearson")
        .transpose("parameter", ...)
    )

    return results


def _handle_nans(x, y, nan_policy):
    """From https://github.com/bradyrx/esmtools
    Modifies `x` and `y` based on `nan_policy`.

    Args:
        x, y (xr.DataArray or ndarrays): Two time series to which statistical function
            is being applied.
        nan_policy (str): One of ['none', 'propagate', 'raise', 'omit', 'drop']. If
            'none' or 'propagate', return unmodified so the nans can be propagated
            through in the functions. If 'raise', raises a warning if there are any
            nans in `x` or `y`. If 'omit' or 'drop', removes values that contain
            a nan in either `x` or `y` and returns resulting `x` and `y`.

    Returns:
        x, y (xr.DataArray or ndarrays): Modified `x` and `y` datasets.

    Raises:
        ValueError: If `nan_policy` is 'raise' and there are nans in either `x` or `y`;
            if `nan_policy` is not one of ['none', 'propagate', 'raise', 'omit',
            'drop']; or if `x` or `y` are larger than 1-dimensional.
    """

    # Only support 1D, since we are doing `~np.isnan()` indexing for 'omit'/'drop'.
    if (x.ndim > 1) or (y.ndim > 1):
        raise ValueError(f"x and y must be 1-dimensional. Got {x.ndim} for x and {y.ndim} for y.")

    if nan_policy in ["none", "propagate"]:
        return x, y
    elif nan_policy == "raise":
        if has_missing(x) or has_missing(y):
            raise ValueError(
                "Input data contains NaNs. Consider changing `nan_policy` to 'none' "
                "or 'omit'. Or get rid of those NaNs somehow."
            )
        else:
            return x, y
    elif nan_policy in ["omit", "drop"]:
        if has_missing(x) or has_missing(y):
            x_mod, y_mod = match_nans(x, y)
            # The above function pairwise-matches nans. Now we remove them so that we
            # can compute the statistic without the nans.
            x_mod = x_mod[np.isfinite(x_mod)]
            y_mod = y_mod[np.isfinite(y_mod)]
            return x_mod, y_mod
        else:
            return x, y
    else:
        raise ValueError(f"{nan_policy} not one of ['none', 'propagate', 'raise', 'omit', 'drop']")


def has_missing(data):
    """From https://github.com/bradyrx/esmtools
    Returns ``True`` if any NaNs in ``data`` and ``False`` otherwise.

    Args:
        data (ndarray or xarray object): Array to check for missing data.
    """
    return np.isnan(data).any()


def match_nans(x, y):
    """From https://github.com/bradyrx/esmtools
    Performs pairwise matching of nans between ``x`` and ``y``.

    Args:
        x, y (ndarray or xarray object): Array-like objects to pairwise match nans over.

    Returns:
        x, y (ndarray or xarray object): If either ``x`` or ``y`` has missing data,
            adds nans in the same places between the two arrays.
    """
    if has_missing(x) or has_missing(y):
        # Need to copy to avoid mutating original objects and to avoid writeable errors
        # with ``xr.apply_ufunc`` with vectorize turned on.
        x, y = x.copy(), y.copy()
        idx = np.logical_or(np.isnan(x), np.isnan(y))
        # NaNs cannot be added to `int` arrays.
        if x.dtype == "int":
            x = x.astype("float")
        if y.dtype == "int":
            y = y.astype("float")
        x[idx], y[idx] = np.nan, np.nan
    return x, y


def has_dims(xobj, dims, kind):
    """From https://github.com/bradyrx/esmtools
    Checks that at the minimum, the object has provided dimensions.

    Args:
        xobj (xarray object): Dataset or DataArray to check dimensions on.
        dims (list or str): Dimensions being checked.
        kind (str): String to precede "object" in the error message.
    """
    if isinstance(dims, str):
        dims = [dims]

    if not all(dim in xobj.dims for dim in dims):
        raise ValueError(
            f"Your {kind} object must contain the following dimensions at the minimum: {dims}"
        )
    return True


def calc_linear_trend(da: xr.DataArray, dim="time", deg=1):
    """
    Calculate the linear trend of a DataArray along a given dimension.

    Args:
        da (xarray object): DataArray to calculate trend on.
        dim (str): Dimension to calculate trend along.
        deg (int): Degree of polynomial to fit. Default is 1 (linear).

    Returns:
        xarray object: Linear trend of the DataArray along dim, with the same shape as da.
    """

    polyres = da.polyfit(dim=dim, deg=deg)
    coefs = polyres[list(polyres.data_vars)[0]]

    x = da[dim]

    trend = xr.polyval(x, coefs)

    return trend


def detrend(da: xr.DataArray, dim="time", deg=1):
    """
    Detrend a DataArray along a given dimension.

    Args:
        da (xarray object): DataArray to detrend.
        dim (str): Dimension to detrend along.
        deg (int): Degree of polynomial to fit. Default is 1 (linear).

    Returns:
        xarray object: Detrended DataArray.
    """

    trend = calc_linear_trend(da, dim=dim, deg=deg)

    detrended = da - trend

    return detrended


def get_significant_slope(trend_output, threshold=0.05):
    pvalue = trend_output.sel(parameter="pvalue", drop=True)
    slope = trend_output.sel(parameter="slope", drop=True)

    slope_significant = slope.where(pvalue < threshold)

    return slope_significant
