"""Aerosol number concentration per station, with composition pie charts overlaid.

Box plots: number concentration of aerosol particles (10-710 nm) for July/August at
Narsaq (2023), Zeppelin (2010-2020), Villum (2010-2017), Mace Head (2011-2012) and
Jungfraujoch (2012-2014). Boxes = interquartile range, whiskers = 10th/90th
percentiles, bar = median.

Pie charts: fractional contribution of four PM10 ions for Narsaq (2023), Zeppelin
(1993-2019), Villum (1990-2017) and Jungfraujoch (2011-2021).

Data flow: box-plots.txt + Pie-charts.txt -> box statistics + normalised ion
fractions -> box plots with inset pies. All settings live in
``config_AEROSOL_CONC.yaml``. The stacked-bar variant is
``plot_AEROSOL_CONC_STACKED.py``.

Run from the repository root:

    MPLCONFIGDIR="$TMPDIR/mpl" .venv/bin/python figures/fig7_AEROSOL_CONC/plot_AEROSOL_CONC.py
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from greenfjord.config import get_script_name, read_config
from greenfjord.viz import set_paper_style

# paths and names, derived from the script name (plot_<NAME>.py)
HERE = Path(__file__).resolve().parent
NAME = get_script_name(__file__)
FIG_STEM = f"fig_{NAME}"

# config
cfg = read_config(HERE / f"config_{NAME}.yaml")
analysis = cfg["analysis"]
plot = cfg["plot"]
output = cfg["output"]
BOX_STATS = HERE / cfg["inputs"]["box_stats"]
ION_FRACTIONS = HERE / cfg["inputs"]["ion_fractions"]


def load_box_stats() -> list[dict]:
    """Return matplotlib ``bxp`` statistics per station (whiskers = 10th/90th percentile)."""
    box = pd.read_csv(BOX_STATS, sep="\t").set_index("placesnames")
    stats = []
    for name in analysis["stations"]:
        r = box.loc[name]
        stats.append({
            "label": name,
            "q1": r["W_Percentile_all_25"],
            "med": r["W_Percentile_all_50"],
            "q3": r["W_Percentile_all_75"],
            "whislo": r["W_Percentile_all_25"] - r["W_Percentile_all_10EB"],
            "whishi": r["W_Percentile_all_75"] + r["W_Percentile_all_90EB"],
            "fliers": [],
        })
    return stats


def load_ion_fractions() -> pd.DataFrame:
    """Return ion fractions (rows = ion names, columns = data columns)."""
    # keep_default_na=False so the species label "NA" (sodium) is not read as NaN
    pie = pd.read_csv(ION_FRACTIONS, sep="\t", keep_default_na=False)
    return pie.set_index("species").astype(float).rename(index=analysis["species_rows"])


def plot_composition_pies(ax, pie: pd.DataFrame) -> None:
    """Draw one pie per station as an inset axes in data coordinates above its box."""
    p = plot["pie"]
    ion_order = plot["ion_order"]
    y_span = plot["ylim"][1]
    lim = p["axes_half_width"]
    for name, pos in p["positions"].items():
        frac = pie[analysis["pie_columns"][name]].reindex(ion_order)
        frac = frac / frac.sum()
        r = pos["radius"]
        axpie = ax.inset_axes(
            [pos["x"] - r, pos["y"] - r * y_span / 2, 2 * r, r * y_span],
            transform=ax.transData,
            zorder=5,
        )
        axpie.pie(
            frac.values,
            colors=[plot["ion_colors"][s] for s in ion_order],
            startangle=p["startangle"],
            counterclock=False,
            autopct=p["autopct"],
            pctdistance=p["label_distance"],
            explode=[p["explode"]] * len(ion_order),
            wedgeprops=dict(linewidth=p["edge_linewidth"], edgecolor=p["edge_color"]),
            textprops=dict(fontsize=p["label_fontsize"], color=p["label_color"]),
        )
        axpie.set(aspect="equal", xlim=(-lim, lim), ylim=(-lim, lim))


def plot_box_concentrations(ax, stats: list[dict]) -> None:
    """Draw the number-concentration box plots."""
    b = plot["box"]
    n = len(stats)
    ax.bxp(
        stats,
        positions=list(range(1, n + 1)),
        widths=b["width"],
        showfliers=False,
        patch_artist=True,
        boxprops=dict(facecolor=b["facecolor"], edgecolor=b["color"], lw=b["linewidth"]),
        whiskerprops=dict(color=b["color"], lw=b["linewidth"]),
        capprops=dict(lw=b["cap_linewidth"]),
        medianprops=dict(color=b["color"], lw=b["linewidth"]),
    )
    ax.set_ylabel(plot["ylabel"])
    ax.set_ylim(*plot["ylim"])
    yt = plot["yticks"]
    ax.set_yticks(range(yt["start"], yt["stop"] + 1, yt["step"]))
    ax.set_xlim(0, n + plot["xlim_pad"])
    ax.set_xticklabels(
        plot["station_labels"], fontsize=plot["xtick_fontsize"], fontweight=plot["xtick_fontweight"]
    )
    ax.tick_params(axis="x", length=0)


def plot_ion_legend(ax) -> None:
    """Legend without markers: each ion name is printed in its own colour."""
    ions = plot["ion_order"]
    handles = [plt.Line2D([0], [0], ls="", marker="") for _ in ions]
    ax.legend(
        handles=handles,
        labels=ions,
        labelcolor=[plot["ion_colors"][s] for s in ions],
        loc=plot["legend"]["loc"],
        bbox_to_anchor=plot["legend"]["bbox_to_anchor"],
        handlelength=0,
        handletextpad=0,
        prop=dict(weight=plot["legend"]["weight"]),
    )


def main() -> None:
    set_paper_style(plot.get("style"))
    stats = load_box_stats()
    pie = load_ion_fractions()

    fig, ax = plt.subplots(figsize=plot["figsize"])
    plot_box_concentrations(ax, stats)
    plot_composition_pies(ax, pie)
    plot_ion_legend(ax)
    fig.tight_layout()

    for fmt in output["formats"]:
        out = HERE / f"{FIG_STEM}.{fmt}"
        fig.savefig(out, dpi=output["dpi"], bbox_inches="tight")
        print(f"saved {out}")


if __name__ == "__main__":
    main()
