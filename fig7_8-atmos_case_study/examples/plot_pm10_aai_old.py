"""
Recreate the PM10 / absorbing-aerosol-index figure as two stacked panels.

Panel a) (top)    Annually integrated GOME-2 absorbing aerosol index anomaly for
                  the area of Narsaq (2013-2024). The period covered by the PM10
                  record is shaded.
Panel b) (bottom) PM10 mass concentration in Narsaq (2023), red line, with the
                  WHO 45 ug/m3 threshold.

Caption (Fig. Y): a) Anomaly of the GOME-2 absorbing aerosol index compared to
the mean of 2013-2024 for the area of Narsaq. b) Estimated PM10 mass
concentration in Narsaq, Greenland, based on aerosol size distribution
measurements by a Fidas Frog (density 1.5 g/cm3). The horizontal black line
indicates the 45 ug/m3 threshold by WHO.
"""

from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd

HERE = Path(__file__).parent
WHO_THRESHOLD = 45.0  # ug/m3

plt.style.use(str(HERE / "figure.mplstyle"))

# --- PM10 daily record -------------------------------------------------------
# mastertime_1d is LabVIEW time: seconds since 1904-01-01 (the Fidas/LabVIEW
# epoch). This maps the first sample to 2023-06-21.
pm10 = pd.read_csv(HERE / "PM10-concentrations.txt", sep="\t")
pm10["time"] = pd.Timestamp("1904-01-01") + pd.to_timedelta(pm10["mastertime_1d"], unit="s")
pm10 = pm10.dropna(subset=["PM10_1d"])

# --- Absorbing aerosol index -------------------------------------------------
# Daily point estimates -> annual integral (sum) per year.
aai = pd.read_csv(HERE / "greenfjord_timeseries_aai_anom_gome2b_2013_2024.csv",
                  parse_dates=["time"])
aai_annual = aai.groupby(aai["time"].dt.year)["absorbing_aerosol_index"].sum()
years = aai_annual.index.to_numpy()


def to_decimal_year(ts):
    start = pd.Timestamp(ts.year, 1, 1)
    return ts.year + (ts - start) / (pd.Timestamp(ts.year + 1, 1, 1) - start)


pm10_start = to_decimal_year(pm10["time"].min())
pm10_end = to_decimal_year(pm10["time"].max())

# --- Figure ------------------------------------------------------------------
# Width from figure.mplstyle (7.5 in); taller to fit the two stacked panels.
fig, (ax_aai, ax_pm10) = plt.subplots(
    2, 1, figsize=(plt.rcParams["figure.figsize"][0], 6))

# Panel a) top: annual AAI anomaly, one bar per year
ax_aai.bar(years + 0.5, aai_annual.values, width=0.6, color="#1f6fb4",
           zorder=2)
# highlight the period the PM10 record covers
ax_aai.axvspan(pm10_start, pm10_end, color="#f0a020", alpha=0.35, lw=0,
               zorder=0, label="PM10 record")
ax_aai.axhline(0, color="black", lw=0.9, zorder=3)
ax_aai.set_ylabel("Absorbing aerosol index\n(annual anomaly)")
ax_aai.set_xlim(years.min(), years.max() + 1)
ax_aai.margins(y=0.15)
ax_aai.legend(loc="upper left", handlelength=1.0)
ax_aai.text(0.02, 0.88, "a)", transform=ax_aai.transAxes,
            fontweight="bold", fontsize=13)

# Panel b) bottom: PM10 record
ax_pm10.plot(pm10["time"], pm10["PM10_1d"], color="red", lw=1.4)
ax_pm10.axhline(WHO_THRESHOLD, color="black", lw=1.0)
ax_pm10.set_ylabel("PM10 (µg / m$^{-3}$)")
ax_pm10.set_ylim(0, None)
ax_pm10.xaxis.set_major_locator(mdates.DayLocator(bymonthday=[21, 1, 11]))
ax_pm10.xaxis.set_major_formatter(mdates.DateFormatter("%d.%m.%Y"))
ax_pm10.text(0.02, 0.88, "b)", transform=ax_pm10.transAxes,
             fontweight="bold", fontsize=13)

fig.tight_layout()
out = HERE / "concentrations_recreated.png"
fig.savefig(out, dpi=200, bbox_inches="tight")
print(f"saved {out}")
