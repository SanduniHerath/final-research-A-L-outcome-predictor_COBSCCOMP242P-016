"""Tests for the Phase 7 evaluation code (verdict rules, subgroup scores, one-time test access)."""

from __future__ import annotations

import numpy as np
import pytest

from src.evaluation import phase07_analysis as a
from src.evaluation import run_phase07


def test_verdict_follows_locked_rule() -> None:
    assert a.verdict(0.30, 0.15, 0.10) == "met"
    assert a.verdict(0.12, 0.05, 0.10) == "partly met"
    assert a.verdict(0.08, 0.01, 0.10) == "not met"


def test_group_score_ignores_classes_absent_from_the_group() -> None:
    y = np.array([0, 0, 1, 1])
    proba = np.eye(7)[[0, 0, 1, 1]]  # perfect on the two classes that occur
    assert a.group_score("degree_category", y, proba) == pytest.approx(1.0)
    assert a.group_score("zscore", np.array([1.0, 2.0]), np.array([1.5, 2.0])) == pytest.approx(
        0.25
    )


def test_temperature_one_changes_nothing_and_sharpening_raises_confidence() -> None:
    p = np.array([[0.6, 0.3, 0.1]])
    assert np.allclose(a.apply_temperature(p, 1.0), p)
    assert a.apply_temperature(p, 0.5)[0, 0] > 0.6


def test_test_set_cannot_be_opened_twice(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:  # noqa: ANN001
    access = tmp_path / "test_access.json"
    access.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(run_phase07, "ACCESS_FILE", access)
    with pytest.raises(run_phase07.TestAlreadyOpenedError):
        run_phase07.open_test_once()
