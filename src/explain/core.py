"""Explainable-AI building blocks (system part 5), shared by Phase 8 and the Phase 9 app.

* :class:`ChosenSystem` loads the deployed networks (Phase 6/7 decision): the multi-output
  MLP for band, university group and degree category, and the Stage-2 MLP for the Z-score.
* :func:`shap_explain` gives Shapley values with the permutation algorithm, which is
  model-agnostic and exactly additive: base value + sum of contributions = prediction.
* :func:`grouped_permutation_importance` measures how much a whole group of questions
  matters (hypothesis H7). These are associations in the data, not causes.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import joblib
import numpy as np
import pandas as pd
import shap
import torch

from src.evaluation.metrics import PRIMARY, target_metrics
from src.models.data import TASKS, ModelData
from src.models.train import Fitted, predict
from src.utils.config import load_config, resolve_path

PATHS = load_config("project")["paths"]
P6 = resolve_path(PATHS["reports"]) / "phase06"
ModelFn = Callable[[np.ndarray], np.ndarray]


def final_columns() -> list[str]:
    """The 34 model input columns (Phase 6)."""
    return json.loads((P6 / "final_columns.json").read_text("utf-8"))


def load_network(file: str) -> Fitted:
    """Load a saved network from models/phase06."""
    return torch.load(resolve_path(PATHS["models"]) / "phase06" / file, weights_only=False)


@dataclass
class ChosenSystem:
    """The deployed prediction system and its feature pipeline."""

    multi: Fitted
    zscore: Fitted
    pipeline: Any
    columns: list[str]

    @classmethod
    def load(cls) -> ChosenSystem:
        """Load the networks chosen in Phase 6 (seed 0) and the training-fitted pipeline."""
        decisions = json.loads((P6 / "decisions.json").read_text("utf-8"))
        selected = decisions["architecture"]["selected"]
        multi = load_network(f"final__{selected}__-__s0.pt")
        stage2 = decisions.get("stage2", {}).get("zscore")
        zscore = (
            load_network(f"stage2_final__{stage2['selected']}__zscore__s0.pt") if stage2 else multi
        )
        pipeline = joblib.load(resolve_path(PATHS["models"]) / "feature_pipeline.joblib")
        return cls(multi=multi, zscore=zscore, pipeline=pipeline, columns=final_columns())

    def network_for(self, task: str) -> Fitted:
        """Which network produces a task."""
        return self.zscore if task == "zscore" else self.multi

    def task_function(self, task: str) -> ModelFn:
        """``f(X) -> prediction`` for one task on standardised feature rows (34 columns)."""
        return network_function(self.network_for(task), task)


def network_function(model: Fitted, task: str) -> ModelFn:
    """Wrap a fitted network as ``f(X)`` for one task (Z-score value, or class probabilities)."""

    def f(x: np.ndarray) -> np.ndarray:
        data = ModelData(x=np.asarray(x, dtype=np.float32), targets={})
        return predict(model, data)[task]

    return f


def display_name(column: str, names: dict[str, str] | None = None) -> str:
    """Plain-language name of a model column."""
    names = names or load_config("explain")["display_names"]
    if column in names:
        return names[column]
    for pattern, label in names.items():
        if pattern.endswith("*") and column.startswith(pattern[:-1]):
            return label + column[len(pattern) - 1 :]
    return column


def group_columns(columns: list[str], groups: dict[str, list[str]]) -> dict[str, list[str]]:
    """Expand group definitions (names or ``prefix*``) to the model columns they cover."""
    out: dict[str, list[str]] = {}
    for group, members in groups.items():
        cols = []
        for m in members:
            cols += (
                [c for c in columns if c.startswith(m[:-1])]
                if m.endswith("*")
                else [m]
                if m in columns
                else []
            )
        out[group] = cols
    covered = {c for cols in out.values() for c in cols}
    missing = [c for c in columns if c not in covered]
    if missing:
        raise ValueError(f"Columns in no group: {missing}")
    return out


def shap_explain(
    f: ModelFn, x: np.ndarray, background: np.ndarray, max_evals: int, seed: int
) -> shap.Explanation:
    """Shapley values (permutation algorithm) for rows ``x`` against a background sample."""
    masker = shap.maskers.Independent(background, max_samples=len(background))
    explainer = shap.PermutationExplainer(f, masker, seed=seed)
    return explainer(x, max_evals=max_evals, silent=True)


def mean_abs_shap(values: np.ndarray) -> np.ndarray:
    """Global importance per feature: mean |SHAP| over rows (and over classes if present)."""
    v = np.abs(values)
    return v.mean(axis=(0, 2)) if v.ndim == 3 else v.mean(axis=0)


def oriented_score(task: str, y: np.ndarray, pred: np.ndarray) -> float:
    """Primary metric with higher = better."""
    name, direction = PRIMARY[task]
    value = target_metrics(task, y, pred)[name]
    return -value if direction == "lower" else value


def grouped_permutation_importance(
    f: ModelFn,
    task: str,
    x: np.ndarray,
    y: np.ndarray,
    groups: dict[str, list[int]],
    n_boot: int,
    level: float,
    seed: int,
) -> pd.DataFrame:
    """Drop in the primary metric when a whole group of columns is shuffled together.

    Each bootstrap draw resamples the rows AND uses a fresh joint permutation of the group,
    so the interval covers both sources of uncertainty. Importance > 0 means the model relies
    on the group; the CI lower bound > 0 is the H7 test.
    """
    rng = np.random.default_rng(seed)
    full = f(x)
    rows = []
    for group, idx in groups.items():
        drops = []
        for _ in range(n_boot):
            r = rng.integers(0, len(x), len(x))
            shuffled = x[r].copy()
            shuffled[:, idx] = shuffled[rng.permutation(len(r))][:, idx]
            drops.append(
                oriented_score(task, y[r], full[r]) - oriented_score(task, y[r], f(shuffled))
            )
        point_x = x.copy()
        point_x[:, idx] = x[rng.permutation(len(x))][:, idx]
        point = oriented_score(task, y, full) - oriented_score(task, y, f(point_x))
        tail = (1 - level) / 2 * 100
        low, high = np.percentile(drops, [tail, 100 - tail])
        rows.append(
            {
                "task": task,
                "group": group,
                "n_columns": len(idx),
                "importance": float(np.mean(drops)),
                "single_permutation": float(point),
                "ci_low": float(low),
                "ci_high": float(high),
                "supported": bool(low > 0),
            }
        )
    return pd.DataFrame(rows)


__all__ = [
    "TASKS",
    "ChosenSystem",
    "display_name",
    "group_columns",
    "grouped_permutation_importance",
    "mean_abs_shap",
    "network_function",
    "shap_explain",
]
