import pathlib as _pathlib
import dotenv as _dotenv
from .. import logger

BBOX_WSEN = (-60, 55, -35, 65)
# S3 name does not automatically update the bbox, so check this with the BBOX given above
S3_FNAME = 's3://spi-greenfjord-sdsc/ocean/ocean_color/chl-phenology-OCCCIv6-{res_km:d}KM-nicolson2024_fmt.zarr'

BASE_DIR = _pathlib.Path(_dotenv.find_dotenv()).parent


def main(res_km=4, to_zarr=True):
    import fsspec
    import xarray as xr

    s3_fname = S3_FNAME.format(res_km=res_km)
    fs = fsspec.filesystem('s3')
    if fs.exists(s3_fname):
        logger.info(f"File already exists: {s3_fname}")
        return xr.open_zarr(s3_fname)
    else:
        logger.info(f"Downloading data and saving to {s3_fname}")
        fname = download_chl_phenology(res_km)
        ds = xr.open_mfdataset(fname, preprocess=process_netcdf).compute()
        if to_zarr:
            ds.to_zarr(S3_FNAME.format(res_km=res_km), mode='w')
        return  ds


def download_chl_phenology(res_km=25, tmp_dir=BASE_DIR / 'data/tmp/'):
    import pooch

    url = get_nicholson_url(res_km)

    fname = pooch.retrieve(
        url=url,
        known_hash=None,
        fname=f'OCCCIv6_{res_km}KM_PHENOLOGY_CHLOR_A.nc',
        path=tmp_dir,
        progressbar=True)
    
    return fname


def process_netcdf(ds):
    import xarray as xr
    import rioxarray

    w, s, e, n = BBOX_WSEN

    logger.debug(f"Subsetting data to the bounding box: {BBOX_WSEN}")
    lat_slice = slice(s, n) if ds.lat[0] < ds.lat[-1] else slice(n, s)
    ds = ds.sel(lat=lat_slice, lon=slice(w, e)).rio.write_crs(4326)

    logger.debug("Converting datetime to dayofyear, and timedelta to days")
    for key in ds:
        da = ds[key]
        if da.dtype == 'datetime64[ns]':
            ds[key] = da.dt.dayofyear.astype('float32')
        elif da.dtype == 'timedelta64[ns]':
            ds[key] = da.dt.days.astype('float32')
    
    variables = ['duration', 'initiation', 'int_chl', 'mean_chl', 'termination']
    methods = ['cs', 'rc', 'ts']

    ds_out = xr.Dataset()
    list_of_vars = set(list(ds.data_vars))
    for key in variables:
        da_methods = []
        for mthd in methods:
            name = key + '_' + mthd
            da_methods += ds[name].expand_dims(method=[mthd]),
            list_of_vars -= set([name])
        ds_out[key] = xr.concat(da_methods, dim='method')

    for key in list_of_vars:
        ds_out[key] = ds[key]

    logger.debug("Setting the crs to EPSG:4326")
    ds_out = ds_out.rio.write_crs('EPSG:4326')

    return ds_out


def get_nicholson_url(res_km=25):
    if res_km == 25:
        url = "https://zenodo.org/records/8402823/files/OCCCIv6_25KM_PHENOLOGY_CHLOR_A.nc?download=1"
    elif res_km == 9:
        url = "https://zenodo.org/records/8402847/files/OCCCIv6_9KM_PHENOLOGY_CHLOR_A.nc?download=1"
    elif res_km == 4:
        url = "https://zenodo.org/records/8402932/files/OCCCIv6_4KM_PHENOLOGY_CHLOR_A.nc?download=1"

    return url


if __name__ == '__main__':
    main()
