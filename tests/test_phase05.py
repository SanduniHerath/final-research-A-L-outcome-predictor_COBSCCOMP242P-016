"""Tests for class weights and cross-validation folds (Phase 5)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.data.imbalance import class_weights, imbalance_ratio, needs_weights
from src.data.load import ID_COLUMN
from src.data.run_phase05 import make_folds


def test_balanced_weights_average_one_per_row() -> None:
    labels = pd.Series(["a"] * 60 + ["b"] * 30 + ["c"] * 10)
    weights = class_weights(labels)
    assert weights["c"] == pytest.approx(100 / (3 * 10))
    assert sum(weights[c] for c in labels) / len(labels) == pytest.approx(1.0)
    assert imbalance_ratio(labels) == pytest.approx(6.0)
    assert needs_weights(labels, 1.5) and not needs_weights(pd.Series(["a", "b"]), 1.5)


def test_folds_cover_each_row_once_per_repeat() -> None:
    rng = np.random.default_rng(0)
    train = pd.DataFrame(
        {ID_COLUMN: [f"M{i}" for i in range(100)], "stratum": rng.choice(["s1", "s2", "s3"], 100)}
    )
    folds = make_folds(train, folds=5, repeats=3, seed=1)
    assert len(folds) == 300
    per_repeat = folds.groupby("repeat")[ID_COLUMN].nunique()
    assert (per_repeat == 100).all()
    assert folds.groupby(["repeat", "fold"]).size().between(19, 21).all()
