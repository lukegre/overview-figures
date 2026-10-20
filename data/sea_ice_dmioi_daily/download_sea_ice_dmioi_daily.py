"""Download the DMI OI Arctic L4 daily sea-ice fraction from CMEMS.

Writes ``sea_ice_dmioi_daily.nc`` next to this script: the daily
``sea_ice_fraction`` (float32, fraction 0-1) over the GreenFjord plot extent
plus a buffer, 1982-2025. The request below reproduces the file that was
originally cached by ``figS_SEAICE_PHENOL`` (formerly ``figS-sea_ice_seasonlity``).

Credentials (``COPERNICUSMARINE_SERVICE_USERNAME`` / ``_PASSWORD``) come from
``.env`` via ``greenfjord.settings.get_env``.

Run from the repository root:

    .venv/bin/python data/sea_ice_dmioi_daily/download_sea_ice_dmioi_daily.py
"""

from __future__ import annotations

from pathlib import Path

import copernicusmarine as cm

from greenfjord.data.copernicusmarine import load_copernicusmarine_credentials

HERE = Path(__file__).resolve().parent
OUT = HERE / "sea_ice_dmioi_daily.nc"

DATASET_ID = "cmems_obs_si_arc_phy_my_L4-DMIOI_P1D-m"
VARIABLE = "sea_ice_fraction"
PLOT_LON = (-52.0, -40.0)  # degrees east, plot extent of the figures using this file
PLOT_LAT = (58.6, 63.0)  # degrees north
BUFFER = 0.1  # degrees added on every side of the plot extent
START_DATETIME = "1982-01-01T00:00:00"
END_DATETIME = "2025-12-31T23:59:59"


def main() -> None:
    load_copernicusmarine_credentials()
    seaice = cm.open_dataset(
        dataset_id=DATASET_ID,
        variables=[VARIABLE],
        minimum_longitude=PLOT_LON[0] - BUFFER,
        maximum_longitude=PLOT_LON[1] + BUFFER,
        minimum_latitude=PLOT_LAT[0] - BUFFER,
        maximum_latitude=PLOT_LAT[1] + BUFFER,
        start_datetime=START_DATETIME,
        end_datetime=END_DATETIME,
    )
    ice_fraction = seaice[VARIABLE].astype("float32").compute()
    ice_fraction.attrs = {"source_dataset_id": DATASET_ID}
    ice_fraction.to_netcdf(OUT, encoding={VARIABLE: {"zlib": True, "complevel": 4}})


if __name__ == "__main__":
    main()
