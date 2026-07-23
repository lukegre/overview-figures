"""Decadal temperature figure for the GreenFjord large-scale trends analysis.

Produces a single multi-panel figure combining:

    (a) the regional mask map, using the code from ``region_plots.ipynb``
        (``other._plot_ocean_region_map`` + land / ice-sheet / AOI overlays)
    (b) decadal Sea Surface Temperature (SST) as small per-region bar plots
    (c) decadal 2 m air temperature (ERA5 t2m) as small subset bar plots

Each small bar plot shows the decadal **mean** (bar) with the **standard
deviation** as error bars. Bar colours are taken from the matplotlib default
cycle (= tab10) so they match the regional-mask map:
Oceanic=C0, Southwest=C1, Central western=C2, South Eastern=C3, Ice=C4.
Within a region the bars fade from light (1980s) to solid (2010s) so the decade
progression reads left-to-right while the hue keeps the region identity.

Data / dependencies:
    - data/decade_distribution_stats.xlsx      (in this folder; sheets SST, ERA5)
    - greenfjord_trends.data.other             (builds the regional mask from
                                                GEBCO bathymetry on S3)
    - <repo>/data/era5-land-ocean-ice.gpkg     (land / ocean / ice polygons,
                                                produced by examples/region_plots.ipynb)

The mask is cached to ``data/regions_mask.nc`` so reruns don't re-hit S3.
Delete that file to force a rebuild.

Run (use the project venv so the package and its deps are importable):
    ../../.venv/bin/python plot_sst_t2m_trends.py
"""

from __future__ import annotations

from pathlib import Path

import dotenv
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import to_rgb
from matplotlib.patches import Patch

HERE = Path(__file__).resolve().parent
REPO = Path(dotenv.find_dotenv("pyproject.toml")).parent

XLSX = HERE / "data" / "decade_distribution_stats.xlsx"
MASK_CACHE = HERE / "data" / "regions_mask.nc"
AOI_GPKG = REPO / "data" / "era5-land-ocean-ice.gpkg"
OUT_PNG = HERE / "fig2-sst_t2m_trends.png"
OUT_PDF = HERE / "fig2-sst_t2m_trends.pdf"

DECADES = [1980, 1990, 2000, 2010]
DECADE_LABELS = ["1980", "1990", "2000", "2010"]

# ---------------------------------------------------------------------------
# Colours: matched to the regional-mask map. get_ocean_regions() writes mask
# values 1..4 for Oceanic, Southwest, Central western, South Eastern, which the
# project plots with colors=['C0','C1','C2','C3', ...].
# ---------------------------------------------------------------------------
SST_ORDER = ["Oceanic", "Southwest", "South Eastern"]
SST_COLORS = {
    "Oceanic": "C0",  # blue
    "Southwest": "C1",  # orange
    "Central western": "C2",  # green
    "South Eastern": "C3",  # red
}

# ERA5 subsets mapped onto the same visual language as the regional map. The
# workbook's ``ocean`` series is the Southwest subset in the paper figure.
T2M_ORDER = ["land", "ocean", "ice"]
T2M_COLORS = {"land": "0.55", "ocean": "C1", "ice": "C4"}
T2M_LABELS = {"land": "Land", "ocean": "Southwest", "ice": "Ice"}

LAND_COLOR = "0.95"  # light grey for the AOI land mask


def set_paper_style() -> None:
    """Apply a compact, publication-oriented Matplotlib style."""
    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.size": 8,
        "axes.titlesize": 8.5,
        "axes.labelsize": 8,
        "axes.linewidth": 0.5,
        "axes.titleweight": "normal",
        "xtick.labelsize": 7.2,
        "ytick.labelsize": 7.2,
        "xtick.major.size": 3,
        "ytick.major.size": 3,
        "xtick.major.width": 0.6,
        "ytick.major.width": 0.6,
        "legend.fontsize": 7.2,
        "legend.frameon": False,
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "savefig.facecolor": "white",
        "savefig.dpi": 300,
        # Keep text editable when the PDF is placed in illustration software.
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
    })


