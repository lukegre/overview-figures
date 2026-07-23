"""Transposed heatmap of the significant-trend pixel fraction.

Same data and styling as plot_heatmap.py, but with variables on the Y-axis and
seasons on the X-axis (the transpose of the default layout).
"""

import pathlib

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

PATH = pathlib.Path(__file__).parent
CSV = PATH / "data" / "era5-greenfjord-significant_trend_pixel_frac.csv"
SEASONS = ["DJF", "MAM", "JJA", "SON"]
# variables shown in original.png, plus 10m wind speed
VARIABLES = [
    "2m temperature",
    "Dewpoint temperature",
    "Total cloud cover",
    "Low cloud cover",
    "Cloud base height",
    "10m wind speed",
]


def load_net_fraction(path):
    """Return a (variable x season) frame of net signed significant-trend fraction."""
    df = pd.read_csv(path, header=[0, 1], index_col=0)
    df.columns.names = ["sign", "season"]
    # negative fractions are already stored as negative -> net = positive + negative
    net = df["negative"] + df["positive"]
    return net[SEASONS] * 100


def main():
    net = load_net_fraction(CSV)
    # keep only the requested variables, ordered most positive -> most negative
    net = net.loc[VARIABLES]
    net = net.loc[net.mean(axis=1).sort_values(ascending=False).index]

    # variables on the Y-axis, seasons on the X-axis (no transpose)
    data = net.to_numpy()
    nrows, ncols = data.shape

    fig, ax = plt.subplots(figsize=(4.5, 3), constrained_layout=True)
    ax.set_facecolor("0.95")
    # near-zero cells render as grey in coolwarm; mask them so they show cream instead
    cmap = plt.get_cmap("coolwarm").copy()
    cmap.set_bad("0.95")
    masked = np.ma.masked_where(np.abs(data) < 5, data)
    im = ax.imshow(masked, cmap=cmap, vmin=-100, vmax=100, aspect="auto")

    labels_wrapped = net.index.str.wrap(width=20, break_long_words=False).tolist()
    ax.set_xticks(range(ncols), net.columns)
    ax.set_yticks(range(nrows), labels_wrapped)
    ax.tick_params(length=0)
    for spine in ax.spines.values():
        spine.set_visible(True)
        spine.set_linewidth(0.5)
        spine.set_color("0.7")

    # thin gridlines between cells
    ax.set_xticks(np.arange(-0.5, ncols), minor=True)
    ax.set_yticks(np.arange(-0.5, nrows), minor=True)
    ax.grid(which="minor", color="white", linewidth=1.5)
    ax.tick_params(which="minor", length=0)

    # annotate each cell; hide near-zero values to reduce clutter
    for i in range(nrows):
        for j in range(ncols):
            v = data[i, j]
            if abs(v) < 5:
                continue
            ax.text(
                j,
                i,
                f"{abs(v):.0f}",
                ha="center",
                va="center",
                fontweight="bold",
                fontsize=7,
                color="white" if abs(v) > 60 else "black",
            )

    cbar = fig.colorbar(
        im,
        ax=ax,
        pad=0.02,
        aspect=15,
        drawedges=False,
    )
    cbar.set_ticks([-100, 0, 100])
    cbar.set_label("Significant trend fraction\n− decreasing / + increasing", labelpad=-10)
    [cbar.ax.spines[side].set_linewidth(0.5) for side in cbar.ax.spines]
    [cbar.ax.spines[side].set_color("0.75") for side in cbar.ax.spines]
    cbar.ax.yaxis.set_tick_params(length=0)

    fig.savefig(PATH / "fig5-era5_pixel_frac_transposed.png", dpi=200)
    print("wrote fig5-era5_pixel_frac_transposed.png")


if __name__ == "__main__":
    main()
