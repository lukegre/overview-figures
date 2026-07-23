"""
Recreate the PM10 / absorbing-aerosol-index figure.

Main plot   Annually integrated GOME-2 absorbing aerosol index anomaly for the
            area of Narsaq (2013-2024) as a bar chart. The period covered by the
            PM10 record is highlighted with a shaded band.
Inlay       A stripped-down view of the PM10 record in Narsaq (2023): only the
            y-axis (min/max), the WHO 45 ug/m3 limit as a dashed line, and the
            two exceedance peaks annotated with their dates.

Caption (Fig. Y): Anomaly of the GOME-2 absorbing aerosol index compared to the
mean of 2013-2024 for the area of Narsaq. Inlay: estimated PM10 mass
concentration in Narsaq, Greenland, based on aerosol size distribution
measurements by a Fidas Frog (density 1.5 g/cm3); the dashed line indicates the
45 ug/m3 threshold by WHO.
"""

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

HERE = Path(__file__).parent
WHO_THRESHOLD = 45.0  # ug/m3

# Publication-safe palette: blue carries the AAI series, while coral is
# reserved for PM10 exceedances.  The record period is deliberately subdued.
AAI_COLOR = "#245A8D"
EXCEEDANCE_COLOR = "#C54B3C"
RECORD_BAND_COLOR = EXCEEDANCE_COLOR
PM10_COLOR = RECORD_BAND_COLOR
REFERENCE_COLOR = "#3D3D3D"

plt.style.use(str(HERE / "figure.mplstyle"))

# --- PM10 daily record -------------------------------------------------------
# mastertime_1d is LabVIEW time: seconds since 1904-01-01 (the Fidas/LabVIEW
# epoch). This maps the first sample to 2023-06-21.
pm10 = pd.read_csv(HERE / "data" / "PM10-concentrations.txt", sep="\t")
pm10["time"] = pd.Timestamp("1904-01-01") + pd.to_timedelta(pm10["mastertime_1d"], unit="s")
pm10 = pm10.dropna(subset=["PM10_1d"])

# --- Absorbing aerosol index -------------------------------------------------
# Daily point estimates -> annual integral (sum) per year.
aai = pd.read_csv(
    HERE / "data" / "greenfjord_timeseries_aai_anom_gome2b_2013_2024.csv", parse_dates=["time"]
)
aai_annual = aai.groupby(aai["time"].dt.year)["absorbing_aerosol_index"].sum()
years = aai_annual.index.to_numpy()


def to_decimal_year(ts):
    start = pd.Timestamp(ts.year, 1, 1)
    return ts.year + (ts - start) / (pd.Timestamp(ts.year + 1, 1, 1) - start)


pm10_start = to_decimal_year(pm10["time"].min())
pm10_end = to_decimal_year(pm10["time"].max())

# --- Figure ------------------------------------------------------------------
fig, ax = plt.subplots(figsize=(7.5, 4))

# Main plot: annual AAI anomaly, one bar per year
ax.bar(years + 0.5, aai_annual.values, width=0.85, color=AAI_COLOR, zorder=2)
# Widened slightly so the short measurement period remains visible at column width.
band_pad = 0.0
ax.axhline(0, color=REFERENCE_COLOR, lw=0.75, zorder=3)
ax.set_ylabel("Integrated AAI anomaly (annual)")
ax.set_xlim(years.min(), years.max() + 1)
ax.set_ylim(-25, 55)
ax.tick_params(axis="both", width=0.8, length=3)
ax.hlines(ax.get_yticks(), *ax.get_xlim(), colors="white", lw=1.2, alpha=0.5)


def get_y_normalised(value):
    """Return the y-coordinate of a value normalised to the current y-axis limits."""
    y_min, y_max = ax.get_ylim()
    return (value - y_min) / (y_max - y_min)


y0 = aai_annual.max() + 0.5
x0 = (pm10_start + pm10_end) / 2
ax.plot(x0, y0, color=RECORD_BAND_COLOR, marker=7, markersize=7, zorder=4)
# Elbow arrow from the inset's right edge (axes fraction) that runs across the
# gap and turns down onto the triangle marker at the bar top (data coords). The
# angle connectionstyle leaves the inset horizontally, then drops down with a
# rounded corner (rad=5) so the head points at the bar without overlapping it.
arrow_connection_style = "angle,angleA=0,angleB=90,rad=20"
ax.annotate(
    "",
    xy=(x0, y0 - 1),
    xycoords="data",
    xytext=(0.78, 0.94),
    textcoords="axes fraction",
    arrowprops=dict(
        arrowstyle="-",
        connectionstyle=arrow_connection_style,
        color=RECORD_BAND_COLOR,
        lw=1.2,
        shrinkA=2,
        shrinkB=6,
    ),
    zorder=5,
)

# --- PM10 inset --------------------------------------------------------------
# The white panel and connector make this a readable supporting detail rather
# than an unanchored second chart.
axin = ax.inset_axes([0.3, 0.56, 0.48, 0.4], zorder=6)
axin.set_facecolor("white")
axin.plot(pm10["time"], pm10["PM10_1d"], color=PM10_COLOR, lw=1.15, zorder=2)
axin.axhline(WHO_THRESHOLD, color=REFERENCE_COLOR, lw=0.75, ls=(0, (3, 2)), zorder=1)

exceedances = pm10[pm10["PM10_1d"] > WHO_THRESHOLD]
axin.scatter(
    exceedances["time"],
    exceedances["PM10_1d"],
    color=EXCEEDANCE_COLOR,
    edgecolor="white",
    linewidth=0.45,
    s=16,
    zorder=3,
)

axin.set_ylim(0, 88)
axin.set_yticks([0, WHO_THRESHOLD, 80])
axin.set_xticks([])
axin.set_ylabel("PM$_{10}$ (µg m$^{-3}$)", labelpad=2)
axin.set_title("Summer\n2023", loc="left", pad=1.5, y=0.97, x=0.02, va="top", alpha=0.5)
axin.tick_params(axis="y", width=0.65, length=2, pad=1.5)
for spine in axin.spines.values():
    spine.set_visible(True)
    spine.set_linewidth(0.65)
    spine.set_alpha(0.2)
axin.spines["left"].set_alpha(1.0)
axin.set_facecolor("0.98")

axin.text(
    0.98,
    WHO_THRESHOLD,
    "WHO guideline",
    transform=axin.get_yaxis_transform(),
    ha="right",
    va="bottom",
    fontsize="small",
    color=REFERENCE_COLOR,
)

# annotate the two peaks that exceed the WHO limit with their dates
for _, row in exceedances.iterrows():
    axin.annotate(
        row["time"].strftime("%-d %b"),
        xy=(row["time"], row["PM10_1d"]),
        xytext=(2, 0),
        textcoords="offset points",
        ha="left",
        va="center",
        fontsize="medium",
        color=EXCEEDANCE_COLOR,
        arrowprops=dict(arrowstyle="-", color=EXCEEDANCE_COLOR, lw=0),
    )


fig.subplots_adjust(left=0.20, right=0.985, bottom=0.17, top=0.95)
out = HERE / "fig8-pm10_aai.png"
fig.savefig(out, dpi=300, bbox_inches="tight", pad_inches=0.02)
print(f"saved {out}")
