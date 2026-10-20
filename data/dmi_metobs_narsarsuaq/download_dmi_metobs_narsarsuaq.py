"""Download the DMI metObs record of Narsarsuaq airport (station 04270).

Writes ``dmi_metobs_narsarsuaq.csv`` next to this script: hourly, raw (not
quality controlled) observations indexed by UTC ``time``. The DMI open-data
API needs no credentials.

Run from the repository root:

    .venv/bin/python data/dmi_metobs_narsarsuaq/download_dmi_metobs_narsarsuaq.py
"""

from __future__ import annotations

from pathlib import Path

from greenfjord.data.weather_station_dmi import NARSARSUAQ, fetch_dmi_station

HERE = Path(__file__).resolve().parent
OUT = HERE / "dmi_metobs_narsarsuaq.csv"

STATION_ID = NARSARSUAQ  # '04270'
START = None  # None = start of the record (1961)
END = None  # None = up to now


def main() -> None:
    fetch_dmi_station(STATION_ID, start=START, end=END).to_csv(OUT)


if __name__ == "__main__":
    main()
