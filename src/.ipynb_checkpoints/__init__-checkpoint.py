import geopandas as _gpd
import dotenv as _dotenv
import copernicusmarine as _copernicusmarine

_gpd.options.io_engine = "fiona"

_dotenv.load_dotenv()
_copernicusmarine.login(
    username=_dotenv.os.getenv("COPERNICUS_USERNAME"),
    password=_dotenv.os.getenv("COPERNICUS_PASSWORD"))