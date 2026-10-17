"""Tests for the psychometric functions in src.data.questionnaire."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from factor_analyzer.factor_analyzer import calculate_bartlett_sphericity, calculate_kmo

from src.data import questionnaire as q


@pytest.fixture
def one_factor_data() -> pd.DataFrame:
    rng = np.random.default_rng(0)
    latent = rng.normal(size=600)
    cols = {f"x{i}": 0.8 * latent + 0.6 * rng.normal(size=600) for i in range(4)}
    return pd.DataFrame(cols)


def test_cronbach_alpha_hand_value() -> None:
    items = pd.DataFrame({"a": [1, 2, 3, 4], "b": [2, 1, 4, 3]})
    # item variances 5/3 each, total-score variance 16/3 -> alpha = 2 * (1 - (10/3)/(16/3))
    assert q.cronbach_alpha(items) == pytest.approx(0.75)


def test_reverse_code() -> None:
    items = pd.DataFrame({"a": [1, 3, 5], "b": [1, 2, 3]})
    out = q.reverse_code(items, ["a"], 1, 5)
    assert out["a"].tolist() == [5, 3, 1]
    assert out["b"].tolist() == [1, 2, 3]
    assert items["a"].tolist() == [1, 3, 5]  # input untouched


def test_feldt_interval_brackets_alpha() -> None:
    low, high = q.feldt_interval(0.8, n=100, k=4, level=0.95)
    assert low < 0.8 < high
    narrow_low, narrow_high = q.feldt_interval(0.8, n=1000, k=4, level=0.95)
    assert narrow_high - narrow_low < high - low


def test_item_total_excludes_item_itself(one_factor_data: pd.DataFrame) -> None:
    table = q.item_total_table(one_factor_data, "pearson")
    rest = one_factor_data.drop(columns="x0").sum(axis=1)
    assert table.loc["x0", "citc"] == pytest.approx(one_factor_data["x0"].corr(rest))
    assert table.loc["x0", "alpha_if_deleted"] == pytest.approx(
        q.cronbach_alpha(one_factor_data.drop(columns="x0"))
    )


def test_kmo_and_bartlett_match_factor_analyzer(one_factor_data: pd.DataFrame) -> None:
    corr = one_factor_data.corr()
    kmo, msa = q.kmo_from_corr(corr)
    ref_msa, ref_kmo = calculate_kmo(one_factor_data)
    assert kmo == pytest.approx(ref_kmo)
    assert msa.to_numpy() == pytest.approx(ref_msa)
    chi2, df, p = q.bartlett_from_corr(corr, len(one_factor_data))
    ref_chi2, ref_p = calculate_bartlett_sphericity(one_factor_data)
    assert chi2 == pytest.approx(ref_chi2)
    assert df == 6
    assert p == pytest.approx(ref_p)


def test_paf_recovers_known_loadings() -> None:
    lam = np.array([0.8, 0.7, 0.6, 0.5])
    corr = np.outer(lam, lam)
    np.fill_diagonal(corr, 1.0)
    loadings = q.principal_axis_factoring(corr, 1)[:, 0]
    assert loadings == pytest.approx(lam, abs=1e-3)


def test_efa_separates_two_constructs() -> None:
    rng = np.random.default_rng(1)
    f1, f2 = rng.normal(size=(2, 800))
    data = pd.DataFrame(
        {
            **{f"a{i}": f1 + 0.5 * rng.normal(size=800) for i in range(3)},
            **{f"b{i}": f2 + 0.5 * rng.normal(size=800) for i in range(3)},
        }
    )
    result = q.run_efa(data.corr(), len(data), 2, "principal", "oblimin")
    mapping = q.align_factors(result.loadings, {"A": ["a0", "a1", "a2"], "B": ["b0", "b1", "b2"]})
    assert mapping["A"] != mapping["B"]
    assert (result.loadings.loc[["a0", "a1", "a2"], mapping["A"]] > 0.7).all()


def test_parallel_analysis_finds_one_factor(one_factor_data: pd.DataFrame) -> None:
    table = q.parallel_analysis(one_factor_data, "spearman", 50, 95, seed=1)
    assert q.suggested_factor_count(table) == 1


def test_cr_and_ave_hand_values() -> None:
    lam = pd.Series([0.8, 0.8])
    assert q.average_variance_extracted(lam) == pytest.approx(0.64)
    assert q.composite_reliability(lam) == pytest.approx(2.56 / 3.28)


def test_htmt_hand_value() -> None:
    names = ["a1", "a2", "b1", "b2"]
    values = np.full((4, 4), 0.32)
    values[:2, :2] = 0.64
    values[2:, 2:] = 0.64
    np.fill_diagonal(values, 1.0)
    corr = pd.DataFrame(values, index=names, columns=names)
    table = q.htmt(corr, {"A": ["a1", "a2"], "B": ["b1", "b2"]})
    assert table.loc["B", "A"] == pytest.approx(0.5)


def test_item_decisions_rules() -> None:
    thresholds = {
        "citc_drop_below": 0.20,
        "citc_min": 0.30,
        "alpha_if_deleted_tolerance": 0.01,
        "outer_loading_remove_below": 0.40,
        "outer_loading_min": 0.70,
        "efa_loading_min": 0.40,
        "efa_cross_loading_max": 0.30,
        "efa_cross_loading_gap_min": 0.20,
        "single_category_share_max": 0.50,
    }
    items = ["good", "weak", "bad"]
    item_total = pd.DataFrame(
        {"citc": [0.8, 0.25, 0.1], "alpha_if_deleted": [0.80, 0.86, 0.90]}, index=items
    )
    loadings = pd.Series([0.85, 0.6, 0.3], index=items)
    efa = pd.DataFrame({"F1": [0.85, 0.6, 0.3], "F2": [0.05, 0.1, 0.1]}, index=items)
    stats = pd.DataFrame({"max_category_share": [0.3, 0.3, 0.3]}, index=items)
    table = q.item_decisions(
        item_total,
        {"C": 0.84},
        dict.fromkeys(items, "C"),
        efa,
        {"C": "F1"},
        loadings,
        stats,
        thresholds,
    )
    assert table["decision"].tolist() == ["Keep", "Revise", "Drop"]
