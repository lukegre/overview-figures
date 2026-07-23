import fsspec
import pathlib
import click
import pandas as pd
import xarray as xr
from loguru import logger
from typing import Union

URL = (
    "filecache::https://d1qb6yzwaaq4he.cloudfront.net/airpollution/absaai/"
    "{product}/daily/data/{t:%Y}/ESACCI-AEROSOL-L3-AAI-{product}-1D-{t:%Y%m%d}-fv1.9.nc"
)


@click.command()
@click.argument("time_start")
@click.argument("time_end")
@click.option("--path", default="../data", help="Destination path for downloaded data")
def cli(time_start: str, time_end: str, path: str):
    """
    Download GOME2A AAI data for a given time range.
    Requires a start and end date in the format 'YYYY-MM-DD'.
    """
    product = "GOME2B"
    download_aai(product, time_start, time_end, path, download_batch_size="30D")


def main(time_start: str, time_end: str):
    product = "GOME2B"
    download_aai(
        product, time_start, time_end, f"../data/{product}", download_batch_size="30D"
    )


def download_aai(
    product: str,
    date_start: Union[pd.Timestamp, str],
    date_end: Union[pd.Timestamp, str],
    dest_path: str,
    download_batch_size: str = "30D",
) -> tuple[str, ...]:
    
    if isinstance(date_start, str):
        date_start = pd.Timestamp(date_start)
    if isinstance(date_end, str):
        date_end = pd.Timestamp(date_end)

    assert isinstance(dest_path, str), "dest_path must be a string"

    flist = ()
    for t0 in pd.date_range(date_start, date_end, freq=download_batch_size):
        t1 = min(t0 + pd.Timedelta(download_batch_size), date_end)
        batch_dates = pd.date_range(t0, t1, freq="D")
        flist += _download_aai_batch(product, batch_dates, dest_path)

    return flist


def _download_aai_batch(
    product: str,
    date: Union[pd.DatetimeIndex, list[pd.Timestamp], pd.Timestamp],
    dest_path: Union[str, pathlib.Path],
) -> tuple[str, ...]:
    if isinstance(date, pd.DatetimeIndex):
        urls = [URL.format(product=product, t=t) for t in date]
    elif isinstance(date, list):
        assert all(isinstance(t, pd.Timestamp) for t in date)
        urls = [URL.format(product=product, t=t) for t in date]
    elif isinstance(date, pd.Timestamp):
        urls = [URL.format(product=product, t=date)]
    else:
        raise ValueError(
            "date must be a pd.DatetimeIndex, list of pd.Timestamp or pd.Timestamp"
        )

    # fnames = _download_urls_with_pooch(urls, dest_path)
    fnames = _download_urls_with_fsspec(urls, dest_path)
    return tuple(fnames)


def _download_urls_with_pooch(urls, dest_path):
    """fallback option"""
    import pooch

    flist = ()
    for url in urls:
        try:
            fname = url.split("/")[-1]
            flist += (
                pooch.retrieve(url, known_hash=None, fname=fname, path=dest_path),
            )
        except Exception:
            logger.warning(f"Failed to download {url}")
            continue

    return flist


def _download_urls_with_fsspec(urls, dest_path):
    from aiohttp.client_exceptions import ClientResponseError

    storage_options = {
        "same_names": True,
        "cache_storage": dest_path,
        "http": {
            "headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.61 Safari/537.36"
            }
        },
    }

    try:
        fsspec.open_local(urls, **storage_options)
    except ClientResponseError:
        for url in urls:
            try:
                fsspec.open_local(url, **storage_options)
            except ClientResponseError:
                logger.warning(f"Failed to download {url}")
                continue

    fnames = [f"{dest_path}/{url.split('/')[-1]}" for url in urls]
    return fnames


def combine_nc_to_zarr(
    fname_glob: str, fname: Union[str, pathlib.Path]
) -> xr.Dataset:
    from tqdm.dask import TqdmCallback

    def time_from_fname(ds: xr.Dataset) -> xr.Dataset:
        import pandas as pd
        import re

        fname = ds.encoding["source"]
        match = re.search(r"20[0-3][0-9][01][0-9][0-3][0-9]", fname)

        if match:
            time = pd.to_datetime(match.group(0), format="%Y%m%d")
            ds = ds.assign_coords(time=[time])

        ds = ds.rename({"latitude": "lat", "longitude": "lon"}).transpose(
            "time", "lat", "lon"
        )

        return ds

    fname = pathlib.Path(fname)

    if not fname.exists():
        with TqdmCallback():
            ds = xr.open_mfdataset(
                fname_glob,
                combine="by_coords",
                preprocess=time_from_fname,
                parallel=True,
                chunks={},
            ).compute()
            ds.to_zarr(fname)
    else:
        ds = xr.open_zarr(fname)

    return ds


if __name__ == "__main__":
    cli()
