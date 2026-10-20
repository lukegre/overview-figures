"""Download ERA5 monthly means for the south Greenland region from CDS.

Writes ``era5_monthly_south_greenland.nc`` next to this script: monthly
averaged reanalysis, 1982-2025, on the 0.25 deg grid, for the area
55-70 N, 80-30 W.

Credentials: ``cdsapi`` reads ``CDSAPI_URL`` / ``CDSAPI_KEY``, which
``greenfjord.settings`` loads from ``.env`` on import, and otherwise
``~/.cdsapirc``.

Run from the repository root:

    .venv/bin/python data/era5_monthly_south_greenland/download_era5_monthly_south_greenland.py
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import cdsapi
import numpy as np
import xarray as xr
from loguru import logger

from greenfjord import settings  # noqa: F401 - loads .env (CDS credentials)

HERE = Path(__file__).resolve().parent
OUT = HERE / "era5_monthly-greenfjord-55S_70N_80W_30W-1982_2025.nc"

DATASET = "reanalysis-era5-single-levels-monthly-means"
START_YEAR = 1982
END_YEAR = 2025
AREA_NESW = [70, -80, 55, -30]  # north, west, south, east (degrees)
VARIABLES = [
    "2m_dewpoint_temperature",
    "2m_temperature",
    "mean_sea_level_pressure",
    "surface_pressure",
    "total_precipitation",
    "10m_wind_speed",
    "instantaneous_10m_wind_gust",
    "cloud_base_height",
    "total_cloud_cover",
    "low_cloud_cover",
    "high_cloud_cover",
    "medium_cloud_cover",
]
CHUNK_YEARS = 5
MAX_CONCURRENT = 2  # CDS rate limit
REQUEST = {
    "product_type": ["monthly_averaged_reanalysis"],
    "variable": VARIABLES,
    "month": [f"{m:02d}" for m in range(1, 13)],
    "time": ["00:00"],
    "area": AREA_NESW,
    "data_format": "netcdf",
    "download_format": "unarchived",
}


def year_chunks(start: int = START_YEAR, end: int = END_YEAR, size: int = CHUNK_YEARS):
    """Split start-end into blocks aligned to 5-year boundaries (1982-1985, 1986-1990, ...)."""
    chunks = []
    first = start
    while first <= end:
        last = min(end, (first - 1) // size * size + size)
        chunks.append((first, last))
        first = last + 1
    return chunks


def _chunk_fname(output_fname: Path, first: int, last: int) -> Path:
    return output_fname.with_name(f"{output_fname.stem}-chunk_{first}_{last}.nc")


def _download_chunk(first: int, last: int, output_fname: Path) -> Path:
    """Retrieve a single chunk of years (one CDS request)."""
    target = _chunk_fname(output_fname, first, last)
    request = {**REQUEST, "year": [str(y) for y in range(first, last + 1)]}
    logger.info(f"Requesting {first}-{last} -> {target.name}")
    cdsapi.Client().retrieve(DATASET, request, target=str(target))
    return target


def download(output_fname: Path = OUT, dry_run: bool = False, keep_chunks: bool = False) -> None:
    """Download ERA5 monthly means in 5-year chunks (MAX_CONCURRENT at a time), then combine."""
    chunks = year_chunks()
    if dry_run:
        logger.info(f"Would download {DATASET} in chunks {chunks} with request:\n{REQUEST}")
        return

    # each retrieve() blocks while CDS processes it, so threads run requests concurrently
    with ThreadPoolExecutor(max_workers=MAX_CONCURRENT) as pool:
        futures = [pool.submit(_download_chunk, first, last, output_fname) for first, last in chunks]
        fnames = [f.result() for f in futures]

    ds = xr.open_mfdataset(fnames, combine="nested", concat_dim="valid_time").sortby("valid_time")
    ds.load().to_netcdf(output_fname)
    ds.close()
    if not keep_chunks:
        for f in fnames:
            f.unlink()
    logger.info(f"Wrote {output_fname}")


def merge(input_fnames: list[str], output_fname: str, dry_run: bool = False):
    """Merge ERA5 monthly means into a single file."""
    logger.info(f"Merging {len(input_fnames)} files into {output_fname}")

    ds_list = [xr.open_dataset(f) for f in input_fnames]
    ds0 = ds_list[0]

    # first, check that all datasets have the same shape, coordinates, and coordinate values
    same_shape = all(ds0[key].shape == ds[key].shape for ds in ds_list[1:] for key in ds0.coords)
    if not same_shape:
        raise ValueError("Input files do not have the same shape")

    # same names and dtypes for all coords
    same_coords = all(
        ds0.coords.keys() == ds.coords.keys()
        and all(ds0[coord].dtype == ds[coord].dtype for coord in ds0.coords)
        for ds in ds_list[1:]
    )
    if not same_coords:
        raise ValueError("Input files do not have the same coordinates")

    # check that coordinates (at a dataset level) are within a tolerance of 5% of the grid spacing
    grid_spacing = lambda c: abs(np.diff(c.values).mean())
    for coord in ds0.dims:
        spacing = grid_spacing(ds0[coord])
        for ds in ds_list[1:]:
            dist = np.array(np.abs(ds0[coord] - ds[coord]))
            if not np.all(dist < (0.05 * spacing)):
                raise ValueError(
                    f"Coordinate {coord} is not within tolerance: {dist.max()} > {0.05 * spacing}"
                )

    # assign the coordinates of the first dataset to all others, then merge
    coords = ds0.coords
    new_ds = [ds0]
    for ds in ds_list[1:]:
        for coord in coords:
            ds = ds.assign_coords({coord: coords[coord]})
        new_ds.append(ds)

    merged = xr.merge(new_ds, compat="override")

    if not dry_run:
        merged.to_netcdf(output_fname)
    else:
        logger.info(f"Would merge to {output_fname}:\n{merged}")


def main() -> None:
    download()


if __name__ == "__main__":
    main()
