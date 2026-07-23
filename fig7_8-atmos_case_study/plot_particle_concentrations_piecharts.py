"""
Recreate the particle-number-concentration box-plot figure with overlaid
composition pie charts.

Box plots: number concentration of aerosol particles (10-710 nm) for
July/August at Narsaq (2023), Zeppelin (2010-2020), Villum (2010-2017),
Mace Head (2011-2012), Jungfraujoch (2012-2014). Boxes = interquartile range,
whiskers = 10th/90th percentiles, bar = median.

Pie charts: fractional contribution of selected ions in PM10 for Narsaq (2023),
Zeppelin (1993-2019), Villum (1990-2017), Jungfraujoch (2011-2021).

Colours are taken exactly from the original figure (they carry meaning in the
community). Adjustment vs. the original: a small gap is added between pie slices.
"""

from pathlib import Path

import matplotlib.pyplot as plt
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

STATIONS = ["Narsaq", "Zeppelin", "Villum", "Mace Head", "Jungfraujoch"]
XNAMES = [
    "Narsaq\nGreenland",
    "Zeppelin\nSvalbard",
    "Villum\nGreenland",
    "Mace Head\nIreland",
    "Jungfraujoch\nSwitzerland",
]

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

# --- Pie-chart composition ---------------------------------------------------
# Note: 'Na_species_PM10' is the Narsaq PM10 column (Na = Narsaq, not sodium).
# keep_default_na=False so the species label "NA" (sodium) is not read as NaN.
pie = pd.read_csv(HERE / "data" / "Pie-charts.txt", sep="\t", keep_default_na=False)
pie = pie.set_index("species").astype(float)
# map species-row labels to legend names
ROW = {"NA": "Sodium", "NO3": "Nitrate", "SO4": "Sulfate", "NH4": "Ammonium"}
pie = pie.rename(index=ROW)

PIE_COL = {  # station -> data column ; Mace Head has no pie
    "Narsaq": "Na_species_PM10",
    "Zeppelin": "Zep_species",
    "Villum": "Vil_species",
    "Jungfraujoch": "JFJ_species",
}
PIE_ORDER = ["Sodium", "Nitrate", "Sulfate", "Ammonium"]

# --- Figure ------------------------------------------------------------------
fig, ax = plt.subplots()  # size from figure.mplstyle (default 7.5 in wide)
positions = range(1, len(STATIONS) + 1)

ax.bxp(
    bxp_stats,
    positions=list(positions),
    widths=0.5,
    showfliers=False,
    patch_artist=True,
    boxprops=dict(facecolor="white", edgecolor="black", lw=1.3),
    whiskerprops=dict(color="black", lw=1.3),
    capprops=dict(lw=0),  # original has no whisker caps
    medianprops=dict(color="black", lw=1.3),
)

ax.set_ylabel("number concentration (cm$^{-3}$)")
ax.set_ylim(0, 3050)  # matches original framing
ax.set_yticks(range(0, 3001, 500))
ax.set_xlim(0, len(STATIONS) + 1)
ax.set_xticklabels(XNAMES, fontsize=11, fontweight=100)
ax.tick_params(axis="x", length=0)

# Overlaid pie charts (data-coordinate placement above each box).
# The percentage labels sit just OUTSIDE the rim in black, exactly as in the
# original figure. A small explode adds spacing between slices.
PIE_POS = {  # (x-position, y-centre, radius) tuned to sit above each box
    "Narsaq": (1.0, 2550, 0.60),
    "Zeppelin": (2.0, 1950, 0.56),
    "Villum": (3.0, 1500, 0.54),
    "Jungfraujoch": (5.0, 1250, 0.54),
}
# The pie axes span [-LIM, LIM] so external labels (at pctdistance ~1.2) are not
# clipped; the pie itself has radius 1 and stays circular via aspect="equal".
LIM = 1.45
y_span = 3050
for name, (xc, yc, r_ax) in PIE_POS.items():
    frac = pie[PIE_COL[name]].reindex(PIE_ORDER)
    frac = frac / frac.sum()
    axpie = ax.inset_axes(
        [xc - r_ax, yc - r_ax * y_span / 2, 2 * r_ax, r_ax * y_span],
        transform=ax.transData,
        zorder=5,
    )
    # start at 12 o'clock, go clockwise; explode adds spacing between slices
    axpie.pie(
        frac.values,
        colors=[COLORS[s] for s in PIE_ORDER],
        startangle=270,
        counterclock=False,
        autopct="%.0f%%",
        pctdistance=1.26,
        explode=[0.02] * len(PIE_ORDER),
        wedgeprops=dict(linewidth=1, edgecolor="white"),
        textprops=dict(fontsize=8, color="black"),
    )
    axpie.set(aspect="equal", xlim=(-LIM, LIM), ylim=(-LIM, LIM))

# Legend (matches original wording/colour order). No marker box: the label
# text itself carries the colour, so each species name is printed in its colour.
LEGEND_ORDER = ["Sodium", "Nitrate", "Sulfate", "Ammonium"]
handles = [plt.Line2D([0], [0], ls="", marker="") for _ in LEGEND_ORDER]
ax.legend(
    handles=handles,
    labels=LEGEND_ORDER,
    labelcolor=[COLORS[s] for s in LEGEND_ORDER],
    loc="upper right",
    bbox_to_anchor=(0.99, 0.99),
    handlelength=0,
    handletextpad=0,
    prop=dict(weight="bold"),
)

fig.tight_layout()
out = HERE / "fig7-particle_concentrations_piecharts.png"
fig.savefig(out, dpi=300, bbox_inches="tight")
print(f"saved {out}")
