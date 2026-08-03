import pathlib

import fjord_props as fp
from xarray import DataArray, open_dataarray

BASE = pathlib.Path(__file__).resolve().parent.parent
FNAME_BEDMACHINE6 = str(BASE / "data" / "BedMachine" / "BedMachineGreenland_bed-v6.tif")
FNAME_FJORD = str(BASE / "data" / "fjords" / "fjord_{fjord_num}" / "fjord_aggregator.pkl_joblib")


def get_fjord_bathymetry(
    fjord_num: int,
    fname_bedmachine6: str = FNAME_BEDMACHINE6,
    fname_fjord: str = FNAME_FJORD,
    agg_method: str = "median",
):
    """Bathymetry aggregated along the fjord centerline.

    ``agg_method`` is applied across each cross-fjord polygon: "median" gives a
    representative depth, "min" the thalweg (deepest point).
    """
    bath = open_bathymetry(fname_bedmachine6)
    fjord = open_fjord_data(fjord_num, fname_fjord=fname_fjord)
    fjord_bath = _get_fjord_bathymetry(fjord, bath, agg_method=agg_method)

    return fjord_bath


def open_bathymetry(fname_bedmachine6: str = FNAME_BEDMACHINE6):
    chunks = {"x": 1024, "y": 1024}

    return (
        open_dataarray(fname_bedmachine6, chunks=chunks)
        .isel(band=0, drop=True)
        .rename("bathymetry")
    )


def open_fjord_data(
    fjord_num: int,
    grid_size: float = 500.0,
    fname_fjord: str = FNAME_FJORD,
):
    fjord = fp.FjordAggregator.from_pickle(fname_fjord.format(fjord_num=fjord_num))

    fjord.polygons = fjord.compute_polygons(interp_distance_m=grid_size)

    return fjord


def _get_fjord_bathymetry(
    fjord: fp.FjordAggregator, bath: DataArray, agg_method: str = "median"
):
    fjord_bath = fjord.get_aggregated_by_distance(bath, agg_method=agg_method)
    fjord_bath = fjord_bath.assign_coords(
        distance=lambda x: (x.distance.max() - x.distance) / 1e3
    ).rename(distance="distance_to_glacier_km")
    return fjord_bath
