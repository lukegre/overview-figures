from pathlib import Path

import dotenv

if not dotenv.load_dotenv():
    raise RuntimeError("Failed to load .env file. Please ensure it exists and is readable.")

ROOT = str(Path(dotenv.find_dotenv("pyproject.toml")).parent)

EPSG = 32623
EPSG_LATLON = 4326

BBOX_OCEAN = -52, 58, -40, 63
BBOX_ERA5 = BBOX_OCEAN  # -60, 55, -35, 70
BBOX_LAND = -48.21, 59.79, -44.32, 61.56

TIME_START = "1982-01-01"
TIME_END = "2021-12-31"

PATH_LOCAL_DATA = "data"

# save and load ERA5 data from this location on S3 bucket
FNAME_S3_ERA5 = (
    "simplecache::s3://spi-greenfjord-sdsc/atm/era5/era5-single_levels-monthly-1960_2024.zarr/"
)
FNAME_S3_GEBCO = "simplecache::s3://spi-greenfjord-sdsc/shared/bathymetry-GEBCO-2023.zarr/"
FNAME_S3_DIST2COAST = "simplecache::s3://spi-greenfjord-sdsc/shared/dist2coast_01deg_ocean.zarr/"
FNAME_AOI = f"{ROOT}/data/era5-land-ocean-ice.gpkg.zip"
