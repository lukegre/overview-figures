import sys as _sys

import geopandas as _gpd
from loguru import logger
from tqdm.dask import TqdmCallback

from . import analysis, config, data
from . import credentials as _credentials
from .loggers import get_loglevel

progressbar = TqdmCallback(desc="Xarray")
if not progressbar.active:
    progressbar.register()

_gpd.options.io_engine = "fiona"

logger.remove()
logger.add(_sys.stdout, level="DEBUG")
