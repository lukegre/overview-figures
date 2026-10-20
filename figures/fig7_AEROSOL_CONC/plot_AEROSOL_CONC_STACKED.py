"""Aerosol composition (stacked bars) over number concentration (box plots), per station.

Top panel: stacked-bar composition (%) of the four dominant PM ions per station,
each station normalised to 100 %. Bottom panel: number-concentration box plots on
a logarithmic axis (boxes = interquartile range, whiskers = 10th/90th
percentiles, bar = median; no fliers). Mace Head has no composition data.

Data flow: box-plots.txt + Pie-charts.txt -> box statistics + ion percentages ->
two stacked panels. All settings live in ``config_AEROSOL_CONC_STACKED.yaml``.
The pie-chart variant is ``plot_AEROSOL_CONC.py``.

Run from the repository root:

    MPLCONFIGDIR="$TMPDIR/mpl" .venv/bin/python figures/fig7_AEROSOL_CONC/plot_AEROSOL_CONC_STACKED.py
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
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


def composition_pct(pie: pd.DataFrame, name: str) -> pd.Series:
    """Return the four ion fractions (%) for a station, normalised to 100."""
    frac = pie[analysis["pie_columns"][name]].reindex(plot["stack_order"])
    return frac / frac.sum() * 100.0


def plot_composition_bars(ax, pie: pd.DataFrame, positions) -> None:
    """Draw the stacked ion-composition bars (top panel)."""
    c = plot["composition"]
    na = c["not_available"]
    for x, name in zip(positions, analysis["stations"]):
        if name in analysis["no_composition_stations"]:
            ax.bar(
                x,
                100,
                width=c["bar_width"],
                facecolor="none",
                edgecolor=na["edge_color"],
                hatch=na["hatch"],
                linewidth=na["edge_linewidth"],
                zorder=2,
            )
            ax.text(
                x,
                50,
                na["text"],
                ha="center",
                va="center",
                fontsize=na["fontsize"],
                color=na["text_color"],
                bbox=dict(
                    facecolor="white", edgecolor="none", alpha=na["box_alpha"], boxstyle="round,pad=0.2"
                ),
            )
            continue
        pct = composition_pct(pie, name)
        bottom = 0.0
        for ion in plot["stack_order"]:
            h = pct[ion]
            ax.bar(
                x,
                h,
                width=c["bar_width"],
                bottom=bottom,
                facecolor=plot["ion_colors"][ion],
                edgecolor=c["edge_color"],
                zorder=2,
            )
            if h > c["label_min_percent"]:
                ax.text(
                    x,
                    bottom + h / 2,
                    c["label_format"].format(h),
                    ha="center",
                    va="center",
                    fontsize=c["label_fontsize"],
                    color=plot["ion_label_colors"][ion],
                )
            bottom += h

    yt = c["yticks"]
    ax.set_ylabel(c["ylabel"])
    ax.set_ylim(yt["start"], yt["stop"])
    ax.set_yticks(range(yt["start"], yt["stop"] + 1, yt["step"]))
    ax.spines["bottom"].set_visible(True)


def plot_box_concentrations(ax, stats: list[dict], positions) -> None:
    """Draw the log-scale number-concentration box plots (bottom panel)."""
    c = plot["concentration"]
    b = c["box"]
    g = c["grid"]
    ax.set_yscale("log")
    ax.bxp(
        stats,
        positions=list(positions),
        widths=b["width"],
        showfliers=False,
        patch_artist=True,
        boxprops=dict(facecolor=b["facecolor"], edgecolor=b["color"], lw=b["box_linewidth"]),
        whiskerprops=dict(color=b["color"], lw=b["line_linewidth"]),
        capprops=dict(color="none", lw=1.3),  # no whisker caps
        medianprops=dict(color=b["color"], lw=b["line_linewidth"]),
        zorder=3,
    )
    ax.set_ylabel(c["ylabel"])
    ax.set_ylim(*c["ylim"])
    ax.set_yticks(c["yticks"])
    ax.set_yticklabels(c["yticklabels"])
    ax.grid(axis="y", which="major", ls=g["linestyle"], color=g["color"], lw=g["linewidth"], zorder=0)
    ax.set_axisbelow(True)


def plot_ion_legend(fig) -> None:
    """Legend of coloured squares above the panels."""
    leg = plot["legend"]
    handles = [
        plt.Rectangle((0, 0), 1, 1, facecolor=plot["ion_colors"][s], edgecolor="none")
        for s in plot["legend_order"]
    ]
    fig.legend(
        handles,
        plot["legend_order"],
        loc=leg["loc"],
        bbox_to_anchor=leg["bbox_to_anchor"],
        frameon=False,
        linewidth=0.5,
        ncol=leg["ncol"],
        handlelength=leg["handlelength"],
        handleheight=leg["handleheight"],
        labelspacing=leg["labelspacing"],
        fontsize=leg["fontsize"],
    )


def main() -> None:
    set_paper_style(plot.get("style"))
    stats = load_box_stats()
    pie = load_ion_fractions()

    n = len(analysis["stations"])
    positions = np.arange(1, n + 1)
    dividers = positions[:-1] + 0.5  # vertical separators between stations

    fig, (ax_top, ax_bot) = plt.subplots(
        2,
        1,
        figsize=plot["figsize"],
        sharex=True,
        gridspec_kw=dict(height_ratios=plot["height_ratios"], hspace=plot["panel_hspace"]),
    )
    plot_composition_bars(ax_top, pie, positions)
    plot_box_concentrations(ax_bot, stats, positions)

    for ax in (ax_top, ax_bot):
        for xd in dividers:
            ax.axvline(xd, color=plot["divider"]["color"], lw=plot["divider"]["linewidth"], zorder=1)
    ax_bot.set_xlim(0.5, n + 0.5)
    ax_bot.set_xticks(positions)
    ax_bot.set_xticklabels(plot["station_labels"], fontsize=plot["xtick_fontsize"])
    ax_bot.tick_params(axis="x", length=0)

    plot_ion_legend(fig)
    fig.subplots_adjust(**plot["margins"])

    for fmt in output["formats"]:
        out = HERE / f"{FIG_STEM}.{fmt}"
        fig.savefig(out, dpi=output["dpi"], bbox_inches="tight")
        print(f"saved {out}")


if __name__ == "__main__":
    main()
