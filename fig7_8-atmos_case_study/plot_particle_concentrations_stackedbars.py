"""
Two-panel version of the aerosol case-study figure (white background).

Top panel    : stacked-bar composition (%) of the four dominant PM ions per
                station, each station normalised to 100 %.
Bottom panel : number-concentration box plots on a logarithmic axis. Boxes =
                interquartile range, whiskers = 10th/90th percentiles, bar =
                median. No fliers / no scatter points are drawn.

Data:
  box-plots.txt  - box statistics (see column notes below)
  Pie-charts.txt - ion fractions per station

Colours are taken exactly from the original figure (they carry meaning in the
community). Mace Head has no composition data ("Not available").
"""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

HERE = Path(__file__).parent

plt.style.use(str(HERE / "figure.mplstyle"))

# Exact colours sampled from the original figure ------------------------------
COLORS = {
    "Sodium": "#6911dd",  # NA  (purple)
    "Nitrate": "#173df5",  # NO3 (blue)
    "Sulfate": "#ea3323",  # SO4 (red)
    "Ammonium": "#f3ae3d",  # NH4 (orange)
}
# White text reads well on the dark slices; black on the light orange one.
LABEL_COLOR = {
    "Sodium": "white",
    "Nitrate": "white",
    "Sulfate": "white",
    "Ammonium": "black",
}
# Stacking order (bottom -> top). Consistent across stations so the stack is
# readable; the legend follows the reverse (top -> bottom) order.
STACK_ORDER = ["Ammonium", "Sulfate", "Nitrate", "Sodium"]
LEGEND_ORDER = ["Sodium", "Nitrate", "Sulfate", "Ammonium"]

STATIONS = ["Narsaq", "Zeppelin", "Villum", "Mace Head", "Jungfraujoch"]
XNAMES = [
    "Narsaq\nGreenland",
    "Zeppelin\nSvalbard",
    "Villum\nGreenland",
    "Mace Head\nIreland",
    "Jungfraujoch\nSwitzerland",
]
NO_COMPOSITION = {"Mace Head"}

# --- Box-plot statistics -----------------------------------------------------
# Columns: *_25 / *_50 / *_75 are the box (Q1/median/Q3); *_10EB and *_90EB are
# the whisker error-bar lengths measured from the box edges, i.e.
#   lower whisker (10th pct) = Q1 - 10EB ; upper whisker (90th pct) = Q3 + 90EB.
box = pd.read_csv(HERE / "data" / "box-plots.txt", sep="\t").set_index("placesnames")

bxp_stats = []
for name in STATIONS:
    r = box.loc[name]
    bxp_stats.append({
        "label": name,
        "q1": r["W_Percentile_all_25"],
        "med": r["W_Percentile_all_50"],
        "q3": r["W_Percentile_all_75"],
        "whislo": r["W_Percentile_all_25"] - r["W_Percentile_all_10EB"],
        "whishi": r["W_Percentile_all_75"] + r["W_Percentile_all_90EB"],
        "fliers": [],
    })

# --- Composition -------------------------------------------------------------
# keep_default_na=False so the species label "NA" (sodium) is not read as NaN.
pie = pd.read_csv(HERE / "data" / "Pie-charts.txt", sep="\t", keep_default_na=False)
pie = pie.set_index("species").astype(float)
ROW = {"NA": "Sodium", "NO3": "Nitrate", "SO4": "Sulfate", "NH4": "Ammonium"}
pie = pie.rename(index=ROW)

PIE_COL = {  # station -> data column
    "Narsaq": "Na_species_PM10",
    "Zeppelin": "Zep_species",
    "Villum": "Vil_species",
    "Jungfraujoch": "JFJ_species",
}


def composition_pct(name):
    """Return the four ion fractions (%) for a station, normalised to 100."""
    frac = pie[PIE_COL[name]].reindex(STACK_ORDER)
    return frac / frac.sum() * 100.0


# --- Figure ------------------------------------------------------------------
positions = np.arange(1, len(STATIONS) + 1)
dividers = positions[:-1] + 0.5  # vertical separators between stations

