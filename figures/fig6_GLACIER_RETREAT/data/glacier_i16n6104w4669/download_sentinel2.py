"""Build the true-colour Sentinel-2 scene used as backdrop of panel (b) of fig6-glacier_retreat.

Median composite of the cloud-filtered Sentinel-2 L2A scenes of one month from the
Microsoft Planetary Computer, scaled to reflectance, clipped to [0, 1] and
histogram-equalised for display contrast. Writes
``glacier_i16n6104w4669_sentinel2-truecolor-2024-08.tif`` next to this script
(red/green/blue bands, EPSG:32623, 10 m). Needs network and ``scikit-image``.

Run from the repository root:

    .venv/bin/python fig6-glacier_retreat/data/glacier_i16n6104w4669/download_sentinel2.py
"""

from pathlib import Path

import planetary_computer
import pystac_client
import rioxarray  # noqa: F401  (registers the .rio accessor)
import stackstac
import xarray as xr
from skimage import exposure

OUT_TIF = Path(__file__).resolve().parent / "glacier_i16n6104w4669_sentinel2-truecolor-2024-08.tif"

# bbox of the glacier fronts (1973-2023) padded by (0, -0.04, 0, +0.03) degrees: west, south, east, north
BBOX = (-46.79913481993752, 60.95978014331399, -46.588405397023166, 61.098296972006196)  # degrees
YEAR, MONTH = 2024, 8  # acquisition year and month
MAX_CLOUD = 10  # scenes with more cloud cover than this are skipped, percent
NORM_DENOM = 7000  # reflectance scaling before histogram equalisation
EPSG = 32623  # UTM zone 23N, output CRS
RESOLUTION = 10  # output pixel size, m

catalog = pystac_client.Client.open(
    "https://planetarycomputer.microsoft.com/api/stac/v1",
    modifier=planetary_computer.sign_inplace,
)
items = catalog.search(
    collections=["sentinel-2-l2a"],
    bbox=BBOX,
    datetime=f"{YEAR:04d}-{MONTH:02d}-01/{YEAR:04d}-{MONTH:02d}-28",
    query={"eo:cloud_cover": {"lt": MAX_CLOUD}},
).item_collection()

da = stackstac.stack(
    items,
    assets=["B04", "B03", "B02"],  # red, green, blue
    epsg=EPSG,
    bounds_latlon=BBOX,
    chunksize=2048,
    resolution=RESOLUTION,
).assign_coords(band=["red", "green", "blue"])
da = da.sel(time=(da.time.dt.year.isin([YEAR]) & da.time.dt.month.isin([MONTH]))).compute()

da = (da.median("time") / NORM_DENOM).clip(0, 1)
da = xr.apply_ufunc(exposure.equalize_hist, da)
da = da.rio.write_crs(EPSG).rio.set_spatial_dims(x_dim="x", y_dim="y")
da.rio.to_raster(OUT_TIF)
print(f"wrote {OUT_TIF}")
