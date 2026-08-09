"""Shared figure style for print-quality report figures.

Colours come from a validated colour-blind-safe reference palette:
categorical hues in fixed order, a blue-red diverging pair with a grey midpoint,
recessive grid and axes, and text in ink colours (never in series colours).
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

INK = {"primary": "#0b0b0b", "secondary": "#52514e", "muted": "#898781"}
SURFACE = "#ffffff"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"

# Categorical slots, assigned in this order and never cycled.
CATEGORICAL = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6"]

# Five-point diverging scale for Likert answers: red arm, grey midpoint, blue arm.
LIKERT_5 = ["#b83230", "#ee9e9c", "#d9d8d3", "#86b6ef", "#1c5cab"]


def apply_style() -> None:
    """Set matplotlib defaults: readable sizes for print, light grid, no top/right spines."""
    plt.rcParams.update(
        {
            "figure.facecolor": SURFACE,
            "axes.facecolor": SURFACE,
            "axes.edgecolor": AXIS,
            "axes.labelcolor": INK["secondary"],
            "axes.titlecolor": INK["primary"],
            "axes.titlesize": 12,
            "axes.titleweight": "bold",
            "axes.labelsize": 10,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": True,
            "grid.color": GRID,
            "grid.linewidth": 0.6,
            "xtick.color": INK["secondary"],
            "ytick.color": INK["secondary"],
            "xtick.labelsize": 9,
            "ytick.labelsize": 9,
            "legend.frameon": False,
            "legend.fontsize": 9,
            "font.family": "DejaVu Sans",
            "savefig.dpi": 200,
            "savefig.bbox": "tight",
        }
    )


def save_figure(fig: plt.Figure, path: Path) -> Path:
    """Save a figure as PNG and close it."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path)
    plt.close(fig)
    return path
