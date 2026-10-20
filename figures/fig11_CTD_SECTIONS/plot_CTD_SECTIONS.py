"""2024 CTD and nutrient sections of the land and glacial fjord.

Four distance-depth sections (potential temperature, salinity, DIN, chlorophyll
fluorescence) are drawn for each fjord on shared colour scales so the two fjords
can be compared directly. Data flow: the GF24 hydrography workbook is filtered per
variable, interpolated inside the measured distance-depth domain, smoothed,
extended downwards to the seabed (bottom hold) and masked by the BedMachine v6
bathymetry from ``data/fjord_bathymetry``. The upper ``depth_split.depth_m``
metres are drawn on an expanded axis above the full water column.
All settings live in ``config_CTD_SECTIONS.yaml``.

Run from the repository root:

    MPLCONFIGDIR="$TMPDIR/mpl" .venv/bin/python fig11-CTD_SECTIONS/plot_CTD_SECTIONS.py
"""

from __future__ import annotations

import string
from pathlib import Path

import cmocean  # noqa: F401  (registers the cmo.* colour maps)
import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import xarray as xr
from matplotlib.colors import BoundaryNorm
from scipy.interpolate import (
    CloughTocher2DInterpolator,
    LinearNDInterpolator,
    NearestNDInterpolator,
)
from scipy.ndimage import gaussian_filter
from scipy.spatial import Delaunay, cKDTree

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
HYDROGRAPHY = HERE / cfg["inputs"]["hydrography"]
BATHYMETRY = cfg["inputs"]["bathymetry"]  # template, filled per fjord


def load_hydrography() -> pd.DataFrame:
    """Read the CTD / nutrient workbook and check that all needed columns exist."""
    df = pd.read_excel(HYDROGRAPHY, sheet_name=cfg["inputs"]["hydrography_sheet"])
    required = {
        "FEJORD",
        "Station_ID",
        "dist_from_1st",
        "Depth",
        "Bottom Depth",
        "Latitude",
        "Longitude",
    }
    required.update(v["column"] for v in plot["variables"])
    missing = sorted(required.difference(df.columns))
    if missing:
        raise ValueError(f"Hydrography workbook is missing columns: {missing}")
    return df


def resolve_x_limits(data: pd.DataFrame, configured: list[float] | str) -> list[float]:
    """Return configured limits or the exact finite distance extent in the data."""
    if configured != "data":
        return configured
    distances = pd.to_numeric(data["dist_from_1st"], errors="coerce").dropna()
    if distances.empty:
        raise ValueError("Cannot derive x-limits: transect has no finite distances")
    return [float(distances.min()), float(distances.max())]


def station_table(data: pd.DataFrame) -> pd.DataFrame:
    """Return one row per station, preserving the workbook's distance order."""
    return (
        data
        .groupby("Station_ID", sort=False)
        .agg(
            distance=("dist_from_1st", "first"),
            bottom=("Bottom Depth", "first"),
            latitude=("Latitude", "first"),
            longitude=("Longitude", "first"),
            max_depth=("Depth", "max"),
        )
        .reset_index()
        .sort_values("distance")
    )


def idw_scales(points: np.ndarray, options: dict) -> np.ndarray:
    """Estimate axis scales from mean station and within-profile spacing.

    Each profile contributes equally to the vertical estimate, so deep casts
    do not dominate. Horizontal units are km; vertical units are m.
    """
    distances = np.unique(points[:, 0])
    vertical_spacings = [
        np.diff(np.unique(points[points[:, 0] == distance, 1])).mean()
        for distance in distances
        if np.unique(points[points[:, 0] == distance, 1]).size > 1
    ]
    estimates = (
        np.diff(distances).mean() if distances.size > 1 else np.nan,
        np.mean(vertical_spacings) if vertical_spacings else np.nan,
    )
    scales = []
    for key, estimate in zip(("distance_scale_km", "depth_scale_m"), estimates):
        configured = options.get(key, "auto")
        value = estimate if configured == "auto" else float(configured)
        if not np.isfinite(value) or value <= 0:
            raise ValueError(f"idw.{key} must be positive; cannot estimate it from these data")
        scales.append(value)
    return np.asarray(scales)


