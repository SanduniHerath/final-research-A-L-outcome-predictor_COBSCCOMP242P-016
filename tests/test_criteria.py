"""Tests for locking the Phase 2 success criteria."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.evaluation import criteria


def test_project_criteria_cover_all_targets() -> None:
    cfg = criteria.load_criteria()
    assert set(cfg["targets"]) == {"zscore", "zscore_band", "university_group", "degree_category"}
    for spec in cfg["targets"].values():
        assert spec["primary_metric"] and spec["minimum"]
        assert spec["primary_metric"] not in spec["secondary_metrics"]
    assert cfg["calibration"]["max_ece"] > 0


def test_lock_requires_confirmed_status(tmp_path: Path) -> None:
    file = tmp_path / "c.yaml"
    file.write_text("status: proposed\n", encoding="utf-8")
    with pytest.raises(ValueError, match="confirmed"):
        criteria.lock(file, tmp_path / "c.lock.json")


def test_lock_detects_later_change(tmp_path: Path) -> None:
    file, lock_file = tmp_path / "c.yaml", tmp_path / "c.lock.json"
    file.write_text("status: confirmed\nx: 1\n", encoding="utf-8")
    assert not criteria.is_locked(file, lock_file)
    criteria.lock(file, lock_file)
    assert criteria.is_locked(file, lock_file)
    criteria.require_locked(file, lock_file)
    with pytest.raises(FileExistsError):
        criteria.lock(file, lock_file)
    file.write_text("status: confirmed\nx: 2\n", encoding="utf-8")
    assert not criteria.is_locked(file, lock_file)
    with pytest.raises(criteria.CriteriaNotLockedError):
        criteria.require_locked(file, lock_file)
