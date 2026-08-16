"""Tests for the split, the feature pipeline and the selection measures."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.data import split as split_mod
from src.data.load import ID_COLUMN
from src.features import selection
from src.features.build import FeaturePipeline, binary_columns, encode_raw
from src.utils.config import load_config, resolve_path

CFG = load_config("features")


def survey_like(n: int, seed: int, district: str = "Kandy") -> pd.DataFrame:
    """Small synthetic table with every column the feature pipeline reads."""
    rng = np.random.default_rng(seed)
    grades = ["W", "S", "C", "B", "A"]
    data = {ID_COLUMN: [f"M{i:04d}" for i in range(n)]}
    for col in CFG["ordinal"]["grades"]["columns"]:
        data[col] = rng.choice(grades[1:], n)
    for col, spec in CFG["ordinal"].items():
        if col not in ("grades", "numeric_scales"):
            data[col] = rng.choice(spec["order"], n)
    for col in CFG["ordinal"]["numeric_scales"]["columns"]:
        data[col] = rng.integers(1, 6, n)
    for prefix, opts in (
        ("stream_influence_", ["career_goals", "parents"]),
        ("school_activity_", ["sports"]),
        ("leadership_", ["prefect"]),
    ):
        for o in opts:
            data[prefix + o] = rng.integers(0, 2, n).astype(float)
    data["leadership_roles"] = "Prefect"
    for col in CFG["skipped_indicators"]:
        data[col] = 0
    data["grade5_result"] = rng.choice(["Qualified", "Did not qualify"], n)
    data["ol_school_type"] = rng.choice(["National school", "Provincial school"], n)
    data["al_subject_combination"] = rng.choice(["Bio", "Maths"], n)
    data["al_district"] = district
    return pd.DataFrame(data)


def test_encode_raw_codes_grades_and_reverses_er4() -> None:
    data = survey_like(4, 0)
    data["ol_maths"] = ["A", "B", "C", "S"]
    data["er4"] = [1, 2, 4, 5]
    out = encode_raw(data, CFG)
    assert out["ol_maths"].tolist() == [4, 3, 2, 1]
    assert out["er4"].tolist() == [5, 4, 2, 1]
    expected = out[["er1", "er2", "er3", "er4"]].mean(axis=1)
    assert np.allclose(out["effort_regulation_index"], expected)


def test_encode_raw_rejects_unknown_label() -> None:
    data = survey_like(2, 0)
    data.loc[0, "class_rank_freq"] = "Sometimes?"
    with pytest.raises(ValueError, match="without an ordinal code"):
        encode_raw(data, CFG)


def test_binary_columns_excludes_text_skipped_and_counts() -> None:
    cols = pd.DataFrame(
        columns=[
            "leadership_roles",
            "leadership_prefect",
            "leadership_roles_skipped",
            "leadership_count",
            "school_activity_sports",
        ]
    )
    assert binary_columns(cols, ["leadership_", "school_activity_"]) == [
        "leadership_prefect",
        "school_activity_sports",
    ]


def test_pipeline_learns_only_from_training_rows() -> None:
    train, other = survey_like(200, 1), survey_like(50, 2, district="Jaffna")
    other["g6_11_perf_rating"] = 5  # very different from training
    pipe = FeaturePipeline(CFG).fit(train)
    before = pipe.scaler_.mean_.copy()
    out = pipe.transform(other)
    assert np.array_equal(before, pipe.scaler_.mean_)  # transform does not refit
    assert pipe.fitted_rows_ == 200
    assert (out["al_district_index"] == 0).all()  # unseen district -> unknown
    assert not out.filter(like="al_district_").drop(columns="al_district_index").any().any()
    assert not out.isna().any().any()


def test_training_features_are_standardised() -> None:
    pipe = FeaturePipeline(CFG)
    out = pipe.fit_transform(survey_like(300, 3))
    assert np.allclose(out[pipe.numeric_].mean(), 0, atol=1e-9)


def test_cramers_v_and_epsilon_squared_limits() -> None:
    x = pd.Series(["a", "b"] * 50)
    v, p = selection.cramers_v(x, x)
    assert v == pytest.approx(1.0) and p < 1e-6
    values = pd.Series(np.r_[np.zeros(50), np.ones(50)])
    e, _ = selection.epsilon_squared(values, pd.Series(["g1"] * 50 + ["g2"] * 50))
    assert e > 0.9


def test_redundant_to_drop_keeps_preferred() -> None:
    pairs = pd.DataFrame(
        {"feature_a": ["se1"], "feature_b": ["self_efficacy_index"], "spearman": [0.95]}
    )
    assert selection.redundant_to_drop(pairs, ["self_efficacy_index", "se1"]) == ["se1"]


def test_stratification_merges_small_strata() -> None:
    data = pd.DataFrame(
        {
            "zscore": np.r_[np.linspace(0, 1, 60), [2.0]],
            "degree_category": ["A"] * 30 + ["B"] * 30 + ["B"],
        }
    )
    key = split_mod.stratification_key(data, min_size=10)
    assert key.value_counts().min() >= 10 or key.nunique() < 6


def test_make_split_proportions_and_disjoint() -> None:
    rng = np.random.default_rng(0)
    data = pd.DataFrame(
        {
            ID_COLUMN: [f"M{i}" for i in range(400)],
            "zscore": rng.normal(1.5, 0.4, 400),
            "degree_category": rng.choice(["A", "B", "C"], 400),
        }
    )
    out = split_mod.make_split(data, load_config("split"), seed=1)
    counts = out["split"].value_counts()
    assert counts["test"] == 60  # 15 % of 400
    assert abs(counts["validation"] - 60) <= 1 and counts.sum() == 400  # sklearn rounds up
    assert out[ID_COLUMN].is_unique


@pytest.mark.skipif(not resolve_path("configs/split.lock.json").exists(), reason="no split yet")
def test_test_set_is_locked() -> None:
    with pytest.raises(split_mod.TestSetLockedError):
        split_mod.load_split_rows("test")


def test_redundant_to_drop_never_loses_both_sides_of_a_chain() -> None:
    # g11 ~ effort_index and effort_regulation_index ~ effort_index:
    # effort_index goes (less preferred than ER index), so g11 must be kept.
    pairs = pd.DataFrame(
        {
            "feature_a": ["g11", "er_index"],
            "feature_b": ["effort_index", "effort_index"],
            "spearman": [0.94, 0.93],
        }
    )
    assert selection.redundant_to_drop(pairs, ["er_index", "effort_index", "g11"]) == [
        "effort_index"
    ]
