"""Class-imbalance measures and class weights (Phase 5, used in Phase 6).

Weights are always computed from the labels of the rows a model is trained on (the
training split, or the training part of a cross-validation fold), never from
validation or test labels. No resampling is used: synthetic rows (e.g. SMOTE) would
add answers nobody gave.
"""

from __future__ import annotations

import pandas as pd


def imbalance_ratio(labels: pd.Series) -> float:
    """Largest class count divided by the smallest class count."""
    counts = labels.value_counts()
    return float(counts.max() / counts.min())


def class_weights(labels: pd.Series) -> dict[str, float]:
    """Balanced class weights: n / (k * count), so the average weight per row is 1."""
    counts = labels.value_counts()
    n, k = int(counts.sum()), len(counts)
    return {str(cls): n / (k * int(c)) for cls, c in counts.items()}


def needs_weights(labels: pd.Series, threshold: float) -> bool:
    """True if the imbalance ratio exceeds the threshold set in configs/split.yaml."""
    return imbalance_ratio(labels) > threshold
