import pathlib
import sys

import copernicusmarine as cm
import dotenv
import fire
import xarray as xr
from loguru import logger

from greenfjord import get_loglevel

LOGLEVEL = "DEBUG"
logger.remove()
logger.add(sys.stdout, level=LOGLEVEL)

HERE = pathlib.Path(__file__).parent.resolve()
REPO = pathlib.Path(dotenv.find_dotenv("pyproject.toml")).parent.resolve()
DATASETS = (
    {
        "dataset_id": "METOFFICE-GLO-SST-L4-REP-OBS-SST",
        "variables": ["analysed_sst", "analysis_error", "sea_ice_fraction"],
    },
    {
        "dataset_id": "cmems_obs_si_arc_phy_my_L4-DMIOI_P1D-m",
        "variables": ["analysed_st", "analysis_error", "sea_ice_fraction"],
    },
)

DEFAULT_QUERY = dict(
    minimum_longitude=-54.5,
    maximum_longitude=-35.5,
    minimum_latitude=58,
    maximum_latitude=67.5,
    start_datetime="1982-01-01T00:00:00",
    end_datetime="2024-12-31T00:00:00",
    output_directory=HERE,
    skip_existing=True,
    file_format="zarr",
)


def main(datasets: tuple = DATASETS) -> None:
    """Download the sea surface temperature dataset."""
    for dataset in datasets:
        query = DEFAULT_QUERY.copy()
        query.update(**dataset)
        get_monthly(query)


def get_monthly(query: dict) -> None:
    """Download the sea surface temperature dataset."""
    fname = get_cmems_data(query)
    logger.info(f"Dataset path: {fname}")

    ds = xr.open_dataset(fname, chunks={})
    logger.debug(f"Dataset info: {ds}")

    ds_monthly = resample_to_monthly_mean(ds, sea_ice_frac_thresh=0.05)

    fname_monthly = fname.with_suffix(".monthly.zarr")
    ds_monthly.to_zarr(fname_monthly, mode="w", zarr_format=2)


def get_cmems_data(query: dict) -> pathlib.PosixPath:
    import logging

    # for the dry run, disable the logger
    logging.getLogger("copernicusmarine").disabled = True
    dry_run_query = query.copy()
    dry_run_query.pop("variables", None)

    dry_run_result = cm.subset(dry_run=True, **dry_run_query)
    if (get_loglevel(logger) <= 10) and (dry_run_result.file_status != "DOWNLOADED"):
        logger.debug(f"CMEMS subset result: {dry_run_result}")

    logging.getLogger("copernicusmarine").disabled = False
    query = query.copy()
    logger.debug(f"CMEMS query: {query}")
    result = cm.subset(**query)
    return result.file_path


def resample_to_monthly_mean(ds: xr.Dataset, sea_ice_frac_thresh: float) -> xr.Dataset:
    """Resample the dataset to monthly mean."""
    return (
        ds
        .where(ds.sea_ice_fraction < sea_ice_frac_thresh)
        .drop_vars("sea_ice_fraction")
        .assign(sea_ice_frac=ds.sea_ice_fraction)
        .resample(time="1MS")
        .mean()
        .chunk({"time": -1, "latitude": 100, "longitude": 100})
    )


if __name__ == "__main__":
    fire.Fire(main)
