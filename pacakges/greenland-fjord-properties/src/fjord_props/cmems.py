import pathlib
import tempfile
import warnings
from typing import Callable

import copernicusmarine
import dask.array.core
import fsspec
import numpy as np
import pandas as pd
import rioxarray  # noqa: F401
import xarray as xr
from loguru import logger

from fjord_props import cfg


def get_file_list(dataset_id: str) -> list[str]:
    fname = f"full_list-{dataset_id}.txt"

    if not pathlib.Path(fname).exists():
        copernicusmarine.get(dataset_id=dataset_id, create_file_list=fname, overwrite=True)

    flist = open(fname).read().splitlines()
    return flist


def filter_file_list(flist: list[str], map_grids: list[str]) -> list[str]:
    filtered_list = []
    for f in flist:
        if any(mg in f for mg in map_grids):
            filtered_list.append(f)
    return filtered_list


def download_single_copernicusmarine_ncfile(
    dataset_id: str, s3url: str, output_dir: str, nc_processor: Callable | None = None, **kwargs
) -> pathlib.Path:
    local_output = pathlib.Path(output_dir)  # type: ignore
    final_name = local_output / pathlib.Path(s3url).name

    if final_name.exists():
        logger.info(f"File {final_name} already exists, skipping download.")
        return final_name

    with tempfile.TemporaryDirectory() as tmpdir, warnings.catch_warnings():
        warnings.simplefilter("ignore", category=RuntimeWarning)

        tmpdir = pathlib.Path(tmpdir)
        temp_filelist_name = tmpdir / "filelist.txt"
        temp_filelist_name.write_text(s3url + "\n")

        props = (
            dict(
                dataset_id=dataset_id,
                file_list=temp_filelist_name,
                overwrite=True,
                disable_progress_bar=True,
                no_directories=True,
                output_directory=tmpdir,
            )
            | kwargs
        )
        response = copernicusmarine.get(**props)  # type: ignore

        temp_fname = pathlib.Path(response.files[0].file_path)

        if nc_processor is not None:
            write_nc_to_same_path_after_processing(temp_fname, nc_processor)

        new_name = local_output / temp_fname.name
        assert new_name == final_name
        temp_fname.rename(new_name)

    assert not tmpdir.exists()

    return new_name


def write_nc_to_same_path_after_processing(fname_nc: pathlib.Path, nc_processor: Callable):
    fname_tmp = fname_nc.with_name("tmp")
    fname_nc.rename(fname_tmp)
    ds = xr.open_dataset(fname_tmp, chunks={})
    ds = nc_processor(ds)
    ds.to_netcdf(fname_nc, engine="h5netcdf", encoding={k: dict(zlib=True, complevel=4) for k in ds})


def create_zarr_template(
    dataset_id: str,
    template_flist: list[str],
    fname_zarr: str | pathlib.Path,
    dates: pd.DatetimeIndex,
    nc_processor: Callable | None = None,
    overwrite: bool = False,
):
    fs, url = fsspec.url_to_fs(str(fname_zarr))
    if fs.exists(url) and not overwrite:
        logger.debug(f"Zarr file {fname_zarr} already exists, skipping template creation.")
        return

    flist = tuple()
    for f in template_flist:
        f = download_single_copernicusmarine_ncfile(dataset_id, f, str(cfg.CACHE_DIR), nc_processor=nc_processor)
        flist += (f.rename(f.with_stem(f.stem + "_full")),)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=dask.array.core.PerformanceWarning)

        ds = _make_template(flist)

        for t in dates:
            ds.time.values[:] = t
            logger.info(f"Processing time {t:%Y-%m-%d}")

            props = {"mode": "w"} if t == dates[0] else {"mode": "a", "append_dim": "time"}
            ds.to_zarr(fname_zarr, write_empty_chunks=False, zarr_format=2, **props)  # type: ignore


def _make_template(flist: tuple[pathlib.Path, ...] | list[pathlib.Path]) -> xr.Dataset:
    ds = xr.open_mfdataset(flist, combine="by_coords", data_vars="all", join="outer")
    ds = ds.rio.write_crs(ds.spatial_ref.crs_wkt)
    ds = ds.drop_vars(["lat", "lon"], errors="ignore")
    fill_values = {v: np.nan for v in ds.data_vars if v not in ["time", "x", "y", "data_written"]}

    if "data_written" in ds.data_vars:
        fill_values["data_written"] = False

    ds = xr.full_like(ds, fill_value=fill_values).compute().chunk({"time": 1, "y": 500, "x": 500}).persist()
    return ds
