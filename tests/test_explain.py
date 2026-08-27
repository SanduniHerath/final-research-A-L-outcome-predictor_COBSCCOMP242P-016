"""Tests for the XAI building blocks (src/explain/core.py)."""

from __future__ import annotations

import numpy as np
import pytest

from src.explain import core


def test_display_name_handles_wildcards() -> None:
    names = {"ol_maths": "O/L Maths", "al_subject_combination_*": "A/L subjects: "}
    assert core.display_name("ol_maths", names) == "O/L Maths"
    assert core.display_name("al_subject_combination_Bio", names) == "A/L subjects: Bio"
    assert core.display_name("unknown", names) == "unknown"


def test_group_columns_requires_every_column_in_a_group() -> None:
    groups = {"a": ["x1", "p_*"], "b": ["x2"]}
    out = core.group_columns(["x1", "x2", "p_1", "p_2"], groups)
    assert out == {"a": ["x1", "p_1", "p_2"], "b": ["x2"]}
    with pytest.raises(ValueError, match="no group"):
        core.group_columns(["x1", "x3"], groups)


def test_shap_values_add_up_to_the_prediction() -> None:
    rng = np.random.default_rng(0)
    x, background = rng.normal(size=(5, 3)), rng.normal(size=(20, 3))

    def f(z: np.ndarray) -> np.ndarray:
        return 2 * z[:, 0] - z[:, 1] + 0.5 * z[:, 0] * z[:, 2]

    expl = core.shap_explain(f, x, background, max_evals=200, seed=0)
    assert np.allclose(expl.base_values + expl.values.sum(axis=1), f(x), atol=1e-8)


def test_permutation_importance_finds_the_used_group_only() -> None:
    rng = np.random.default_rng(1)
    x = rng.normal(size=(200, 2)).astype(np.float32)
    y = (2 * x[:, 0]).astype(np.float32)

    def f(z: np.ndarray) -> np.ndarray:
        return 2 * z[:, 0]

    table = core.grouped_permutation_importance(
        f, "zscore", x, y, {"used": [0], "unused": [1]}, n_boot=50, level=0.95, seed=0
    )
    result = table.set_index("group")
    assert result.loc["used", "supported"]
    assert not result.loc["unused", "supported"]
    assert result.loc["unused", "importance"] == pytest.approx(0.0, abs=1e-6)