def interpolate_idw(points, values, xx, zz, options, extrapolate=False):
    """Local IDW with elliptical distance and optional convex-hull masking."""
    scales = idw_scales(points, options)
    power = float(options.get("power", 2.0))
    neighbors = options.get("neighbors", 32)
    if not np.isfinite(power) or power <= 0:
        raise ValueError("idw.power must be finite and positive")
    if isinstance(neighbors, bool) or not isinstance(neighbors, int) or neighbors < 1:
        raise ValueError("idw.neighbors must be a positive integer")
    scaled = points / scales
    queries = np.column_stack((xx.ravel(), zz.ravel())) / scales
    inside = np.ones(len(queries), dtype=bool)
    if not extrapolate:
        inside = Delaunay(scaled).find_simplex(queries) >= 0
    field = np.full(len(queries), np.nan)
    tree = cKDTree(scaled)
    indices = np.flatnonzero(inside)
    # Bound memory independently of grid resolution and neighbor count.
    for start in range(0, len(indices), 8192):
        target = indices[start : start + 8192]
        distance, index = tree.query(queries[target], k=min(neighbors, len(points)))
        distance = distance.reshape(len(target), -1)
        index = index.reshape(len(target), -1)
        exact = distance[:, 0] == 0
        field[target[exact]] = values[index[exact, 0]]
        d = distance[~exact]
        # Relative weights avoid overflow close to an observed point.
        weights = (d[:, :1] / d) ** power
        field[target[~exact]] = np.sum(weights * values[index[~exact]], axis=1) / weights.sum(
            axis=1
        )
    return field.reshape(xx.shape)


