"""Sea-ice cover by fjord zone and annual ice / freshwater fluxes for three fjords.

The top-row boxplots show monthly sea-ice concentration (Inner / Mid / Outer
fjord zones) from the shared ice-cover workbook, with the mean coastal-ocean
ice cover as a dashed line. The bottom-row bars show the ice flux, annual
freshwater flux and ocean melt (ice flux times its tabulated ratio), each
summed over the glaciers of a fjord, from ``fluxes_overviewpaper_tabulated.csv``.
All settings live in ``config_FJORD_ICE_BARS.yaml``.

Run from the repository root:

    MPLCONFIGDIR="$TMPDIR/mpl" .venv/bin/python figures/fig9_FJORD_ICE_BARS/plot_FJORD_ICE_BARS.py
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from greenfjord.config import get_script_name, read_config
from greenfjord.viz import set_paper_style

# paths and names, derived from the script name (plot_<NAME>.py)
HERE = Path(__file__).resolve().parent
NAME = get_script_name(__file__)  # FJORD_ICE_BARS
FIG_STEM = f"fig_{NAME}"  # prefix of the PNG outputs

# config
cfg = read_config(HERE / f"config_{NAME}.yaml")
ana = cfg["analysis"]
plot = cfg["plot"]
output = cfg["output"]
ICE_COVER_PATH = HERE / cfg["inputs"]["ice_cover"]
FLUXES_PATH = HERE / cfg["inputs"]["fluxes"]

PANELS = plot["panels"]
POSITIONS = plot["x_positions"]
FONT_SIZE = plot["font_size"]


def read_fluxes() -> pd.DataFrame:
    """Return total ice, freshwater and ocean-melt flux (km3/yr) per fjord.

    Ocean melt is the ice flux times its tabulated ratio; empty cells count as 0.
    """
    table = pd.read_csv(FLUXES_PATH)
    ice = table[ana["csv_ice_flux_column"]].fillna(0)
    freshwater = table[ana["csv_freshwater_flux_column"]].fillna(0)
    melt_ratio = table[ana["csv_ocean_melt_ratio_column"]].fillna(0)

    fluxes = pd.DataFrame({
        "fjord": table[ana["csv_fjord_column"]],
        "ice": ice,
        "freshwater": freshwater,
        "ocean_melt": ice * melt_ratio,
    })
    return fluxes.groupby("fjord").sum()


def read_ice_cover() -> tuple[dict[str, list], float]:
    """Return the ice cover per fjord as one array per zone, and the mean coastal ice cover (%)."""
    data = pd.read_excel(ICE_COVER_PATH, sheet_name=ana["ice_cover_sheet"], header=[0, 1])

    ice_cover = {}
    for panel in PANELS:
        fjord = panel["workbook_fjord"]
        ice_cover[fjord] = [
            pd.to_numeric(data[(fjord, zone)], errors="coerce").dropna().to_numpy()
            for zone in ana["zones"]
        ]

    coastal = pd.to_numeric(data[tuple(ana["coastal_column"])], errors="coerce").dropna()
    return ice_cover, coastal.mean()


def style_axes(ax: plt.Axes, ylim: list, yticks: list) -> None:
    """Hide the top / right spines, soften the others and set the y range and ticks."""
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    for spine in ax.spines.values():
        spine.set_linewidth(plot["spine_linewidth"])
        spine.set_color(plot["spine_color"])
    ax.set_xlim(plot["xlim"])
    ax.set_ylim(ylim)
    ax.set_yticks(yticks)


def plot_ice_cover_boxplots(ax: plt.Axes, zones: list, coastal_mean: float, panel: dict) -> None:
    """Draw the Inner / Mid / Outer ice-cover boxplots with the coastal-mean reference line."""
    cfg_ice = plot["ice"]
    color = panel["color"]
    ax.boxplot(
        zones,
        positions=POSITIONS,
        widths=cfg_ice["box_width"],
        patch_artist=True,
        showfliers=True,
        boxprops={
            "facecolor": color,
            "alpha": cfg_ice["box_alpha"],
            "edgecolor": color,
            "linewidth": cfg_ice["box_linewidth"],
        },
        medianprops={"color": color, "linewidth": cfg_ice["box_linewidth"]},
        whiskerprops={"color": cfg_ice["whisker_color"], "linewidth": cfg_ice["whisker_linewidth"]},
        capprops={"color": "none"},
        flierprops={
            "marker": "o",
            "markersize": cfg_ice["flier_size"],
            "markerfacecolor": "none",
            "markeredgecolor": cfg_ice["flier_edgecolor"],
            "markeredgewidth": cfg_ice["flier_edgewidth"],
        },
    )
    ax.axhline(
        coastal_mean,
        color=cfg_ice["coastal_line_color"],
        linewidth=cfg_ice["coastal_line_width"],
        linestyle=(0, tuple(cfg_ice["coastal_line_dashes"])),
        zorder=0,
    )
    ax.set_xticks(
        POSITIONS,
        cfg_ice["xticklabels"],
        rotation=plot["xtick_rotation"],
        ha="center",
        fontsize=FONT_SIZE,
    )
    ax.set_title(panel["title"], fontsize=FONT_SIZE, loc="left")
    style_axes(ax, cfg_ice["ylim"], cfg_ice["yticks"])


def plot_flux_bars(ax: plt.Axes, values: tuple, panel: dict) -> None:
    """Draw the ice flux, freshwater flux and ocean-melt bars of one fjord."""
    cfg_flux = plot["flux"]
    ax.bar(
        POSITIONS,
        values,
        width=cfg_flux["bar_width"],
        color=panel["color"],
        edgecolor=cfg_flux["bar_edgecolor"],
        linewidth=cfg_flux["bar_linewidth"],
    )
    ax.set_xticks(
        POSITIONS,
        cfg_flux["xticklabels"],
        rotation=plot["xtick_rotation"],
        ha="center",
        fontsize=FONT_SIZE,
    )
    style_axes(ax, cfg_flux["ylim"], cfg_flux["yticks"])


def main() -> None:
    set_paper_style(plot.get("style"))
    fluxes = read_fluxes()
    ice_cover, coastal_mean = read_ice_cover()

    fig, axes = plt.subplots(2, 3, figsize=plot["figsize"], layout="constrained", sharey="row")

    for column, panel in enumerate(PANELS):
        plot_ice_cover_boxplots(
            axes[0, column], ice_cover[panel["workbook_fjord"]], coastal_mean, panel
        )
        values = fluxes.loc[panel["csv_fjord"], ["ice", "freshwater", "ocean_melt"]]
        plot_flux_bars(axes[1, column], tuple(values), panel)

        for row in range(2):
            axes[row, column].text(
                *plot["panel_letter_xy"][row],
                plot["panel_letters"][row][column],
                transform=axes[row, column].transAxes,
                fontsize=FONT_SIZE,
                va="top",
            )

    axes[0, 0].set_ylabel(plot["ice"]["ylabel"], fontsize=FONT_SIZE)
    axes[1, 0].set_ylabel(
        plot["flux"]["ylabel"], fontsize=FONT_SIZE, labelpad=plot["ylabel_labelpad_bottom"]
    )

    for fmt in output["formats"]:
        fig.savefig(HERE / f"{FIG_STEM}.{fmt}", dpi=output["dpi"], bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    main()