def tint(color: str, strength: float) -> tuple[float, float, float]:
    """Return an opaque tint of ``color``; 0 is white and 1 is unchanged."""
    rgb = np.asarray(to_rgb(color))
    return tuple(1 - strength * (1 - rgb))


def load_stats(sheet: str) -> pd.DataFrame:
    """Read one sheet of the stats workbook into a tidy dataframe.

    The workbook has three header rows and leaves the decade blank except on the
    first row of each group, so we skip the headers and forward-fill the decade.
    """

    df = pd.read_excel(
        XLSX,
        sheet_name=sheet,
        skiprows=3,
        header=None,
        names=["decade", "region", "median", "mean", "std"],
    )
    df["decade"] = df["decade"].ffill().astype(int)
    return df


def get_region_mask():
    """Return the regional-mask DataArray, building it via other.py if needed.

    Uses greenfjord_trends.data.other.get_ocean_regions (bathymetry-based) and
    caches the result to a local netCDF so reruns are offline and fast. The
    ``names`` attribute is a list, which netCDF can't store, so it is round-
    tripped through a '|'-joined string.
    """
    import xarray as xr

    if MASK_CACHE.exists():
        mask = xr.open_dataset(MASK_CACHE)["region"]
    else:
        from greenfjord_trends.data import other

        mask = other.get_ocean_regions()
        mask.assign_attrs(names="|".join(mask.attrs["names"])).to_netcdf(MASK_CACHE)

    names = mask.attrs.get("names")
    if isinstance(names, str):
        names = names.split("|")
    mask.attrs["names"] = names
    return mask.rio.write_crs("epsg:4326")


def get_overlays(mask):
    """Load the land/ocean/ice polygons and derive the ocean-region boundaries."""
    import geopandas as gpd
    import xarray_raster_vector  # noqa: F401 - registers the .rv accessor

    gpd.options.io_engine = "pyogrio"
    df = gpd.read_file(AOI_GPKG).set_index("index")
    df_ocean_bounds = mask.astype(int).rv.to_polygons().iloc[2:]
    return df, df_ocean_bounds


def _plot_ocean_region_map(da, **kwargs):
    import numpy as np

    from greenfjord_trends.viz.geo import plot_map

    da = da.where(lambda x: x > 0)
    x, y = da.x.isel(x=-120), da.y.isel(y=-2)
    da.loc[y, x] += 1

    x, y = da.x.isel(x=-121), da.y.isel(y=-2)
    da.loc[y, x] += 2

    vmax = da.loc[y, x].item() + 1

    props = dict(
        aspect=1.5,
        size=4,
        levels=np.arange(0.5, vmax),
        colors=["C0", "C1", "C2", "C3", "C4", "none"],
        plot_type="contourf",
        cbar_kwargs=dict(drawedges=True, aspect=10),
    )
    props |= kwargs
    fig, ax, img = plot_map(da, **props)

    ax.set_aspect(2)
    ax.set_title("Regional mask")

    img.colorbar.set_ticks(np.mgrid[1:vmax])
    labels = da.names[1:] + ["Ice sheet", "GreenFjord"]
    img.colorbar.set_ticklabels(labels)
    img.colorbar.set_label("")
    img.colorbar.ax.tick_params(length=0)

    fig.metadata = dict(
        title="Ocean regions in the GreenFjord domain",
        description=(
            "Regions are defined based on bathymetry and distance to coast. "
            "Shelf is defined as bathymetry > -500 m and distance to coast > 4 km. "
            "Open ocean is defined as bathymetry < -500 m and distance to coast > 10 km."
        ),
        data_source="https://www.gebco.net/data_and_products/gridded_bathymetry_data/",
        func="src.clusters.ocean.ocean_mask",
    )

    return fig, ax, img