def interpolate_section(
    data: pd.DataFrame,
    variable: str,
    xlim: list[float],
    ylim: list[float],
    grid_cfg: dict,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Interpolate scattered measurements onto the configured section grid."""
    clean = data[["dist_from_1st", "Depth", variable]].dropna()
    if len(clean) < 3:
        raise ValueError(f"Not enough observations to interpolate {variable}")

    # Duplicate x/depth pairs can occur after instrument merging; average them.
    clean = clean.groupby(["dist_from_1st", "Depth"], as_index=False)[variable].mean()
    x = np.arange(xlim[0], xlim[1] + grid_cfg["distance_step_km"], grid_cfg["distance_step_km"])
    z = np.arange(0, ylim[0] + grid_cfg["depth_step_m"], grid_cfg["depth_step_m"])
    xx, zz = np.meshgrid(x, z)
    points = clean[["dist_from_1st", "Depth"]].to_numpy(float)
    values = clean[variable].to_numpy(float)

    if grid_cfg["method"] == "idw":
        return (
            xx,
            zz,
            interpolate_idw(
                points,
                values,
                xx,
                zz,
                grid_cfg.get("idw", {}),
                extrapolate=grid_cfg.get("extrapolate", False),
            ),
        )

    if grid_cfg["method"] == "linear":
        interpolator = LinearNDInterpolator(points, values, fill_value=np.nan)
    elif grid_cfg["method"] == "cubic":
        # Clough-Tocher is the scattered-data analogue of bicubic
        # interpolation: a piecewise-cubic, continuously differentiable
        # surface that remains undefined outside the observations' convex hull.
        interpolator = CloughTocher2DInterpolator(points, values, fill_value=np.nan)
    elif grid_cfg["method"] == "nearest":
        interpolator = NearestNDInterpolator(points, values)
    else:
        raise ValueError("grid.method must be 'idw', 'cubic', 'linear', or 'nearest'")
    field = np.asarray(interpolator(xx, zz), dtype=float)

    if grid_cfg.get("clip_to_data_range", False):
        field = np.clip(field, np.nanmin(values), np.nanmax(values))

    if grid_cfg.get("extrapolate", False) and grid_cfg["method"] in {"cubic", "linear"}:
        missing = ~np.isfinite(field)
        nearest = NearestNDInterpolator(points, values)
        field[missing] = nearest(xx[missing], zz[missing])
    return xx, zz, field


def smooth_masked_field(
    field: np.ndarray,
    smoothing: dict | None,
    grid_cfg: dict,
) -> np.ndarray:
    """Gaussian-smooth valid cells while preserving the no-data mask."""
    if not smoothing:
        return field
    sigma = (
        smoothing.get("depth_m", 0) / grid_cfg["depth_step_m"],
        smoothing.get("distance_km", 0) / grid_cfg["distance_step_km"],
    )
    if max(sigma) <= 0:
        return field
    valid = np.isfinite(field)
    values = gaussian_filter(np.where(valid, field, 0.0), sigma=sigma, mode="nearest")
    weights = gaussian_filter(valid.astype(float), sigma=sigma, mode="nearest")
    smoothed = np.divide(values, weights, out=np.full_like(values, np.nan), where=weights > 1e-8)
    smoothed[~valid] = np.nan
    return smoothed


def extend_field_downward(
    field: np.ndarray, method: str, max_rows: int | None = None
) -> np.ndarray:
    """Extend each column below its deepest valid value using a bottom hold.

    The hold stops ``max_rows`` grid rows below the deepest value (None = seabed).
    """
    if method == "none":
        return field
    if method != "bottom_hold":
        raise ValueError("grid.vertical_extrapolation must be 'none' or 'bottom_hold'")

    extended = field.copy()
    for column in range(extended.shape[1]):
        valid_rows = np.flatnonzero(np.isfinite(extended[:, column]))
        if valid_rows.size:
            deepest = valid_rows[-1]
            stop = None if max_rows is None else deepest + 1 + max_rows
            extended[deepest + 1 : stop, column] = extended[deepest, column]
    return extended

def load_bathymetry(fjord_num: int) -> tuple[np.ndarray, np.ndarray]:
    """Read the BedMachine fjord section and smooth it with a centred rolling mean.

    Preserve the full profile and original distances, independent of cast
    depths and displayed x-limits.
    """
    path = HERE / BATHYMETRY.format(
        fjord_num=fjord_num, agg_method=analysis["bathymetry"]["agg_method"]
    )
    with xr.open_dataset(path) as section:
        distance = section["distance_to_glacier_km"].values
        depth = -section["bathymetry"].values  # positive down
    window = max(1, int(round(analysis["bathymetry"]["smooth_km"] / np.diff(distance).mean())))
    depth = pd.Series(depth).rolling(window, center=True, min_periods=1).mean().values
    return distance, depth


def style_section_axis(ax: plt.Axes) -> None:
    """Apply water background, spine and tick styling to one section axis."""
    ax.set_facecolor(plot["water_background"])
    for spine in ax.spines.values():
        spine.set_color(plot["spine_color"])
        spine.set_linewidth(plot["spine_width"])
    ax.tick_params(
        direction="out",
        length=plot["tick_length"],
        width=plot["tick_width"],
        color=plot["spine_color"],
    )


def draw_depth_break(shallow_ax: plt.Axes, deep_ax: plt.Axes) -> None:
    """Mark the change in vertical scale without adding a heavy divider."""
    split = plot["depth_split"]
    size = split["break_mark_size"]
    kwargs = {
        "color": plot["spine_color"],
        "clip_on": False,
        "lw": split["break_mark_line_width"],
        "transform": shallow_ax.transAxes,
        "zorder": 20,
    }
    shallow_ax.plot((-size, size), (-size, size), **kwargs)
    shallow_ax.plot((1 - size, 1 + size), (-size, size), **kwargs)
    kwargs["transform"] = deep_ax.transAxes
    deep_ax.plot((-size, size), (1 - size, 1 + size), **kwargs)
    deep_ax.plot((1 - size, 1 + size), (1 - size, 1 + size), **kwargs)


def plot_section_panel(
    shallow_ax: plt.Axes,
    deep_ax: plt.Axes,
    data: pd.DataFrame,
    transect: dict,
    variable: dict,
    bath: tuple[np.ndarray, np.ndarray],
    panel_letter: str,
    row: int,
) -> mpl.contour.QuadContourSet:
    """Draw one variable along one fjord on a split (shallow / deep) pair of axes."""
    axes_cfg = plot["axes"]
    bath_cfg = plot["bathymetry"]
    proc = analysis["variables"][variable["column"]]
    grid_cfg = analysis["grid"]
    filtered = data
    station_filter = proc.get("station_filter")
    if station_filter:
        filtered = filtered[filtered[station_filter["column"]] == station_filter["equals"]]

    interpolation_cfg = {
        **grid_cfg,
        "method": proc.get("interpolation_method", grid_cfg["method"]),
        "idw": {**grid_cfg.get("idw", {}), **proc.get("idw", {})},
    }
    xx, zz, field = interpolate_section(
        filtered,
        variable["column"],
        transect["xlim"],
        transect["ylim"],
        interpolation_cfg,
    )
    field = smooth_masked_field(field, proc.get("smoothing"), grid_cfg)
    field = extend_field_downward(
        field,
        grid_cfg.get("vertical_extrapolation", "none"),
        None
        if grid_cfg.get("vertical_extrapolation_max_m") is None
        else int(round(grid_cfg["vertical_extrapolation_max_m"] / grid_cfg["depth_step_m"])),
    )
    levels = np.linspace(variable["limits"][0], variable["limits"][1], variable["levels"])
    norm = BoundaryNorm(levels, ncolors=mpl.colormaps[variable["cmap"]].N, clip=False)
    bath_x, bath_depth = bath
    floor = transect["ylim"][0]
    stations = station_table(filtered)
    samples = None
    if variable.get("show_samples", False):
        samples = filtered[["dist_from_1st", "Depth", variable["column"]]].dropna()

    contours = []
    for ax in (shallow_ax, deep_ax):
        contours.append(
            ax.contourf(
                xx,
                zz,
                field,
                levels=levels,
                cmap=variable["cmap"],
                norm=norm,
                extend="both",
                antialiased=False,
                zorder=1,
            )
        )
        ax.fill_between(
            bath_x,
            bath_depth,
            floor,
            color=bath_cfg["fill_color"],
            linewidth=0,
            zorder=6,
        )
        ax.plot(
            bath_x,
            bath_depth,
            color=bath_cfg["line_color"],
            lw=bath_cfg["line_width"],
            zorder=6,
        )
        for station in stations.itertuples(index=False):
            ax.plot(
                [station.distance, station.distance],
                [0, station.max_depth],
                color=plot["station_line_color"],
                alpha=plot["station_line_alpha"],
                lw=plot["station_line_width"],
                zorder=3,
            )
        if samples is not None:
            ax.scatter(
                samples["dist_from_1st"],
                samples["Depth"],
                s=plot["sample_marker_size"],
                color=plot["sample_marker_color"],
                alpha=plot["sample_marker_alpha"],
                linewidths=0,
                zorder=4,
            )
        visible_xticks = [
            tick
            for tick in transect["xticks"]
            if transect["xlim"][0] <= tick <= transect["xlim"][1]
        ]
        ax.set_xticks(visible_xticks)
        # Set limits after ticks because Matplotlib may otherwise expand the
        # view to include a configured tick just outside the data extent.
        ax.set_xlim(*transect["xlim"])
        style_section_axis(ax)

    # Label the section in place
    label_cfg = bath_cfg["label"]
    deep_ax.text(
        label_cfg["x"],
        label_cfg["y"],
        label_cfg["text"],
        transform=deep_ax.transAxes,
        color=label_cfg["color"],
        fontsize=label_cfg["size"],
        ha="left",
        va="bottom",
        zorder=7,
    )

    shallow_ax.scatter(
        stations["distance"],
        np.zeros(len(stations)),
        s=plot["station_marker_size"],
        color=plot["station_marker_color"],
        edgecolors="white",
        linewidths=0.35,
        clip_on=False,
        zorder=8,
    )

    if row == axes_cfg["show_station_labels_on_row"]:
        for station in stations.itertuples(index=False):
            shallow_ax.annotate(
                station.Station_ID,
                (station.distance, 0),
                xytext=(0, axes_cfg["station_label_offset_m"]),
                textcoords="offset points",
                ha="center",
                va="bottom",
                rotation=axes_cfg["station_label_rotation"],
                fontsize=axes_cfg["station_label_size"],
                color=plot["station_marker_color"],
                clip_on=False,
            )

    split_depth = plot["depth_split"]["depth_m"]
    shallow_ax.set_ylim(split_depth, 0)
    shallow_ax.set_yticks(plot["depth_split"]["shallow_ticks"])
    deep_ax.set_ylim(floor, split_depth)
    deep_ticks = [split_depth, *[tick for tick in transect["yticks"] if tick > split_depth]]
    deep_ax.set_yticks(deep_ticks)
    shallow_ax.spines["bottom"].set_visible(False)
    deep_ax.spines["top"].set_visible(False)
    shallow_ax.tick_params(axis="x", bottom=False, labelbottom=False)
    draw_depth_break(shallow_ax, deep_ax)

    deep_ax.set_ylabel(transect.get("ylabel", axes_cfg["ylabel"]))
    # The lower axis occupies two-thirds of the combined panel. Its 75%
    # position is the visual centre of the complete split panel.
    deep_ax.yaxis.set_label_coords(-0.11, 0.75)
    if row == len(plot["variables"]) - 1:
        deep_ax.set_xlabel(axes_cfg["xlabel"])
    else:
        deep_ax.tick_params(labelbottom=False)

    xoff, yoff = plot["panel_label_offset"]
    shallow_ax.text(
        xoff,
        1 + yoff,
        panel_letter,
        transform=shallow_ax.transAxes,
        ha="left",
        va="bottom",
        fontsize=plot["panel_label_size"],
        fontweight=plot["panel_label_weight"],
        clip_on=False,
    )

    for ax in (shallow_ax, deep_ax):
        for side in ax.spines:
            ax.spines[side].set_zorder(10)

    return contours[0]


def main() -> None:
    set_paper_style(plot.get("style"))
    data = load_hydrography()

    fig = plt.figure(figsize=plot["figsize"], facecolor="white")
    grid = fig.add_gridspec(
        nrows=len(plot["variables"]),
        # The empty second column creates a wider gutter between transects;
        # the second transect and colour bar retain only the normal spacing.
        ncols=4,
        width_ratios=plot["width_ratios"],
        height_ratios=plot["height_ratios"],
        left=plot["left"],
        right=plot["right"],
        bottom=plot["bottom"],
        top=plot["top"],
        wspace=plot["wspace"],
        hspace=plot["hspace"],
    )

    baths = {t["data_name"]: load_bathymetry(t["fjord_num"]) for t in plot["transects"]}

    for row, variable in enumerate(plot["variables"]):
        row_contour = None
        for col, transect in enumerate(plot["transects"]):
            panel_grid = grid[row, col * 2].subgridspec(
                nrows=2,
                ncols=1,
                height_ratios=plot["depth_split"]["height_ratios"],
                hspace=plot["depth_split"]["hspace"],
            )
            shallow_ax = fig.add_subplot(panel_grid[0, 0])
            deep_ax = fig.add_subplot(panel_grid[1, 0], sharex=shallow_ax)
            subset = data[data["FEJORD"] == transect["data_name"]].copy()
            panel_transect = {
                **transect,
                "xlim": resolve_x_limits(subset, transect["xlim"]),
            }
            letter = string.ascii_lowercase[row * len(plot["transects"]) + col]
            row_contour = plot_section_panel(
                shallow_ax,
                deep_ax,
                subset,
                panel_transect,
                variable,
                baths[transect["data_name"]],
                letter,
                row,
            )
            if row == 0:
                shallow_ax.set_title(
                    transect["label"],
                    fontsize=plot["column_title_size"],
                    fontweight="bold",
                    pad=20,
                )

        cax = fig.add_subplot(grid[row, 3])
        cbar = fig.colorbar(row_contour, cax=cax, ticks=variable["ticks"], extendfrac=0.06)
        # BoundaryNorm colorbars otherwise add minor ticks at every contour
        # boundary, creating apparent double ticks beside the requested labels.
        cbar.minorticks_off()
        cbar.set_label(variable["colorbar_label"], labelpad=plot["colorbar_label_pad"])
        cbar.ax.tick_params(width=plot["tick_width"], length=plot["tick_length"])
        cbar.outline.set_linewidth(plot["spine_width"])
        cbar.outline.set_edgecolor(plot["spine_color"])

    fig.tight_layout()
    for fmt in output["formats"]:
        fig.savefig(
            HERE / f"{FIG_STEM}.{fmt}",
            dpi=output["dpi"],
            bbox_inches="tight",
            facecolor="white",
        )
    plt.close(fig)


if __name__ == "__main__":
    main()
