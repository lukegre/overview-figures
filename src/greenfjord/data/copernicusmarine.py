import dotenv as _dotenv
from pathlib import Path as _path
import copernicusmarine as _copernicusmarine
from loguru import logger
from functools import lru_cache


def load_copernicusmarine_credentials():

    _dotenv_loaded = _dotenv.load_dotenv()
    if _dotenv_loaded:
        _dotenv_fname = _dotenv.find_dotenv()
        keys = _dotenv.dotenv_values(_dotenv_fname)
        logger.bind(class_name='CREDS').info(f"Loaded .env file: {_dotenv_fname}")

    _credentials_path = _path("~/.copernicusmarine/.copernicusmarine-credentials")
    if not _credentials_path.expanduser().exists():
        logger.bind(class_name='CREDS').info(f"Logging into Copernicus Marine (only once, credentials are stored in {_credentials_path})")
        
        _copernicusmarine.login()
    

def set_logger_level(level="WARNING"):

    logger_name = 'copernicus_marine_root_logger'
    _copernicusmarine.logging.getLogger(logger_name).setLevel(level)


@lru_cache(1)
def get_product_list():

    products = _copernicusmarine.describe(include_datasets=True)['products']

    return products


def get_product_and_dataset(dataset_id):

    products = get_product_list()

    for p in products:
        for d in p['datasets']:
            if d['dataset_id'] == dataset_id:
                return p, d


def get_dataset_info(dataset_id, service_name='arco-geo-series'):

    product, dataset = get_product_and_dataset(dataset_id)
    product_id = product['product_id']
    dataset_id = dataset['dataset_id']

    zarr_url = get_zarr_url_from_dataset_info(dataset, service_name=service_name)

    return product_id, dataset_id, zarr_url


def get_zarr_url_from_dataset_info(dataset_info, part_index=0, service_name='arco-geo-series'):
    for v in dataset_info['versions']:
        p = v['parts'][part_index]
        for s in p['services']:
            st = s['service_type']
            if st['service_name'] == service_name:
                return s['uri']
            