def plot_ocean_regions(ax, mask, df, df_ocean_bounds, cax=None, **kwargs):
    """Draw the regional mask into ``ax``.

    Ported from ``region_plots.ipynb::plot_ocean_regions``: the bathymetry-based
    ocean regions (via ``other._plot_ocean_region_map``) plus the GreenFjord AOI
    (land) outline, the ice-sheet box and the ocean boundary. The matplotlib
    default cycle is tab10, matching the notebook's ``sns.set_palette('tab10')``.

    ``cax`` is the axes the categorical colorbar is drawn into; passing a wide,
    short axes at the bottom of the figure makes the legend horizontal.
    """
    from greenfjord_trends.data import other

    # x > 0 keeps the Oceanic region (value 1, blue) on the map; the notebook
    # used x > 1 to drop it.
    fig, ax, img = other._plot_ocean_region_map(
        mask.where(lambda x: x > 0),
        ax=ax,
        alpha=0.8,
        cbar_kwargs=dict(cax=cax, orientation="horizontal", drawedges=True),
        **kwargs,
    )
    df_ocean_bounds.boundary.plot(ax=ax, color="w", lw=0.35)

    df.loc[["land"]].plot(ax=ax, color=LAND_COLOR, lw=1.1, zorder=30, alpha=0.1)
    df.loc[["land"]].plot(ax=ax, color="none", lw=1.1, zorder=30, alpha=1)

    df.loc[["ice"]].plot(ax=ax, color=plt.cm.tab10(4), lw=1.1, ls=":", alpha=0.6, zorder=10)
    df.loc[["ice"]].boundary.plot(ax=ax, color="#333333", lw=1.1, ls=":", zorder=10)

    df.loc[["ocean"]].boundary.plot(ax=ax, color="#333333", lw=1.1, ls=":", zorder=10)

    ax.get_children()[1].set_facecolor(LAND_COLOR)

    ax.set_ylabel("")
    ax.set_xlabel("")
    ax.set_title("")
    ax.set_xticks([])
    ax.set_yticks([])

    # Replace the dense categorical colorbar with a compact two-column legend.
    # This avoids angled labels and remains legible at a two-column paper width.
    if cax is not None:
        cax.clear()
        cax.axis("off")
        handles = [
            Patch(fc="C0", ec="none", label="Oceanic"),
            Patch(fc="C1", ec="none", label="Southwest"),
            Patch(fc="C2", ec="none", label="Central western"),
            Patch(fc="C3", ec="none", label="South Eastern"),
            Patch(fc="C4", ec="#333333", lw=1, ls=":", label="Ice sheet"),
            Patch(fc="0.9", ec="k", lw=1, label="GreenFjord"),
        ]
        cax.legend(
            handles=handles,
            loc="upper left",
            ncol=2,
            mode="expand",
            borderaxespad=0,
            handlelength=1.7,
            handleheight=0.8,
            handletextpad=0.45,
            columnspacing=0.8,
            labelspacing=0.45,
        )

    return ax


def plot_region_bars(axes, df, order, colors, labels, letters, zero_line_zorder=1):
    """Small-multiples bars: one mini-panel per region, one bar per decade.

    Each panel is annotated in the ``region_plots``/notebook style: a left-
    aligned ``"x) Name"`` title placed *inside* the axes near the top
    (``loc='left', y=0.9, x=0.02``). Returns the (ymin, ymax) span (incl. error
    bars) so the caller can share it.
    """
    lo, hi = np.inf, -np.inf
    strengths = np.linspace(0.45, 0.95, len(DECADES))
    x = np.arange(len(DECADES))

    for ax, name, letter in zip(axes, order, letters):
        sub = df[df["region"] == name].set_index("decade").reindex(DECADES)
        means = sub["mean"].to_numpy(dtype=float)
        stds = sub["std"].to_numpy(dtype=float)
        base = colors[name]
        bar_colors = [tint(base, strength) for strength in strengths]

        ax.bar(
            x,
            means,
            width=0.78,
            color=bar_colors,
            edgecolor=tint(base, 0.78),
            linewidth=0.55,
            yerr=stds,
            error_kw=dict(
                ecolor="0.25",
                elinewidth=0.8,
                capsize=2,
                capthick=0.8,
                alpha=0.6,
            ),
            zorder=2,
        )
        ax.axhline(0, color="0.3", lw=0.65, zorder=zero_line_zorder)
        ax.set_title(rf"$\bf{{{letter}}}$  {labels.get(name, name)}", loc="left", pad=3)
        ax.set_xticks(x)
        ax.set_xticklabels(DECADE_LABELS, fontsize=6.8)
        ax.tick_params(axis="x", pad=2)
        for spine in ("top", "right"):
            ax.spines[spine].set_visible(False)

        lo = min(lo, np.nanmin(means - stds))
        hi = max(hi, np.nanmax(means + stds))

    return lo, hi


