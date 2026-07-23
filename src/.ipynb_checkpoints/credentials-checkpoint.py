import dotenv as _dotenv
from pathlib import Path as _path
import copernicusmarine as _copernicusmarine
from loguru import logger


_dotenv_loaded = _dotenv.load_dotenv()
if _dotenv_loaded:
    _dotenv_fname = _dotenv.find_dotenv()
    keys = _dotenv.dotenv_values(_dotenv_fname)
    logger.info(f"Loaded .env file: {_dotenv_fname}")

_credentials_path = _path("~/.copernicusmarine/.copernicusmarine-credentials")
if not _credentials_path.expanduser().exists():
    logger.info(f"Logging into Copernicus Marine (only once, credentials are stored in {_credentials_path})")
    
    _copernicusmarine.login(
        username=keys.get("COPERNICUSMARINE_USERNAME", None),
        password=keys.get("COPERNICUSMARINE_PASSWORD", None))