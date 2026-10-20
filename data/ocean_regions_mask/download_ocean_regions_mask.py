"""Build the ocean-region mask of the GreenFjord domain.

Writes ``ocean_regions_mask.nc`` next to this script. Regions come from
GEBCO 2023 bathymetry and distance to coast (read from the project S3 bucket
by ``greenfjord.data.other.get_ocean_regions``). Region classes: 0 near-shore
(unused), 1 Oceanic, 2 Southwest, 3 Central western, 4 South Eastern.

Run from the repository root:

    .venv/bin/python data/ocean_regions_mask/download_ocean_regions_mask.py
"""

from __future__ import annotations

from pathlib import Path

from greenfjord.data.other import get_ocean_regions

HERE = Path(__file__).resolve().parent
OUT = HERE / "ocean_regions_mask.nc"

SHELF_DEPTH_LIMIT = -500  # m; shelf is shallower than this, open ocean deeper
CLOSING_RADIUS = 5  # pixels, morphological closing of each region
MIN_HOLE_PIXEL_SIZE = 10000  # pixels, smaller holes inside a region are filled


def main() -> None:
    mask = get_ocean_regions(
        shelf_depth_limit=SHELF_DEPTH_LIMIT,
        closing_radius=CLOSING_RADIUS,
        min_hole_pixel_size=MIN_HOLE_PIXEL_SIZE,
    )
    # netCDF can't store a list attribute, so the region names are '|'-joined
    mask.assign_attrs(names="|".join(mask.attrs["names"])).to_netcdf(OUT)


if __name__ == "__main__":
    main()
