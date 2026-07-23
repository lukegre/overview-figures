"""Recreate the ice-cover and freshwater-flux overview figure from source data.

The top-row boxplots use monthly sea-ice concentration measurements from
``fjord_ice_regions-time_series.xlsx``.  The bottom-row bars use
``fluxes_overviewpaper_tabulated.csv``: ice and freshwater fluxes are summed
by fjord, and ocean melt is calculated as ice flux times its supplied ratio.
"""

from __future__ import annotations

import csv
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

HERE = Path(__file__).resolve().parent
CSV_PATH = HERE / "data" / "fluxes_overviewpaper_tabulated.csv"
ICE_COVER_PATH = HERE / "data" / "fjord_ice_regions-time_series.xlsx"
OUTPUT_PATH = HERE / "fig9-ice_cover_fluxes.png"

# CSV fjord name, workbook fjord header, displayed title, panel letter, and colour.
PANELS = (
    (
        "Sermilik",
        "Sermelik - Ikersuaq",
        "Sermilik\nIkersuaq",
        "b)",
        "#2C7FB8",
    ),
    (
        "Narsarsuaq",
        "Tunuliarfik",
        "Tunulliarfik",
        "c)",
        "#9E3D88",
    ),
    (
        "Igaliku",
        "Igalikup Kangerlua",
        "Igalikup\nKangerlua",
        "d)",
        "#D55E4B",
    ),
)


def read_fjord_fluxes(path: Path) -> dict[str, tuple[float, float, float]]:
    """Return total ice, freshwater, and ocean-melt flux for each fjord."""
    totals: dict[str, list[float]] = {}

    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            fjord = row["Fjord"]
            ice_flux = float(row["Ice flux (qice; km3/yr)"] or 0)
            freshwater_flux = float(row["Annual freshwater flux (qfwann; km3/yr)"] or 0)
            ocean_melt_ratio = float(row["Ocean melt (qoceanmelt; ratio to ice flux)"] or 0)

            if fjord not in totals:
                totals[fjord] = [0.0, 0.0, 0.0]
            totals[fjord][0] += ice_flux
            totals[fjord][1] += freshwater_flux
            totals[fjord][2] += ice_flux * ocean_melt_ratio

    return {fjord: tuple(values) for fjord, values in totals.items()}


def read_ice_cover(path: Path) -> tuple[dict[str, list], float]:
    """Read Inner, Mid, and Outer ice-cover series plus mean coastal ice cover."""
    data = pd.read_excel(path, sheet_name="seaice_conc", header=[0, 1])
    ice_cover: dict[str, list] = {}

    for _, workbook_fjord, _, _, _ in PANELS:
        regions = []
        for region in ("Inner ", "Mid", "Outer"):
            values = pd.to_numeric(data[(workbook_fjord, region)], errors="coerce").dropna()
            regions.append(values.to_numpy())
        ice_cover[workbook_fjord] = regions

    coastal = pd.to_numeric(data[("Oceanic", "Coastal ocean")], errors="coerce").dropna()
    return ice_cover, coastal.mean()


def style_axes(axis: plt.Axes, *, top_row: bool, last_column: bool) -> None:
    axis.spines["top"].set_visible(False)
    axis.spines["right"].set_visible(False)
    for spine in axis.spines.values():
        spine.set_linewidth(0.6)
        spine.set_color("#555555")
    # Y-axis lives on the right: ticks on every axis, labels only on the last column.
    # axis.yaxis.set_ticks_position("right")
    # axis.yaxis.set_label_position("right")
    # axis.tick_params(direction="in", width=0.6, length=2.5, labelsize=13)
    # axis.tick_params(axis="y", labelright=last_column)
    if top_row:
        axis.set_ylim(0, 100)
        axis.set_yticks((0, 50, 100))
    else:
        axis.set_ylim(0, 8)
        axis.set_yticks((0, 2, 4, 6, 8))


def make_figure() -> None:
    fluxes = read_fjord_fluxes(CSV_PATH)
    ice_cover, coastal_mean = read_ice_cover(ICE_COVER_PATH)

    fig, axes = plt.subplots(2, 3, figsize=(4, 4), dpi=150, layout="constrained", sharey="row")

    for column, (fjord, workbook_fjord, title, letter, colour) in enumerate(PANELS):
        top_axis = axes[0, column]
        bottom_axis = axes[1, column]
        positions = (1, 2, 3)

        top_axis.boxplot(
            ice_cover[workbook_fjord],
            positions=positions,
            widths=0.55,
            patch_artist=True,
            showfliers=True,
            boxprops={"facecolor": colour, "alpha": 0.40, "edgecolor": colour, "linewidth": 1.1},
            medianprops={"color": colour, "linewidth": 1.1},
            whiskerprops={"color": "#333333", "linewidth": 1.0},
            capprops={"color": "none"},
            flierprops={
                "marker": "o",
                "markersize": 4.5,
                "markerfacecolor": "none",
                "markeredgecolor": "0.6",
                "markeredgewidth": 0.5,
            },
        )
        top_axis.axhline(coastal_mean, color="0.5", linewidth=1.7, linestyle=(0, (2, 2)), zorder=0)
        top_axis.set_xlim(0.3, 3.7)
        top_axis.set_xticks(
            positions,
            ("Inner", "Mid", "Outer"),
            rotation=90,
            ha="center",
            fontsize="medium",
        )
        top_axis.set_title(title, fontsize="medium", loc="left")
        top_axis.text(0.04, 0.96, letter, transform=top_axis.transAxes, fontsize="medium", va="top")
        style_axes(top_axis, top_row=True, last_column=column == len(PANELS) - 1)
        if column == 0:
            top_axis.set_ylabel("Ice cover (%)", fontsize="medium")

        bar_values = fluxes[fjord]
        bottom_axis.bar(
            positions, bar_values, width=0.82, color=colour, edgecolor="black", linewidth=0.55
        )
        bottom_axis.set_xlim(0.3, 3.7)
        bottom_axis.set_xticks(
            positions,
            ("Ice flux", "Freshw.", "Oc. melt"),
            rotation=90,
            ha="center",
            fontsize="medium",
        )
        bottom_axis.text(
            0.04,
            0.97,
            chr(ord("e") + column) + ")",
            transform=bottom_axis.transAxes,
            fontsize="medium",
            va="top",
        )
        style_axes(bottom_axis, top_row=False, last_column=column == len(PANELS) - 1)

    axes[1, 0].set_ylabel(r"Fluxes km$^3\ yr^{-1}$ ", fontsize="medium", labelpad=10)
    fig.savefig(OUTPUT_PATH, dpi=300, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    make_figure()
    print(f"Wrote {OUTPUT_PATH}")