fig, (ax_top, ax_bot) = plt.subplots(
    2,
    1,
    figsize=(7, 4),
    sharex=True,
    gridspec_kw=dict(height_ratios=[1, 1], hspace=0.08),
)
fig.patch.set_facecolor("white")
for ax in (ax_top, ax_bot):
    ax.set_facecolor("white")

# ---- top panel : stacked composition bars ----
BAR_W = 0.62
for x, name in zip(positions, STATIONS):
    if name in NO_COMPOSITION:
        ax_top.bar(
            x,
            100,
            width=BAR_W,
            facecolor="none",
            edgecolor="0.7",
            hatch="///",
            linewidth=0.8,
            zorder=2,
        )
        ax_top.text(
            x,
            50,
            "Not\navailable",
            ha="center",
            va="center",
            fontsize=8,
            color="0.35",
            bbox=dict(facecolor="white", edgecolor="none", alpha=0.95, boxstyle="round,pad=0.2"),
        )
        continue
    pct = composition_pct(name)
    bottom = 0.0
    for ion in STACK_ORDER:
        h = pct[ion]
        ax_top.bar(x, h, width=BAR_W, bottom=bottom, facecolor=COLORS[ion], edgecolor="w", zorder=2)
        if h > 5:
            ax_top.text(
                x,
                bottom + h / 2,
                f"{h:.0f}%",
                ha="center",
                va="center",
                fontsize=8,
                color=LABEL_COLOR[ion],
            )
        bottom += h

ax_top.set_ylabel("Composition (%)")
ax_top.set_ylim(0, 100)
ax_top.set_yticks(range(0, 101, 25))
ax_top.spines["bottom"].set_visible(True)
for xd in dividers:
    ax_top.axvline(xd, color="0.75", lw=0.8, zorder=1)

# ---- bottom panel : log-scale box plots (no points) ----
ax_bot.set_yscale("log")
ax_bot.bxp(
    bxp_stats,
    positions=list(positions),
    widths=0.5,
    showfliers=False,
    patch_artist=True,
    boxprops=dict(facecolor="0.96", edgecolor="0.25", lw=0.8),
    whiskerprops=dict(color="0.25", lw=1),
    capprops=dict(color="none", lw=1.3),
    medianprops=dict(color="0.25", lw=1),
    zorder=3,
)

ax_bot.set_ylabel("Aerosol number\nconcentration (cm$^{-3}$)")
ax_bot.set_ylim(30, 6e3)
ax_bot.set_yticks([100, 1000])
ax_bot.set_yticklabels(["$10^2$", "$10^3$"])
# faint dotted horizontal grid at the decades, like the original
ax_bot.grid(axis="y", which="major", ls=":", color="0.7", lw=0.8, zorder=0)
ax_bot.set_axisbelow(True)
for xd in dividers:
    ax_bot.axvline(xd, color="0.75", lw=0.8, zorder=1)

ax_bot.set_xlim(0.5, len(STATIONS) + 0.5)
ax_bot.set_xticks(positions)
ax_bot.set_xticklabels(XNAMES, fontsize="medium")
ax_bot.tick_params(axis="x", length=0)

# ---- legend (coloured squares, upper-left, outside the axes) ----
handles = [plt.Rectangle((0, 0), 1, 1, facecolor=COLORS[s], edgecolor="none") for s in LEGEND_ORDER]
fig.legend(
    handles,
    LEGEND_ORDER,
    loc="upper center",
    bbox_to_anchor=(0.63, 1.08),
    frameon=False,
    linewidth=0.5,
    ncol=4,
    handlelength=1.1,
    handleheight=1.1,
    labelspacing=0.6,
    fontsize="medium",
)

fig.subplots_adjust(left=0.30, right=0.97, top=0.97, bottom=0.10)
out = HERE / "fig7-particle_concentrations_stackedbars.png"
fig.savefig(out, dpi=300, facecolor="white")
print(f"saved {out}")
