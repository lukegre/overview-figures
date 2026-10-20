"""Shared paper style for the overview figures."""

from __future__ import annotations

import matplotlib.pyplot as plt


def set_paper_style(rc: dict | None = None) -> None:
    """Apply the shared paper style, then ``rc`` overrides (matplotlib rcParams).

    ``rc`` is typically a figure's ``plot.style`` block from its YAML config,
    e.g. ``{"font.size": 8, "xtick.labelsize": 6.6}``.
    """
    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.size": 8,
        "axes.linewidth": 0.5,
        "axes.titleweight": "normal",
        "xtick.major.size": 0,
        "ytick.major.size": 0,
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "savefig.facecolor": "white",
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
    })
    if rc:
        plt.rcParams.update(rc)
