"""Monthly sea-ice cover in the inner, mid and outer zones of three fjords.

Three stacked panels (Inner / Mid / Outer) show the monthly ice cover (%) of
Sermilik Ikersuaq, Tunulliarfik and Igalikup Kangerlua; the coastal-ocean
series is added to the Outer panel for reference. Data flow: ice-cover workbook
(``data/fjord_ice_regions_monthly``) -> one line per fjord and zone -> figure.
All settings live in ``config_FJORD_ICE_TIMESERIES.yaml``.

Run from the repository root:

    MPLCONFIGDIR="$TMPDIR/mpl" .venv/bin/python \
        figures/fig10_FJORD_ICE_TIMESERIES/plot_FJORD_ICE_TIMESERIES.py
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd

from greenfjord.config import get_script_name, read_config
from greenfjord.viz import set_paper_style

# paths and names, derived from the script name (plot_<NAME>.py)
HERE = Path(__file__).resolve().parent
NAME = get_script_name(__file__)  # FJORD_ICE_TIMESERIES
FIG_STEM = f"fig_{NAME}"  # prefix of the PNG / PDF outputs

# config
cfg = read_config(HERE / f"config_{NAME}.yaml")
plot = cfg["plot"]
output = cfg["output"]
ICE_COVER = HERE / cfg["inputs"]["ice_cover"]


def read_ice_cover() -> tuple[pd.Series, pd.DataFrame]:
    """Return the time axis and monthly ice cover (%) per (fjord, zone) column."""
    data = pd.read_excel(ICE_COVER, sheet_name="seaice_conc", header=[0, 1])
    time = pd.to_datetime(data.iloc[:, 0])
    coastal = tuple(plot["coastal_ocean"]["workbook_name"])
    columns = {
        (fjord["workbook_name"], region["workbook_name"]): pd.to_numeric(
            data[(fjord["workbook_name"], region["workbook_name"])], errors="coerce"
        )
        for fjord in plot["fjords"]
        for region in plot["regions"]
    }
    columns[coastal] = pd.to_numeric(data[coastal], errors="coerce")
    return time, pd.DataFrame(columns)


def style_axis(ax: plt.Axes) -> None:
    """Apply spines, y range / ticks, reference lines and tick style to a panel."""
    ref = plot["reference_lines"]
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    for spine in ax.spines.values():
        spine.set_linewidth(plot["spine_linewidth"])
        spine.set_color(plot["spine_color"])
    ax.set_ylim(plot["ylim"])
    ax.set_yticks(plot["yticks"])
    for level in ref["levels"]:
        ax.axhline(level, color=ref["color"], linewidth=ref["linewidth"], zorder=0)
    ax.set_ylabel(plot["ylabel"])
    ax.tick_params(**plot["tick_params"])


def plot_fjord_lines(ax: plt.Axes, time: pd.Series, ice_cover: pd.DataFrame, region: dict) -> None:
    """Draw one ice-cover line per fjord for the zone ``region`` and title the panel."""
    for fjord in plot["fjords"]:
        ax.plot(
            time,
            ice_cover[(fjord["workbook_name"], region["workbook_name"])],
            color=fjord["color"],
            linewidth=plot["fjord_linewidth"],
            label=fjord["label"],
        )
    style_axis(ax)
    ax.set_title(
        f"{region['panel_letter']}) {region['label']}",
        loc="left",
        pad=plot["title_pad"],
    )


def plot_coastal_ocean(ax: plt.Axes, time: pd.Series, ice_cover: pd.DataFrame) -> None:
    """Add the coastal-ocean reference line to ``ax``."""
    coastal = plot["coastal_ocean"]
    ax.plot(
        time,
        ice_cover[tuple(coastal["workbook_name"])],
        color=coastal["color"],
        linewidth=coastal["linewidth"],
        label=coastal["label"],
    )


def main() -> None:
    set_paper_style(plot.get("style"))
    time, ice_cover = read_ice_cover()

    fig, axes = plt.subplots(len(plot["regions"]), 1, figsize=plot["figsize"], sharex=True)
    for ax, region in zip(axes, plot["regions"], strict=True):
        plot_fjord_lines(ax, time, ice_cover, region)
    plot_coastal_ocean(axes[-1], time, ice_cover)

    axes[-1].legend(**plot["legend"])
    axes[-1].set_xlabel(plot["xlabel"])
    axes[-1].xaxis.set_major_locator(mdates.YearLocator(plot["x_tick_spacing_years"]))
    axes[-1].xaxis.set_major_formatter(mdates.DateFormatter(plot["x_tick_format"]))
    fig.tight_layout()

    for fmt in output["formats"]:
        fig.savefig(HERE / f"{FIG_STEM}.{fmt}", dpi=output["dpi"], bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    main()
