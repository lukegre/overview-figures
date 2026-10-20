"""Build the along-fjord BedMachine bathymetry sections for the GreenFjord fjords.

BedMachine v6 is collapsed across each cross-fjord polygon of the fjord
centreline (``fjord_props.FjordAggregator``), giving one depth per distance
along the fjord. Writes one NetCDF per aggregation method and fjord next to
this script: ``fjord_bathymetry_<agg_method>_fjord_<fjord_num>.nc``.

Run from the repository root:

    .venv/bin/python data/fjord_bathymetry/download_fjord_bathymetry.py
"""

from __future__ import annotations

from pathlib import Path

import fjord_props as fp
import xarray as xr

HERE = Path(__file__).resolve().parent
DATA = HERE.parent

# request parameters
FJORD_NUMS = [54, 56]  # fjord ids: 54 = glacial fjord (Narsaq), 56 = land fjord (Qaqortoq)
# statistic across each cross-fjord polygon: "min" is the thalweg (deepest point)
AGG_METHODS = ["min", "median", "mean", "max"]
POLYGON_SPACING_M = 500.0  # distance between cross-fjord polygons along the centreline, m

# inputs
BEDMACHINE = HERE / "BedMachineGreenland_bed-v6.tif"
FJORD_PICKLE = DATA / "fjords" / "fjord_{fjord_num}" / "fjord_aggregator.pkl_joblib"

# output
OUTPUT = HERE / "fjord_bathymetry_{agg_method}_fjord_{fjord_num}.nc"


def open_bathymetry() -> xr.DataArray:
    return (
        xr.open_dataarray(BEDMACHINE, chunks={"x": 1024, "y": 1024})
        .isel(band=0, drop=True)
        .rename("bathymetry")
    )


def open_fjord(fjord_num: int) -> fp.FjordAggregator:
    fjord = fp.FjordAggregator.from_pickle(str(FJORD_PICKLE).format(fjord_num=fjord_num))
    fjord.polygons = fjord.compute_polygons(interp_distance_m=POLYGON_SPACING_M)
    return fjord


def get_fjord_bathymetry(fjord: fp.FjordAggregator, bath: xr.DataArray, agg_method: str):
    """Section along the centreline; distance_to_glacier_km increases down-fjord."""
    section = fjord.get_aggregated_by_distance(bath, agg_method=agg_method)
    section = section.assign_coords(
        distance=lambda x: (x.distance.max() - x.distance) / 1e3
    ).rename(distance="distance_to_glacier_km")
    return section.compute().sortby("distance_to_glacier_km")


def main() -> None:
    bath = open_bathymetry()
    for fjord_num in FJORD_NUMS:
        fjord = open_fjord(fjord_num)
        for agg_method in AGG_METHODS:
            section = get_fjord_bathymetry(fjord, bath, agg_method)
            out = Path(str(OUTPUT).format(agg_method=agg_method, fjord_num=fjord_num))
            section.to_netcdf(out)
            print(f"wrote {out.relative_to(DATA.parent)}")


if __name__ == "__main__":
    main()
