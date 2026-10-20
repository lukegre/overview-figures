"""Download the GreenFjord sampling-location sheet as CSV.

Fetches the project's master Google Sheet and writes it, unchanged, to
``greenfjord_sample_locations.csv`` next to this script. Row 0 of the sheet
holds per-column instructions, so the header is on row 1 (``plot_MAP.py``
skips the first row when reading).

Run from the repository root (needs network access):

    .venv/bin/python fig1-map_samples/data/download_sample_locations.py
"""

from __future__ import annotations

import urllib.request
from pathlib import Path

# Google Sheet exported as CSV (the live sheet is unversioned)
SHEET_CSV_URL = "https://docs.google.com/spreadsheets/d/1iiT7vFbSD5viC6HbDgk3-UziFO5OaffKlKr9PUTY5YM/export?format=csv"

HERE = Path(__file__).resolve().parent
OUT = HERE / "greenfjord_sample_locations.csv"


def main() -> None:
    urllib.request.urlretrieve(SHEET_CSV_URL, OUT)
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