def main() -> None:
    set_paper_style()
    sst = load_stats("SST")
    t2m = load_stats("ERA5")
    mask = get_region_mask()
    df_overlay, df_ocean_bounds = get_overlays(mask)

    # Eight-inch total width for the target two-column journal layout.
    fig = plt.figure(figsize=(8, 3.5))
    outer = fig.add_gridspec(
        1,
        2,
        width_ratios=[1.02, 1.68],
        wspace=0.18,
        left=0.045,
        right=0.99,
        top=0.965,
        bottom=0.09,
    )
    left = outer[0].subgridspec(2, 1, height_ratios=[1, 0.24], hspace=0.04)
    ax_map = fig.add_subplot(left[0])
    ax_map.set_anchor("N")
    cax = fig.add_subplot(left[1])

    right = outer[1].subgridspec(2, 1, height_ratios=[1, 1], hspace=0.48)
    sst_gs = right[0].subgridspec(1, 3, wspace=0.16)
    t2m_gs = right[1].subgridspec(1, 3, wspace=0.16)
    sst_axes = [fig.add_subplot(sst_gs[i]) for i in range(3)]
    t2m_axes = [fig.add_subplot(t2m_gs[i]) for i in range(3)]

    # (a) map — code ported from region_plots.ipynb.
    # The project's plot_map() draws into the *current* axes when `size` is
    # given (the notebook relied on plt.axes(...) for this), so make the map
    # panel current before calling.
    plt.sca(ax_map)
    plot_ocean_regions(
        ax_map,
        mask,
        df_overlay,
        df_ocean_bounds,
        cax=cax,
        size=None,
        aspect=None,
        land_color=LAND_COLOR,
    )
    for spine in ax_map.spines.values():
        spine.set_visible(True)
        spine.set_linewidth(0.5)
        spine.set_color("0.2")
    ax_map.set_title(r"$\bf{a}$  Regional mask", loc="left", pad=3)

    # (b–d) SST bars per ocean region; (e–g) T2m bars per ERA5 subset. Panels
    # are lettered in the notebook's in-axes style; the y-axis label carries the
    # variable so no separate row heading is needed.
    lo, hi = plot_region_bars(
        sst_axes,
        sst,
        SST_ORDER,
        SST_COLORS,
        labels={n: n for n in SST_ORDER},
        letters=["b", "c", "d"],
    )
    span = hi - lo
    for i, ax in enumerate(sst_axes):
        ax.set_ylim(0, hi + 0.08 * span)
        ax.set_yticks([0, 2, 4, 6])
        if i:
            ax.tick_params(labelleft=False)
    sst_axes[0].set_ylabel("SST (°C)")

    lo, hi = plot_region_bars(
        t2m_axes,
        t2m,
        T2M_ORDER,
        T2M_COLORS,
        labels=T2M_LABELS,
        letters=["e", "f", "g"],
        zero_line_zorder=3,
    )
    span = hi - lo
    for i, ax in enumerate(t2m_axes):
        ax.set_ylim(lo - 0.05 * span, hi + 0.08 * span)
        ax.set_yticks([-15, -10, -5, 0, 5])
        ax.set_xlabel("Decade")
        if i:
            ax.tick_params(labelleft=False)
    t2m_axes[0].set_ylabel("2 m air temperature (°C)")

    # The geographic aspect ratio makes the realised map shorter than its grid
    # cell. Place its key directly below the drawn map to avoid a dead band.
    fig.canvas.draw()
    map_pos = ax_map.get_position()
    legend_height = 0.5 / fig.get_figheight()
    legend_gap = 0.1 / fig.get_figheight()
    cax.set_position([
        map_pos.x0,
        map_pos.y0 - legend_gap - legend_height,
        map_pos.width,
        legend_height,
    ])

    fig.savefig(OUT_PNG, dpi=300, bbox_inches="tight")
    # fig.savefig(OUT_PDF, bbox_inches="tight")


if __name__ == "__main__":
    main()
