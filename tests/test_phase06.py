"""Tests for the Phase 6 metrics, bootstrap, networks, training loop and selection helpers."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
import torch

from src.evaluation import metrics
from src.evaluation.bootstrap import bootstrap_ci, paired_bootstrap_diff
from src.models import cv
from src.models.data import ModelData
from src.models.networks import TASK_DIMS, build_network
from src.models.train import class_weight_tensor, fit, predict
from src.utils.config import load_config

MODELS = load_config("models")["models"]


def toy_data(n: int = 120, d: int = 10, seed: int = 0) -> ModelData:
    rng = np.random.default_rng(seed)
    x = rng.normal(size=(n, d)).astype(np.float32)
    z = (1.5 + 0.3 * x[:, 0] + 0.05 * rng.normal(size=n)).astype(np.float32)
    targets = {
        "zscore": z,
        "zscore_band": np.digitize(z, np.quantile(z, [1 / 3, 2 / 3])).astype(np.int64),
        "university_group": rng.integers(0, 5, n).astype(np.int64),
        "degree_category": (x[:, 1] > 0).astype(np.int64) + 2 * (x[:, 2] > 0).astype(np.int64),
    }
    return ModelData(
        x=x,
        targets=targets,
        district=rng.integers(0, 26, n).astype(np.int64),
        wide=np.c_[x, x[:, :2] * x[:, 2:4]].astype(np.float32),
    )


def test_ece_is_zero_for_perfectly_calibrated_bins() -> None:
    proba = np.array([[1.0, 0.0]] * 10)
    assert metrics.expected_calibration_error(np.zeros(10, dtype=int), proba) == pytest.approx(0.0)
    assert metrics.expected_calibration_error(np.ones(10, dtype=int), proba) == pytest.approx(1.0)


def test_classification_metrics_include_ordinal_extras() -> None:
    y = np.array([0, 1, 2, 2])
    proba = np.eye(3)[[0, 1, 2, 1]] * 0.9 + 0.1 / 3
    out = metrics.classification_metrics(y, proba, ordinal=True)
    assert out["accuracy"] == pytest.approx(0.75)
    assert out["within_one_accuracy"] == pytest.approx(1.0)
    assert "qwk" in out and "roc_auc_ovr_macro" in out
    assert "qwk" not in metrics.classification_metrics(y, proba, ordinal=False)


def test_baseline_predictions() -> None:
    assert metrics.baseline_predictions(np.array([1.0, 3.0]), 3, "regression").tolist() == [
        2.0,
        2.0,
        2.0,
    ]
    proba = metrics.baseline_predictions(np.array([0, 0, 1]), 2, "classification", 3)
    assert proba[0].tolist() == pytest.approx([2 / 3, 1 / 3, 0.0])


def test_primary_value_orientation() -> None:
    assert metrics.primary_value("zscore", {"mae": 0.2}) == -0.2
    assert metrics.primary_value("degree_category", {"macro_f1": 0.5}) == 0.5


def test_paired_bootstrap_of_identical_predictions_is_zero() -> None:
    rng = np.random.default_rng(0)
    y, p = rng.normal(size=50), rng.normal(size=50)
    mae = lambda a, b: float(np.mean(np.abs(a - b)))  # noqa: E731
    assert paired_bootstrap_diff(y, p, p, mae, n=200) == (0.0, 0.0, 0.0)
    point, low, high = bootstrap_ci(y, p, mae, n=200)
    assert low <= point <= high


@pytest.mark.parametrize("name", list(MODELS))
def test_every_network_returns_all_heads(name: str) -> None:
    data = toy_data()
    cfg = dict(MODELS[name]["default"]) | {"ae_units": 16}
    dims = {"in_dim": data.x.shape[1], "wide_dim": data.wide.shape[1], "n_districts": 25}
    net = build_network(name, cfg, dims, list(TASK_DIMS))
    net.eval()
    inp = {
        "x": torch.from_numpy(data.x[:8]),
        "district": torch.from_numpy(data.district[:8]),
        "wide": torch.from_numpy(data.wide[:8]),
    }
    if name == "ae_mlp":
        inp["x"] = torch.zeros(8, cfg["bottleneck"])
    out = net(inp)
    assert out["zscore"].shape == (8,)
    assert {t: o.shape[1] for t, o in out.items() if t != "zscore"} == {
        "zscore_band": 3,
        "university_group": 5,
        "degree_category": 7,
    }


def test_single_task_network_has_one_head() -> None:
    net = build_network("mlp", MODELS["mlp"]["default"], {"in_dim": 10}, ["degree_category"])
    assert set(net({"x": torch.zeros(4, 10)}).keys()) == {"degree_category"}


def test_class_weights_ignore_absent_class() -> None:
    w = class_weight_tensor(np.array([0, 0, 1, 1]), 3)
    assert w.tolist() == pytest.approx([1.0, 1.0, 0.0])


def test_fit_learns_signal_and_restores_best_epoch() -> None:
    data = toy_data(240)
    cfg = dict(MODELS["mlp"]["default"]) | {"patience": 5}
    model = fit("mlp", cfg, data, ["zscore"], seed=0, dims={"in_dim": 10}, max_epochs=60)
    pred = predict(model, data)["zscore"]
    baseline = np.mean(np.abs(data.targets["zscore"] - data.targets["zscore"].mean()))
    assert np.mean(np.abs(pred - data.targets["zscore"])) < baseline
    assert 1 <= model.best_epoch <= model.epochs_run


def test_fit_is_repeatable_with_same_seed() -> None:
    data = toy_data(100)
    cfg = dict(MODELS["mlp"]["default"]) | {"patience": 3}
    a = predict(fit("mlp", cfg, data, ["zscore"], 7, {"in_dim": 10}, 20), data)["zscore"]
    b = predict(fit("mlp", cfg, data, ["zscore"], 7, {"in_dim": 10}, 20), data)["zscore"]
    assert np.allclose(a, b)


def test_search_configs_are_seeded_and_in_range() -> None:
    a, b = cv.search_configs("reg_dnn", 5, 1), cv.search_configs("reg_dnn", 5, 1)
    assert a == b and a[0][0] == "c00"
    for _, cfg in a[1:]:
        assert 2 <= cfg["layers"] <= 4 and 0.1 <= cfg["dropout"] <= 0.5


def test_mean_rank_and_tie_rule_prefer_fewer_parameters() -> None:
    rows = []
    for split in ("f0", "f1"):
        for cand, score, params in (("big", 0.80, 1000), ("small", 0.79, 10), ("bad", 0.10, 5)):
            rows.append(
                {"split": split, "task": "t", "score": score, "cand": cand, "n_params": params}
            )
    ranks = cv.mean_rank(pd.DataFrame(rows), "cand")
    assert ranks.index[0] == "big"
    ranks.loc["big", "sd_rank"] = 1.0  # within one SD -> tied with "small"
    assert cv.pick_with_tie_rule(ranks) == "small"
