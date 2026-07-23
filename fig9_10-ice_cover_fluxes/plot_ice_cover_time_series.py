"""Plot fjord ice-cover time series grouped by Inner, Mid, and Outer region."""

from __future__ import annotations

from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd

HERE = Path(__file__).resolve().parent
ICE_COVER_PATH = HERE / "data" / "fjord_ice_regions-time_series.xlsx"
OUTPUT_PATH = HERE / "fig10-ice_cover_timeseries.png"

# Workbook fjord header, display label, and the palette used in recreate_figure.py.
FJORDS = (
    ("Sermelik - Ikersuaq", "Sermilik Ikersuaq", "#2C7FB8"),
    ("Tunuliarfik", "Tunulliarfik", "#9E3D88"),
    ("Igalikup Kangerlua", "Igalikup Kangerlua", "#D55E4B"),
)
REGIONS = ("Inner ", "Mid", "Outer")


def read_ice_cover(path: Path) -> tuple[pd.Series, pd.DataFrame]:
    """Load monthly ice-cover measurements from the source workbook."""
    data = pd.read_excel(path, sheet_name="seaice_conc", header=[0, 1])
    time = pd.to_datetime(data.iloc[:, 0])
    columns = {
        (fjord, region): pd.to_numeric(data[(fjord, region)], errors="coerce")
        for fjord, _, _ in FJORDS
        for region in REGIONS
    }
    columns[("Oceanic", "Coastal ocean")] = pd.to_numeric(
        data[("Oceanic", "Coastal ocean")], errors="coerce"
    )
    return time, pd.DataFrame(columns)


def style_axis(axis: plt.Axes) -> None:
    axis.spines["top"].set_visible(False)
    axis.spines["right"].set_visible(False)
    for spine in axis.spines.values():
        spine.set_linewidth(0.6)
        spine.set_color("#555555")
    axis.set_ylim(0, 100)
    axis.set_yticks((0, 25, 50, 75, 100))
    for level in (50, 100):
        axis.axhline(level, color="#D9D9D9", linewidth=0.7, zorder=0)
    axis.set_ylabel("Ice cover (%)")
    axis.tick_params(direction="in", width=0.6, length=2.5)


def make_figure() -> None:
    time, ice_cover = read_ice_cover(ICE_COVER_PATH)
    fig, axes = plt.subplots(3, 1, figsize=(8.0, 6.0), dpi=150, sharex=True)

    for axis, region, label in zip(axes, REGIONS, ["a", "b", "c"], strict=True):
        for workbook_fjord, display_name, colour in FJORDS:
            axis.plot(
                time,
                ice_cover[(workbook_fjord, region)],
                color=colour,
                linewidth=2.5,
                label=display_name,
            )
        style_axis(axis)
        axis.set_title(f"{label}) {region.strip()}", loc="left", fontweight="bold", pad=4)

    # Add the coastal ocean series to the bottom (Outer) panel.
    axes[-1].plot(
        time,
        ice_cover[("Oceanic", "Coastal ocean")],
        color="#9E9E9E",
        linewidth=2.0,
        linestyle="-",
        label="Coastal ocean",
    )

    handles, labels = axes[-1].get_legend_handles_labels()
    axes[-1].legend(handles, labels, frameon=False, ncols=4, loc="upper center", fontsize=9)
    axes[-1].set_xlabel("Year")
    axes[-1].xaxis.set_major_locator(mdates.YearLocator(2))
    axes[-1].xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    fig.tight_layout()

    fig.savefig(OUTPUT_PATH, dpi=150)
    fig.savefig(OUTPUT_PATH.with_suffix(".pdf"), bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    make_figure()
    print(f"Wrote {OUTPUT_PATH}")
