"""Tests for Phase 3 cleaning and labelling."""

from __future__ import annotations

import pandas as pd
import pytest

from src.data import clean, labels
from src.data.load import ID_COLUMN


def frame(**cols: list) -> pd.DataFrame:
    n = len(next(iter(cols.values())))
    return pd.DataFrame({ID_COLUMN: [f"M{i}" for i in range(n)], **cols})


def test_strip_whitespace_touches_only_text() -> None:
    data = frame(grade=["C ", "A"], year=[2019, "2018 or earlier"])
    out, log = clean.strip_whitespace(data)
    assert out["grade"].tolist() == ["C", "A"]
    assert out["year"].tolist() == [2019, "2018 or earlier"]
    assert len(log) == 1 and log[0]["rows_affected"] == 1


def test_value_correction_is_logged() -> None:
    data = frame(al_district=["M+AX533atara", "Kandy"])
    fix = [{"column": "al_district", "from": "M+AX533atara", "to": "Matara", "reason": "typo"}]
    out, log = clean.apply_corrections(data, fix)
    assert out["al_district"].tolist() == ["Matara", "Kandy"]
    assert log[0]["respondent_ids"] == "M0"


def test_split_multiselect_handles_commas_inside_options() -> None:
    options = [
        "Sports",
        "Academic competitions (Science, Mathematics, ICT, Olympiads)",
        "Other competitions (debating, arts, etc.)",
        "None",
    ]
    cell = "Sports, Academic competitions (Science, Mathematics, ICT, Olympiads)"
    chosen, leftover = clean.split_multiselect(cell, options)
    assert chosen == {"Sports", options[1]}
    assert leftover == ""


def test_split_multiselect_does_not_confuse_prefect_and_head_prefect() -> None:
    chosen, _ = clean.split_multiselect(
        "Head Prefect, Team Captain", ["Prefect", "Head Prefect", "Team Captain"]
    )
    assert chosen == {"Head Prefect", "Team Captain"}


def test_expand_multiselect_marks_skipped_and_other_text() -> None:
    data = frame(acts=["Sports", None, "Sports, Chess club", "None"])
    out, _ = clean.expand_multiselect(data, "acts", ["Sports"], "act")
    assert out["act_sports"].tolist()[0] == 1
    assert pd.isna(out["act_sports"].iloc[1])
    assert out["acts_skipped"].tolist() == [0, 1, 0, 0]
    assert out["act_other_text"].tolist() == [0, 0, 1, 0]
    assert out["act_sports"].iloc[3] == 0


def test_subject_combination_uses_only_taken_flags() -> None:
    cols = {c: ["Not Taken"] for c in clean.AL_SUBJECTS}
    cols.update({"al_biology": ["A"], "al_chemistry": ["S"], "al_physics": ["C"]})
    combo, log = clean.subject_combination(frame(**cols))
    assert combo.iloc[0] == "Biology + Chemistry + Physics"
    assert log == []


def test_map_to_groups_rejects_unknown_and_duplicates() -> None:
    groups = {"West": ["Colombo"], "South": ["Ruhuna"]}
    assert labels.map_to_groups(pd.Series(["Colombo", "Ruhuna"]), groups).tolist() == [
        "West",
        "South",
    ]
    with pytest.raises(ValueError, match="without a group"):
        labels.map_to_groups(pd.Series(["Jaffna"]), groups)
    with pytest.raises(ValueError, match="more than one group"):
        labels.invert_groups({"A": ["x"], "B": ["x"]})


def test_tertile_bands_are_equal_sized_and_edges_go_up() -> None:
    z = pd.Series(range(1, 13), dtype=float)
    edges = labels.band_edges(z, 3)
    bands = labels.assign_band(z, edges)
    assert bands.value_counts().tolist() == [4, 4, 4]
    assert labels.assign_band(pd.Series([edges[0]]), edges).iloc[0] == 1


def test_goal_status_and_combination_flag() -> None:
    target = pd.Series(["Medicine", "Engineering", "Other", "Dental"])
    outcome = pd.Series(["Medicine", "Medicine", "Engineering", "Medicine"])
    status = labels.goal_status(target, outcome, ["Other"])
    assert status.tolist()[:2] == ["reached", "not reached"]
    assert pd.isna(status.iloc[2])
    combo = pd.Series(["Bio", "Bio", "Maths", "Bio"])
    flags = labels.combination_observed(target.where(target != "Other"), outcome, combo)
    # Medicine with Bio observed; Engineering never with Bio; Dental absent -> cannot check
    assert flags.iloc[0] == 1
    assert flags.iloc[1] == 0
    assert pd.isna(flags.iloc[2]) and pd.isna(flags.iloc[3])


def test_mark_excluded_keeps_row_and_rejects_unknown_id() -> None:
    data = frame(x=[1, 2])
    out, log = clean.mark_excluded(data, [{"respondent_id": "M1", "reason": "entry error"}])
    assert out["exclude_from_modelling"].tolist() == [0, 1]
    assert len(out) == 2 and log[0]["respondent_ids"] == "M1"
    with pytest.raises(ValueError, match="Unknown respondent_id"):
        clean.mark_excluded(data, [{"respondent_id": "M9", "reason": "x"}])
