"""Metrics and trivial baselines for every target (evaluation criteria A-D of the brief).

The same functions are used for cross-validation, validation (Phase 6) and test (Phase 7).
"""

from __future__ import annotations

from typing import Any

import numpy as np
from scipy import stats
from sklearn import metrics as skm

PRIMARY = {
    "zscore": ("mae", "lower"),
    "zscore_band": ("macro_f1", "higher"),
    "university_group": ("macro_f1", "higher"),
    "degree_category": ("macro_f1", "higher"),
}
ORDINAL = {"zscore_band"}


def regression_metrics(y: np.ndarray, pred: np.ndarray) -> dict[str, float]:
    """MAE, RMSE, R-squared and Spearman correlation."""
    return {
        "mae": float(skm.mean_absolute_error(y, pred)),
        "rmse": float(np.sqrt(skm.mean_squared_error(y, pred))),
        "r2": float(skm.r2_score(y, pred)),
        "spearman": float(stats.spearmanr(y, pred).statistic) if np.std(pred) > 0 else 0.0,
    }


def expected_calibration_error(y: np.ndarray, proba: np.ndarray, bins: int = 10) -> float:
    """Top-label expected calibration error with equal-width confidence bins."""
    confidence = proba.max(axis=1)
    correct = (proba.argmax(axis=1) == y).astype(float)
    edges = np.linspace(0, 1, bins + 1)
    ece = 0.0
    for low, high in zip(edges[:-1], edges[1:], strict=True):
        in_bin = (confidence > low) & (confidence <= high)
        if in_bin.any():
            ece += in_bin.mean() * abs(correct[in_bin].mean() - confidence[in_bin].mean())
    return float(ece)


def reliability_curve(y: np.ndarray, proba: np.ndarray, bins: int = 10) -> list[dict[str, float]]:
    """Per-bin mean confidence, accuracy and count for a reliability plot."""
    confidence = proba.max(axis=1)
    correct = (proba.argmax(axis=1) == y).astype(float)
    edges = np.linspace(0, 1, bins + 1)
    rows = []
    for low, high in zip(edges[:-1], edges[1:], strict=True):
        in_bin = (confidence > low) & (confidence <= high)
        if in_bin.any():
            rows.append(
                {
                    "low": low,
                    "high": high,
                    "confidence": float(confidence[in_bin].mean()),
                    "accuracy": float(correct[in_bin].mean()),
                    "count": int(in_bin.sum()),
                }
            )
    return rows


def brier_score(y: np.ndarray, proba: np.ndarray) -> float:
    """Multi-class Brier score: mean over rows of the squared error summed over classes."""
    onehot = np.eye(proba.shape[1])[y]
    return float(((proba - onehot) ** 2).sum(axis=1).mean())


def classification_metrics(
    y: np.ndarray, proba: np.ndarray, ordinal: bool, ece_bins: int = 10
) -> dict[str, Any]:
    """All classification metrics of the brief for one target.

    Args:
        y: True class indices (0..k-1).
        proba: Predicted probabilities, shape (n, k), rows summing to 1.
        ordinal: True for ordered classes (adds QWK and within-one-band accuracy).
        ece_bins: Number of bins for the calibration error.
    """
    k = proba.shape[1]
    labels = np.arange(k)
    pred = proba.argmax(axis=1)
    precision, recall, _, _ = skm.precision_recall_fscore_support(
        y, pred, labels=labels, zero_division=0
    )
    out: dict[str, Any] = {
        "macro_f1": float(skm.f1_score(y, pred, labels=labels, average="macro", zero_division=0)),
        "balanced_accuracy": float(skm.balanced_accuracy_score(y, pred)),
        "accuracy": float(skm.accuracy_score(y, pred)),
        "per_class_precision": precision.round(4).tolist(),
        "per_class_recall": recall.round(4).tolist(),
        "confusion_matrix": skm.confusion_matrix(y, pred, labels=labels).tolist(),
        "log_loss": float(skm.log_loss(y, np.clip(proba, 1e-12, 1), labels=labels)),
        "brier": brier_score(y, proba),
        "ece": expected_calibration_error(y, proba, ece_bins),
    }
    present = np.unique(y)
    try:
        if len(present) == k:
            out["roc_auc_ovr_macro"] = float(
                skm.roc_auc_score(y, proba, multi_class="ovr", average="macro", labels=labels)
            )
        else:
            out["roc_auc_ovr_macro"] = float("nan")
    except ValueError:
        out["roc_auc_ovr_macro"] = float("nan")
    if ordinal:
        out["qwk"] = float(skm.cohen_kappa_score(y, pred, weights="quadratic"))
        out["within_one_accuracy"] = float((np.abs(pred - y) <= 1).mean())
    return out


def baseline_predictions(
    y_train: np.ndarray, n_rows: int, kind: str, n_classes: int | None = None
) -> np.ndarray:
    """Trivial reference: training mean (regression) or training class frequencies.

    For classification the returned probabilities are the training class shares for every
    row; their arg-max is the majority class, so the label baseline is included.
    """
    if kind == "regression":
        return np.full(n_rows, float(np.mean(y_train)))
    counts = np.bincount(y_train, minlength=n_classes).astype(float)
    return np.tile(counts / counts.sum(), (n_rows, 1))


def target_metrics(target: str, y: np.ndarray, prediction: np.ndarray) -> dict[str, Any]:
    """Dispatch to the right metric set for a target."""
    if target == "zscore":
        return regression_metrics(y, prediction)
    return classification_metrics(y, prediction, ordinal=target in ORDINAL)


def primary_value(target: str, metrics: dict[str, Any]) -> float:
    """The primary metric of a target, oriented so that HIGHER is always better."""
    name, direction = PRIMARY[target]
    value = float(metrics[name])
    return -value if direction == "lower" else value
