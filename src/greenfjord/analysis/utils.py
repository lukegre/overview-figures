import numpy as np
import pandas as pd
import xarray as xr


def compute_xy_gradient(da: xr.DataArray):
    x, y = np.gradient(da, axis=(1, 2))
    return xr.DataArray(np.hypot(x, y), coords=da.coords, dims=da.dims, name="gradient")


def _copy_xrattrs(func, copy_universal_to_all=False):
    from functools import wraps

    @wraps(func)
    def wrapper(*args, **kwargs):
        ds_in = args[0]
        ds_out = func(*args, **kwargs)

        if isinstance(ds_out, xr.Dataset):
            for key in ds_out.data_vars:
                attrs = ds_in[key].attrs
                if copy_universal_to_all:
                    attrs = {**ds_in.attrs, **attrs}
                ds_out[key] = ds_out[key].assign_attrs(attrs | ds_out[key].attrs)
        if isinstance(ds_out, xr.DataArray):
            new_attrs = ds_in.attrs | ds_out.attrs
            ds_out = ds_out.assign_attrs(new_attrs)

        return ds_out

    return wrapper


def to_excel(df: pd.DataFrame, path, unstack_dim=None, sheet_name=None, **writer_kwargs):
    import pathlib as pl

    import pandas as pd

    if unstack_dim is not None:
        df = df.unstack(unstack_dim)

    props = dict(mode="w")
    props.update(writer_kwargs)
    if pl.Path(path).exists():
        props["mode"] = "a"
        props["if_sheet_exists"] = "replace"

    with pd.ExcelWriter(path, **props) as writer:
        if sheet_name is None:
            sheet_name = "Sheet1"
        sheet_name_safe = sheet_name.replace("**", "^")
        df.to_excel(writer, sheet_name=sheet_name_safe)

    return df
