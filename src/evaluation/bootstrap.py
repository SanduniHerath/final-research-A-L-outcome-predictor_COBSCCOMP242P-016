"""Percentile bootstrap confidence intervals, single and paired (Phase 2 rules).

Paired means both predictions are scored on the same resampled rows, so the noise
common to both cancels out in the difference.
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np

Metric = Callable[[np.ndarray, np.ndarray], float]


def bootstrap_ci(
    y: np.ndarray,
    pred: np.ndarray,
    metric: Metric,
    n: int = 2000,
    level: float = 0.95,
    seed: int = 0,
) -> tuple[float, float, float]:
    """Return (point estimate, lower, upper) of ``metric`` by resampling rows."""
    rng = np.random.default_rng(seed)
    point = metric(y, pred)
    values = []
    for _ in range(n):
        idx = rng.integers(0, len(y), len(y))
        values.append(metric(y[idx], pred[idx]))
    tail = (1 - level) / 2 * 100
    low, high = np.nanpercentile(values, [tail, 100 - tail])
    return float(point), float(low), float(high)


def paired_bootstrap_diff(
    y: np.ndarray,
    pred_a: np.ndarray,
    pred_b: np.ndarray,
    metric: Metric,
    n: int = 2000,
    level: float = 0.95,
    seed: int = 0,
) -> tuple[float, float, float]:
    """Return (metric(a) - metric(b), lower, upper) with both scored on the same resamples."""
    rng = np.random.default_rng(seed)
    point = metric(y, pred_a) - metric(y, pred_b)
    diffs = []
    for _ in range(n):
        idx = rng.integers(0, len(y), len(y))
        diffs.append(metric(y[idx], pred_a[idx]) - metric(y[idx], pred_b[idx]))
    tail = (1 - level) / 2 * 100
    low, high = np.nanpercentile(diffs, [tail, 100 - tail])
    return float(point), float(low), float(high)
