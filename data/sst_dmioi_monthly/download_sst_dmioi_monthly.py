"""Download the DMI OI Arctic L4 daily SST from CMEMS and build monthly means.

Writes ``sst_dmioi_monthly.zarr`` next to this script: monthly means of
``analysed_st`` and ``analysis_error`` with days of sea-ice fraction >= 0.05
masked out, plus the monthly mean ``sea_ice_frac``. The daily subset is kept in
``raw/`` so reruns don't hit CMEMS again.

Credentials (``COPERNICUSMARINE_SERVICE_USERNAME`` / ``_PASSWORD``) come from
``.env`` via ``greenfjord.settings.get_env``.

Run from the repository root:

    .venv/bin/python data/sst_dmioi_monthly/download_sst_dmioi_monthly.py
"""

from __future__ import annotations

from pathlib import Path

import copernicusmarine as cm
import xarray as xr

from greenfjord.data.copernicusmarine import load_copernicusmarine_credentials

HERE = Path(__file__).resolve().parent
OUT = HERE / "sst_dmioi_monthly.zarr"
RAW_DIR = HERE / "raw"

DATASET_ID = "cmems_obs_si_arc_phy_my_L4-DMIOI_P1D-m"
VARIABLES = ["analysed_st", "analysis_error", "sea_ice_fraction"]
MINIMUM_LONGITUDE, MAXIMUM_LONGITUDE = -54.225, -35.775  # degrees east (0.05 deg grid centres)
MINIMUM_LATITUDE, MAXIMUM_LATITUDE = 58.0, 67.75  # degrees north
START_DATETIME = "1982-01-01T00:00:00"
END_DATETIME = "2025-12-31T00:00:00"
SEA_ICE_FRAC_THRESH = 0.05  # values on days with sea-ice fraction >= this are masked


def get_daily() -> Path:
    """Download the daily subset from CMEMS (skipped if already present)."""
    load_copernicusmarine_credentials()
    result = cm.subset(
        dataset_id=DATASET_ID,
        variables=VARIABLES,
        minimum_longitude=MINIMUM_LONGITUDE,
        maximum_longitude=MAXIMUM_LONGITUDE,
        minimum_latitude=MINIMUM_LATITUDE,
        maximum_latitude=MAXIMUM_LATITUDE,
        start_datetime=START_DATETIME,
        end_datetime=END_DATETIME,
        output_directory=RAW_DIR,
        file_format="zarr",
        skip_existing=True,
    )
    return result.file_path


def resample_to_monthly_mean(ds: xr.Dataset, sea_ice_frac_thresh: float) -> xr.Dataset:
    """Monthly means with high-sea-ice days masked (``sea_ice_frac`` is not masked)."""
    return (
        ds
        .where(ds.sea_ice_fraction < sea_ice_frac_thresh)
        .drop_vars("sea_ice_fraction")
        .assign(sea_ice_frac=ds.sea_ice_fraction)
        .resample(time="1MS")
        .mean()
        .chunk({"time": -1, "latitude": 100, "longitude": 100})
    )


def main() -> None:
    daily = xr.open_dataset(get_daily(), chunks={})
    resample_to_monthly_mean(daily, SEA_ICE_FRAC_THRESH).to_zarr(OUT, mode="w", zarr_format=2)


if __name__ == "__main__":
    main()
