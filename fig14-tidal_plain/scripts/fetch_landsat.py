"""Fetch Landsat SWIR + RGB scenes for the tidal-plain dates.

Workflow (as requested):
  1. the user asks for a date (in ``config.yaml``);
  2. it is snapped to the nearest date present in the cleaned tidal-plain netCDF
     (so we only ever fetch scenes that have tidal-plain data);
  3. the matching Landsat scene is fetched from the Planetary Computer via the
     tools in ``stac.py`` (RGB for the land background + SWIR for the water).

Fetched scenes are reprojected onto the netCDF grid and cached as small netCDFs
in ``cache_dir`` so the plotting script can run offline afterwards.

NOTE ON SHIMS: the pinned ``stackstac`` (0.5.0) predates NumPy 2 / pandas 3, so
two tiny compatibility shims are installed before it is imported. They are
narrow wrappers and do not change behaviour for valid inputs.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

# --- stackstac 0.5.0 <-> NumPy 2 / pandas 3 compatibility shims ---------------
_orig_can_cast = np.can_cast


def _can_cast(from_, to, *a, **k):  # NEP-50: can_cast rejects python scalars
    if isinstance(from_, (int, float, complex)):
        from_ = np.min_scalar_type(from_)
    return _orig_can_cast(from_, to, *a, **k)


np.can_cast = _can_cast

_orig_to_datetime = pd.to_datetime


def _to_datetime(*a, **k):  # pandas 3 removed the infer_datetime_format kwarg
    k.pop("infer_datetime_format", None)
    return _orig_to_datetime(*a, **k)


pd.to_datetime = _to_datetime
# -----------------------------------------------------------------------------

import stac  # noqa: E402  (import after the shims are installed)

HERE = Path(__file__).parent
RGB_BANDS = ["red", "green", "blue"]


def nearest_tidal_plain_date(ds, requested_date):
    """Snap a requested date to the nearest scene in the tidal-plain netCDF."""
    times = pd.to_datetime(ds["time"].values)
    idx = int(np.argmin(np.abs(times - pd.Timestamp(requested_date))))
    return idx, times[idx]


def get_scene(ds, requested_date, bbox, cache_dir, max_cloud_cover=90):
    """Return (rgb, swir, scene_time) for the tidal-plain date nearest `requested_date`.

    `rgb` is a (y, x, 3) float array in [0, 1]-ish reflectance; `swir` is a
    (y, x) DataArray on the netCDF grid. Results are cached per scene date.
    """
    idx, scene_time = nearest_tidal_plain_date(ds, requested_date)
    cache_dir = HERE / cache_dir
    cache_dir.mkdir(exist_ok=True)
    cache_file = cache_dir / f"{scene_time.strftime('%Y-%m-%d')}.nc"

    if cache_file.exists():
        scene = xr.open_dataset(cache_file, engine="h5netcdf")
    else:
        scene = _fetch(ds, scene_time, bbox, max_cloud_cover)
        scene.to_netcdf(cache_file, engine="h5netcdf")

    rgb = scene[RGB_BANDS].to_array("band").transpose("y", "x", "band").values
    return rgb, scene["swir16"], scene_time, idx


def _fetch(ds, scene_time, bbox, max_cloud_cover):
    """Download the Landsat scene closest to `scene_time` and put it on the nc grid."""
    day = pd.Timestamp(scene_time).normalize()
    window = f"{(day - pd.Timedelta(days=1)).date()}/{(day + pd.Timedelta(days=1)).date()}"

    da = stac.get_landsat(
        tuple(bbox), window,
        assets=RGB_BANDS + ["swir16"],
        max_cloud_cover=max_cloud_cover,
    )
    # pick the acquisition closest to the tidal-plain scene time
    da = da.sel(time=pd.Timestamp(scene_time), method="nearest")
    # align to the exact netCDF grid
    da = da.reindex(x=ds.x, y=ds.y, method="nearest", tolerance=20)

    scene = xr.Dataset({b: da.sel(band=b, drop=True) for b in RGB_BANDS + ["swir16"]})
    # stackstac attaches non-serializable coords/attrs; keep only x/y and drop attrs
    scene = scene.drop_vars([c for c in scene.coords if c not in ("x", "y")],
                            errors="ignore")
    scene.attrs = {}
    for name in scene.variables:
        scene[name].attrs = {}
    return scene
