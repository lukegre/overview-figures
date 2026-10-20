"""Annual GOME-2B absorbing aerosol index (AAI) anomaly for Narsaq with a PM10 inset.

Main plot: annually integrated (summed) daily AAI anomaly for the area of
Narsaq, one bar per year. Inset: the summer-2023 Narsaq PM10 record with the
WHO guideline as a dashed line and the days above it annotated with their date.
A marker above the highest bar, joined to the inset by a connector, shows where
in the AAI record the PM10 measurements fall.

Data flow: inputs (PM10 text file, AAI csv) -> annual sums / decimal years ->
plot. All settings live in ``config_AEROSOL_ANOM.yaml``.

Run from the repository root:

    MPLCONFIGDIR="$TMPDIR/mpl" .venv/bin/python figures/fig8_AEROSOL_ANOM/plot_AEROSOL_ANOM.py
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
PM10_FILE = HERE / cfg["inputs"]["pm10"]
AAI_FILE = HERE / cfg["inputs"]["aai"]


def load_pm10() -> pd.DataFrame:
    """Daily PM10 with a datetime ``time`` column (LabVIEW seconds -> timestamps)."""
    pm10 = pd.read_csv(PM10_FILE, sep="\t")
    pm10["time"] = pd.Timestamp(analysis["labview_epoch"]) + pd.to_timedelta(
        pm10["mastertime_1d"], unit="s"
    )
    return pm10.dropna(subset=["PM10_1d"])


def load_aai_annual() -> pd.Series:
    """Daily AAI anomaly summed per calendar year."""
    aai = pd.read_csv(AAI_FILE, parse_dates=["time"])
    return aai.groupby(aai["time"].dt.year)["absorbing_aerosol_index"].sum()


def to_decimal_year(ts: pd.Timestamp) -> float:
    start = pd.Timestamp(ts.year, 1, 1)
    return ts.year + (ts - start) / (pd.Timestamp(ts.year + 1, 1, 1) - start)


def plot_aai_bars(ax, aai_annual: pd.Series) -> None:
    """Annual AAI anomaly, one bar per year."""
    p = plot["panels"]["aai"]
    years = aai_annual.index.to_numpy()
    ax.bar(years + 0.5, aai_annual.values, width=p["bar_width"], color=plot["colors"]["aai"], zorder=2)
    ax.axhline(0, color=plot["colors"]["reference"], lw=p["zero_line_width"], zorder=3)
    ax.set_ylabel(p["ylabel"])
    ax.set_xlim(years.min(), years.max() + 1)
    ax.set_ylim(*p["ylim"])
    ax.tick_params(axis="both", width=p["tick_width"], length=p["tick_length"])
    ax.hlines(
        ax.get_yticks(), *ax.get_xlim(), colors=p["grid_color"], lw=p["grid_width"], alpha=p["grid_alpha"]
    )


def plot_record_marker(ax, aai_annual: pd.Series, pm10: pd.DataFrame) -> None:
    """Marker above the highest bar at the PM10 record midpoint, joined to the inset."""
    m = plot["panels"]["marker"]
    c = plot["panels"]["connector"]
    color = plot["colors"]["exceedance"]
    y0 = aai_annual.max() + m["offset"]
    x0 = (to_decimal_year(pm10["time"].min()) + to_decimal_year(pm10["time"].max())) / 2
    ax.plot(x0, y0, color=color, marker=m["style"], markersize=m["size"], zorder=4)
    ax.annotate(
        "",
        xy=(x0, y0 - c["end_offset"]),
        xycoords="data",
        xytext=tuple(c["start_axes_fraction"]),
        textcoords="axes fraction",
        arrowprops=dict(
            arrowstyle="-",
            connectionstyle=c["connection_style"],
            color=color,
            lw=c["width"],
            shrinkA=c["shrink_start"],
            shrinkB=c["shrink_end"],
        ),
        zorder=5,
    )


def plot_pm10_inset(ax, pm10: pd.DataFrame) -> None:
    """PM10 record with the WHO guideline and dated exceedance days."""
    p = plot["panels"]["inset"]
    colors = plot["colors"]
    who = analysis["who_threshold_ugm3"]

    axin = ax.inset_axes(p["position"], zorder=6)
    axin.plot(pm10["time"], pm10["PM10_1d"], color=colors["exceedance"], lw=p["line_width"], zorder=2)
    axin.axhline(
        who, color=colors["reference"], lw=p["who_line_width"], ls=(p["who_line_dashes"][0], tuple(p["who_line_dashes"][1])), zorder=1
    )

    exceedances = pm10[pm10["PM10_1d"] > who]
    axin.scatter(
        exceedances["time"],
        exceedances["PM10_1d"],
        color=colors["exceedance"],
        edgecolor=p["point_edge_color"],
        linewidth=p["point_edge_width"],
        s=p["point_size"],
        zorder=3,
    )

    axin.set_ylim(*p["ylim"])
    axin.set_yticks([p["extra_yticks"][0], who, *p["extra_yticks"][1:]])
    axin.set_xticks([])
    axin.set_ylabel(p["ylabel"], labelpad=p["ylabel_pad"])
    axin.set_title(
        p["title"], loc="left", pad=p["title_pad"], x=p["title_xy"][0], y=p["title_xy"][1], va="top", alpha=p["title_alpha"]
    )
    axin.tick_params(axis="y", width=p["tick_width"], length=p["tick_length"], pad=p["tick_pad"])
    for spine in axin.spines.values():
        spine.set_visible(True)
        spine.set_linewidth(p["spine_width"])
        spine.set_alpha(p["spine_alpha"])
    axin.spines["left"].set_alpha(1.0)
    axin.set_facecolor(p["facecolor"])

    axin.text(
        p["who_label_x"],
        who,
        p["who_label"],
        transform=axin.get_yaxis_transform(),
        ha="right",
        va="bottom",
        fontsize=p["who_label_size"],
        color=colors["reference"],
    )

    # label each day above the WHO guideline with its date
    for _, row in exceedances.iterrows():
        axin.annotate(
            row["time"].strftime(p["peak_date_format"]),
            xy=(row["time"], row["PM10_1d"]),
            xytext=tuple(p["peak_label_offset"]),
            textcoords="offset points",
            ha="left",
            va="center",
            fontsize=p["peak_label_size"],
            color=colors["exceedance"],
            arrowprops=dict(arrowstyle="-", color=colors["exceedance"], lw=0),
        )


def main() -> None:
    set_paper_style(plot.get("style"))
    pm10 = load_pm10()
    aai_annual = load_aai_annual()

    fig, ax = plt.subplots(figsize=plot["figsize"])
    plot_aai_bars(ax, aai_annual)
    plot_record_marker(ax, aai_annual, pm10)
    plot_pm10_inset(ax, pm10)
    fig.subplots_adjust(**plot["margins"])

    for fmt in output["formats"]:
        fig.savefig(
            HERE / f"{FIG_STEM}.{fmt}", dpi=output["dpi"], bbox_inches="tight", pad_inches=output["pad_inches"]
        )


if __name__ == "__main__":
    main()
