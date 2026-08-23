"""Phase 6, part 2 analysis: validation results and the model-specific checks of the brief.

Writes tables to reports/phase06/ and figures to reports/figures/phase06_*.png.
Only training and validation rows are used.
"""

from __future__ import annotations

import json
from itertools import combinations
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import torch
from scipy import stats
from scipy.optimize import minimize_scalar
from sklearn import metrics as skm
from sklearn.decomposition import PCA

from src.evaluation.bootstrap import paired_bootstrap_diff
from src.evaluation.criteria import load_criteria
from src.evaluation.metrics import (
    PRIMARY,
    expected_calibration_error,
    reliability_curve,
    target_metrics,
)
from src.models import cv
from src.models.data import TASKS, make_model_data
from src.models.run_phase06_final import (
    OUT,
    SPLIT,
    context,
    district_onehots,
    load_model,
    load_predictions,
    records,
    seed_summary,
)
from src.models.train import predict
from src.utils.config import load_config, resolve_path
from src.utils.logging_setup import get_logger
from src.utils.plot_style import CATEGORICAL, INK, apply_style, save_figure

logger = get_logger(__name__)
FIG = resolve_path(load_config("project")["paths"]["figures"])
TASK_LABEL = {
    "zscore": "Z-score (MAE, lower is better)",
    "zscore_band": "Z-score band (macro F1)",
    "university_group": "University group (macro F1)",
    "degree_category": "Degree category (macro F1)",
}
CLASS_TASKS = ["zscore_band", "university_group", "degree_category"]
MODEL_LABEL = {
    "mlp": "MLP",
    "reg_dnn": "Regularised DNN",
    "wide_deep": "Wide & Deep",
    "tabnet": "TabNet",
    "mtl": "Multi-task",
    "entity_mlp": "Entity-embedding MLP",
    "ae_mlp": "Autoencoder + MLP",
    "resnet": "ResNet-style",
}


def primary(rec: dict[str, Any], task: str, which: str = "metrics") -> float:
    """Primary metric of a task in one run (as reported, not sign-flipped)."""
    return float(rec[which][task][PRIMARY[task][0]])


def primary_by_seed(recs: list[dict[str, Any]], task: str) -> list[float]:
    """Primary validation metric of each seed."""
    return [primary(r, task) for r in sorted(recs, key=lambda r: r["seed"])]


def mean_sd(values: list[float]) -> str:
    """'mean ± sd' with three decimals."""
    return (
        f"{np.mean(values):.3f} ± {np.std(values, ddof=1):.3f}"
        if len(values) > 1
        else f"{values[0]:.3f}"
    )


def validation_tables(configs: dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Long table of all validation metrics (mean, SD over seeds) and a wide primary table."""
    long_rows, wide_rows = [], []
    for model in configs:
        recs = records("final", model)
        summary = seed_summary(recs)
        summary.insert(0, "model", model)
        long_rows.append(summary)
        row = {
            "model": model,
            "n_params": recs[0]["n_params"],
            "seconds_mean": np.mean([r["seconds"] for r in recs]),
            "best_epoch_mean": np.mean([r["best_epoch"] for r in recs]),
        }
        for task in TASKS:
            row[task] = mean_sd(primary_by_seed(recs, task))
            row[f"{task}_baseline"] = recs[0]["baseline"][task][PRIMARY[task][0]]
        wide_rows.append(row)
    return pd.concat(long_rows), pd.DataFrame(wide_rows)


def gap_table(configs: dict[str, Any]) -> pd.DataFrame:
    """Train vs validation gap of the primary metric, compared with the locked limits."""
    limits = load_criteria()["general"]["overfitting"]
    rows = []
    for model in configs:
        for task in TASKS:
            gaps = []
            for r in records("final", model):
                train_v, val_v = primary(r, task, "train_metrics"), primary(r, task)
                gaps.append((val_v - train_v) / train_v if task == "zscore" else train_v - val_v)
            limit = (
                limits["max_gap_regression_mae_relative"]
                if task == "zscore"
                else limits["max_gap_classification_macro_f1"]
            )
            rows.append(
                {
                    "model": model,
                    "task": task,
                    "gap_mean": np.mean(gaps),
                    "gap_sd": np.std(gaps, ddof=1),
                    "limit": limit,
                    "within_limit": bool(np.mean(gaps) <= limit),
                }
            )
    return pd.DataFrame(rows)


def cv_stability() -> pd.DataFrame:
    """CV mean and spread of the tuned configurations, compared with the locked stability limits."""
    spread = load_criteria()["general"]["cross_validation"]["max_spread"]
    table = pd.read_csv(OUT / "cv_summary_tuned.csv")
    table["spread"] = np.where(
        table["task"] == "zscore", table["cv_sd"] / table["cv_mean"], table["cv_sd"]
    )
    table["limit"] = np.where(table["task"] == "zscore", spread["mae_cv"], spread["f1_like_sd"])
    table["stable"] = table["spread"] <= table["limit"]
    return table


def learning_curves(configs: dict[str, Any]) -> pd.DataFrame:
    """Train and validation primary metric for growing shares of the training split (seed 0)."""
    rows = []
    for r in records("learning_curve"):
        for task in TASKS:
            rows.append(
                {
                    "model": r["model"],
                    "fraction": float(r["variant"]),
                    "task": task,
                    "train": primary(r, task, "train_metrics"),
                    "validation": primary(r, task),
                    "baseline": r["baseline"][task][PRIMARY[task][0]],
                }
            )
    return pd.DataFrame(rows).sort_values(["model", "task", "fraction"])


def fit_temperature(y: np.ndarray, proba: np.ndarray) -> float:
    """Temperature T minimising the log loss of softmax(log p / T) (one network)."""
    logp = np.log(np.clip(proba, 1e-12, 1))

    def nll(log_t: float) -> float:
        z = logp / np.exp(log_t)
        z = z - z.max(axis=1, keepdims=True)
        p = np.exp(z) / np.exp(z).sum(axis=1, keepdims=True)
        return float(skm.log_loss(y, np.clip(p, 1e-12, 1), labels=np.arange(proba.shape[1])))

    return float(np.exp(minimize_scalar(nll, bounds=(-3, 3), method="bounded").x))


def apply_temperature(proba: np.ndarray, temperature: float) -> np.ndarray:
    """Rescale probabilities with a temperature."""
    z = np.log(np.clip(proba, 1e-12, 1)) / temperature
    z = z - z.max(axis=1, keepdims=True)
    return np.exp(z) / np.exp(z).sum(axis=1, keepdims=True)


def calibration(configs: dict[str, Any]) -> tuple[pd.DataFrame, dict[str, Any], dict[str, Any]]:
    """ECE and Brier per model and class task; reliability bins and temperatures (seed 0)."""
    rows, curves, temps = [], {}, {}
    for model in configs:
        recs = records("final", model)
        preds = load_predictions("final", model, "-", 0)
        for task in CLASS_TASKS:
            y, p = preds[f"held_y_{task}"], preds[f"held_pred_{task}"]
            t = fit_temperature(y, p)
            temps.setdefault(model, {})[task] = t
            curves.setdefault(model, {})[task] = reliability_curve(y, p)
            rows.append(
                {
                    "model": model,
                    "task": task,
                    "ece_mean": np.mean([r["metrics"][task]["ece"] for r in recs]),
                    "ece_sd": np.std([r["metrics"][task]["ece"] for r in recs], ddof=1),
                    "brier_mean": np.mean([r["metrics"][task]["brier"] for r in recs]),
                    "baseline_brier": recs[0]["baseline"][task]["brier"],
                    "temperature_seed0": t,
                    "ece_seed0_after_scaling_on_validation": expected_calibration_error(
                        y, apply_temperature(p, t)
                    ),
                }
            )
    return pd.DataFrame(rows), curves, temps


def _oriented(task: str):  # noqa: ANN202 - returns a metric function
    name, direction = PRIMARY[task]

    def metric(y: np.ndarray, pred: np.ndarray) -> float:
        value = target_metrics(task, y, pred)[name]
        return -value if direction == "lower" else value

    return metric


def negative_transfer(models: list[str]) -> pd.DataFrame:
    """Multi-output vs single-task network of the same architecture, on validation rows."""
    rows = []
    for model in models:
        for task in TASKS:
            multi = load_predictions("final", model, "-", 0)
            single = load_predictions("single_task", model, task, 0)
            y = multi[f"held_y_{task}"]
            diff, low, high = paired_bootstrap_diff(
                y,
                multi[f"held_pred_{task}"],
                single[f"held_pred_{task}"],
                _oriented(task),
                n=2000,
                seed=0,
            )
            multi_seeds = primary_by_seed(records("final", model), task)
            single_seeds = primary_by_seed(records("single_task", model, task), task)
            rows.append(
                {
                    "model": model,
                    "task": task,
                    "metric": PRIMARY[task][0],
                    "multi_output": mean_sd(multi_seeds),
                    "single_task": mean_sd(single_seeds),
                    "diff_seed0_higher_is_better": diff,
                    "ci_low": low,
                    "ci_high": high,
                    "negative_transfer": bool(high < 0),
                    "positive_transfer": bool(low > 0),
                }
            )
    return pd.DataFrame(rows)


def variant_table(step: str, model: str, reference: str = "tuned") -> pd.DataFrame:
    """Primary metric (mean ± SD over seeds) for every variant of a check, plus the tuned model."""
    variants = {reference: records("final", model)}
    for r in records(step, model):
        variants.setdefault(r["variant"], []).append(r)
    rows = []
    for name, recs in variants.items():
        row = {
            "variant": name,
            "n_params": recs[0]["n_params"],
            "seconds_mean": np.mean([r["seconds"] for r in recs]),
            "best_epoch_mean": np.mean([r["best_epoch"] for r in recs]),
        }
        for task in recs[0]["tasks"].split("+"):
            row[task] = mean_sd(primary_by_seed(recs, task))
        rows.append(row)
    return pd.DataFrame(rows)


def validation_data(
    model: str, build_as: str | None = None, columns: list[str] | None = None
) -> Any:
    """Validation ModelData for a model (training-split pipeline)."""
    if columns is None:
        _, columns, _, _ = context()
    entry = cv.build_fold_cache()[SPLIT]
    return make_model_data(
        entry["held_x"],
        entry["held_y"],
        build_as or model,
        columns,
        load_config("models")["wide_crosses"],
    )


def cross_importance(seeds: list[int]) -> pd.DataFrame:
    """Validation score drop when all Wide & Deep cross columns are shuffled together."""
    data = validation_data("wide_deep")
    n_base = len(data.columns)
    rng = np.random.default_rng(0)
    rows = []
    for seed in seeds:
        model = load_model("final", "wide_deep", "-", seed)
        base = predict(model, data)
        for _ in range(20):
            shuffled = data.subset(np.arange(len(data)))
            shuffled.wide = data.wide.copy()
            perm = rng.permutation(len(data))
            shuffled.wide[:, n_base:] = data.wide[perm, n_base:]
            pred = predict(model, shuffled)
            for task in TASKS:
                metric = _oriented(task)
                rows.append(
                    {
                        "seed": seed,
                        "task": task,
                        "drop": metric(data.targets[task], base[task])
                        - metric(data.targets[task], pred[task]),
                    }
                )
    out = pd.DataFrame(rows).groupby("task")["drop"].agg(["mean", "std"]).reset_index()
    out["n_cross_columns"] = data.wide.shape[1] - n_base
    return out


def tabnet_masks(seeds: list[int]) -> tuple[pd.DataFrame, dict[str, float]]:
    """Global importance from TabNet attention masks, mask sparsity and stability across seeds."""
    data = validation_data("tabnet")
    x = torch.from_numpy(data.x)
    importances, sparsity = [], []
    for seed in seeds:
        model = load_model("final", "tabnet", "-", seed)
        with torch.no_grad():
            explain, masks = model.network.masks(x)
        imp = explain.numpy().sum(axis=0)
        importances.append(imp / imp.sum())
        sparsity.append(float(np.mean([(m.numpy() < 1e-6).mean() for m in masks.values()])))
    table = pd.DataFrame(
        np.array(importances).T, index=data.columns, columns=[f"seed{s}" for s in seeds]
    )
    table["mean"] = table.mean(axis=1)
    table = table.sort_values("mean", ascending=False)
    pairs = [
        stats.spearmanr(table[f"seed{a}"], table[f"seed{b}"]).statistic
        for a, b in combinations(seeds, 2)
    ]
    top10 = [set(table[f"seed{s}"].nlargest(10).index) for s in seeds]
    overlap = [len(a & b) / 10 for a, b in combinations(top10, 2)]
    return table, {
        "mask_zero_share_mean": float(np.mean(sparsity)),
        "importance_spearman_mean": float(np.mean(pairs)),
        "importance_spearman_min": float(np.min(pairs)),
        "top10_overlap_mean": float(np.mean(overlap)),
    }


def mtl_weights(seeds: list[int]) -> pd.DataFrame:
    """Learned loss weights exp(-log variance) at the restored (best) epoch, per seed."""
    rows = []
    for r in records("final", "mtl"):
        best = r["history"][r["best_epoch"] - 1]
        for task in TASKS:
            rows.append(
                {
                    "seed": r["seed"],
                    "task": task,
                    "log_var": best[f"log_var_{task}"],
                    "weight": float(np.exp(-best[f"log_var_{task}"])),
                }
            )
    return pd.DataFrame(rows).groupby("task")[["log_var", "weight"]].agg(["mean", "std"])


def entity_checks(
    seeds: list[int],
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, float], pd.DataFrame]:
    """Embedding vs one-hot, rare-district scores and embedding geometry (PCA, provinces)."""
    import joblib

    pipe = joblib.load(
        resolve_path(load_config("project")["paths"]["models"]) / "feature_pipeline.joblib"
    )
    index = pipe.district_index_
    train = pd.read_csv(
        resolve_path(load_config("project")["paths"]["processed"]) / "features_train.csv"
    )
    counts = train["al_district_index"].value_counts()
    rare_idx = set(counts[counts < 15].index)
    data = validation_data("entity_mlp")
    rare_rows = np.isin(data.district, list(rare_idx))
    rows = []
    _, columns, _, _ = context()
    for variant, step, build, cols in (
        ("embedding (district embedded)", "final", "entity_mlp", columns),
        ("one_hot_with_district", "check_entity", "mlp_dropout", columns + district_onehots()),
        ("one_hot_version (no district)", "check_entity", "mlp_dropout", columns),
    ):
        vdata = validation_data("entity_mlp", build_as=build, columns=cols)
        saved_variant = "-" if step == "final" else variant.split(" (")[0]
        for seed in seeds:
            model = load_model(step, "entity_mlp", saved_variant, seed)
            pred = predict(model, vdata)
            for task in TASKS:
                metric = PRIMARY[task][0]
                rows.append(
                    {
                        "variant": variant,
                        "seed": seed,
                        "task": task,
                        "all_rows": target_metrics(task, vdata.targets[task], pred[task])[metric],
                        "rare_district_rows": target_metrics(
                            task, vdata.targets[task][rare_rows], pred[task][rare_rows]
                        )[metric],
                    }
                )
    compare = (
        pd.DataFrame(rows)
        .groupby(["variant", "task"])[["all_rows", "rare_district_rows"]]
        .agg(["mean", "std"])
    )
    model = load_model("final", "entity_mlp", "-", 0)
    weights = model.network.embedding.weight.detach().numpy()
    names = sorted(index, key=index.get)
    vectors = weights[[index[n] for n in names]]
    coords = PCA(n_components=2, random_state=0).fit_transform(vectors)
    province = {d: p for p, ds in load_config("geography")["provinces"].items() for d in ds}
    emb = pd.DataFrame(
        {
            "district": names,
            "province": [province.get(n, "?") for n in names],
            "pc1": coords[:, 0],
            "pc2": coords[:, 1],
            "train_rows": [int(counts.get(index[n], 0)) for n in names],
        }
    )
    dist = np.linalg.norm(vectors[:, None, :] - vectors[None, :, :], axis=2)
    same = np.equal.outer(emb["province"].to_numpy(), emb["province"].to_numpy())
    off = ~np.eye(len(names), dtype=bool)
    geometry = {
        "mean_distance_same_province": float(dist[same & off].mean()),
        "mean_distance_other_province": float(dist[~same].mean()),
        "rare_districts": [n for n in names if index[n] in rare_idx],
        "validation_rows_in_rare_districts": int(rare_rows.sum()),
    }
    geometry["ratio_same_to_other"] = (
        geometry["mean_distance_same_province"] / geometry["mean_distance_other_province"]
    )
    perm_ratios = []
    rng = np.random.default_rng(0)
    for _ in range(1000):
        shuffled = rng.permutation(emb["province"].to_numpy())
        s = np.equal.outer(shuffled, shuffled)
        perm_ratios.append(dist[s & off].mean() / dist[~s].mean())
    geometry["permutation_p_value"] = float(
        np.mean(np.array(perm_ratios) <= geometry["ratio_same_to_other"])
    )
    return compare, emb, geometry, pd.DataFrame(rows)


def ae_checks(seeds: list[int]) -> pd.DataFrame:
    """Reconstruction MSE on training and validation rows (AE fitted on training rows)."""
    from src.models.train import reconstruction_mse

    entry = cv.build_fold_cache()[SPLIT]
    _, columns, _, _ = context()
    train = make_model_data(entry["train_x"], entry["train_y"], "ae_mlp", columns)
    val = validation_data("ae_mlp")
    rows = []
    for step, variant in [("final", "-")] + [
        ("check_ae", v)
        for v in sorted({r["variant"] for r in records("check_ae", "ae_mlp")})
        if v.startswith("bottleneck")
    ]:
        for seed in seeds:
            model = load_model(step, "ae_mlp", variant, seed)
            rows.append(
                {
                    "variant": "tuned" if step == "final" else variant,
                    "bottleneck": model.cfg["bottleneck"],
                    "seed": seed,
                    "train_mse": reconstruction_mse(model, train),
                    "validation_mse": reconstruction_mse(model, val),
                }
            )
    return (
        pd.DataFrame(rows)
        .groupby(["variant", "bottleneck"])[["train_mse", "validation_mse"]]
        .agg(["mean", "std"])
    )


def smoothness(recs: list[dict[str, Any]]) -> float:
    """Mean absolute second difference of the early-stopping loss, relative to its mean level."""
    values = []
    for r in recs:
        loss = np.array([h["es_loss"] for h in r["history"]])
        if len(loss) > 3:
            values.append(np.abs(np.diff(loss, 2)).mean() / loss.mean())
    return float(np.mean(values))


# ---- figures ---------------------------------------------------------------------------------
def plot_cv_comparison(configs: dict[str, Any]) -> None:
    """CV primary metric (mean ± SD over 15 folds) per model and task, with the baseline."""
    table = pd.read_csv(OUT / "cv_summary_tuned.csv")
    models = list(configs)
    fig, axes = plt.subplots(2, 2, figsize=(12, 8))
    for ax, task in zip(axes.ravel(), TASKS, strict=True):
        part = table[table["task"] == task].set_index("model").loc[models]
        y = np.arange(len(models))
        ax.barh(
            y,
            part["cv_mean"],
            xerr=part["cv_sd"],
            color=CATEGORICAL[0],
            height=0.6,
            error_kw={"ecolor": INK["secondary"], "capsize": 3},
        )
        ax.axvline(
            part["baseline_mean"].mean(),
            color=CATEGORICAL[1],
            linestyle="--",
            linewidth=2,
            label="Trivial baseline",
        )
        ax.set_yticks(y)
        ax.set_yticklabels([MODEL_LABEL[m] for m in models])
        ax.invert_yaxis()
        ax.set_title(TASK_LABEL[task], loc="left", fontsize=11)
        ax.grid(axis="y", visible=False)
        for i, (m, s) in enumerate(zip(part["cv_mean"], part["cv_sd"], strict=True)):
            ax.text(m + s + 0.005, i, f"{m:.3f}", va="center", fontsize=8, color=INK["secondary"])
    axes[0, 0].legend(loc="lower right")
    fig.suptitle(
        "Cross-validation inside the training split (15 folds, mean ± SD), tuned configurations",
        x=0.01,
        ha="left",
        fontweight="bold",
    )
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    save_figure(fig, FIG / "phase06_cv_comparison.png")


def plot_learning_curves(lc: pd.DataFrame) -> None:
    """Validation primary metric vs share of training rows, one line per model."""
    fig, axes = plt.subplots(2, 2, figsize=(12, 8))
    models = list(MODEL_LABEL)
    styles = ["-", "--"]
    for ax, task in zip(axes.ravel(), TASKS, strict=True):
        part = lc[lc["task"] == task]
        for i, model in enumerate(models):
            m = part[part["model"] == model]
            ax.plot(
                m["fraction"] * 100,
                m["validation"],
                color=CATEGORICAL[i % 7],
                linestyle=styles[i // 7],
                marker="o",
                markersize=4,
                linewidth=1.6,
                label=MODEL_LABEL[model],
            )
        ax.axhline(part["baseline"].mean(), color=INK["muted"], linestyle=":", label="Baseline")
        ax.set_title(TASK_LABEL[task], loc="left", fontsize=11)
        ax.set_xlabel("Share of training rows used (%)")
    axes[0, 0].legend(fontsize=8, ncol=2)
    fig.suptitle(
        "Learning curves on the validation split (seed 0)", x=0.01, ha="left", fontweight="bold"
    )
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    save_figure(fig, FIG / "phase06_learning_curves.png")


def plot_reliability(curves: dict[str, Any], model: str) -> None:
    """Reliability diagrams of one model's three classifiers (validation, seed 0)."""
    fig, axes = plt.subplots(1, 3, figsize=(13, 4.4))
    for ax, task in zip(axes, CLASS_TASKS, strict=True):
        bins = pd.DataFrame(curves[model][task])
        ax.plot([0, 1], [0, 1], color=INK["muted"], linestyle=":", label="Perfect calibration")
        ax.plot(
            bins["confidence"], bins["accuracy"], color=CATEGORICAL[0], marker="o", label="Model"
        )
        for _, b in bins.iterrows():
            ax.annotate(
                str(int(b["count"])),
                (b["confidence"], b["accuracy"]),
                textcoords="offset points",
                xytext=(4, -10),
                fontsize=7,
                color=INK["secondary"],
            )
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.set_xlabel("Predicted confidence")
        ax.set_ylabel("Observed accuracy")
        ax.set_title(TASK_LABEL[task].split(" (")[0], loc="left", fontsize=11)
    axes[0].legend(loc="upper left", fontsize=8)
    fig.suptitle(
        f"Reliability on the validation split - {MODEL_LABEL[model]} (numbers = students per bin)",
        x=0.01,
        ha="left",
        fontweight="bold",
    )
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    save_figure(fig, FIG / f"phase06_reliability_{model}.png")


def plot_mtl_losses() -> None:
    """Multi-task model loss curves (seed 0): total and per task."""
    rec = [r for r in records("final", "mtl") if r["seed"] == 0][0]
    hist = pd.DataFrame(rec["history"])
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.4))
    axes[0].plot(hist["epoch"], hist["train_loss"], color=CATEGORICAL[0], label="Training part")
    axes[0].plot(hist["epoch"], hist["es_loss"], color=CATEGORICAL[1], label="Early-stopping part")
    axes[0].axvline(rec["best_epoch"], color=INK["muted"], linestyle=":", label="Restored epoch")
    axes[0].set_title("Total loss (sum of the four tasks)", loc="left", fontsize=11)
    for i, task in enumerate(TASKS):
        axes[1].plot(
            hist["epoch"],
            hist[f"es_loss_{task}"],
            color=CATEGORICAL[i],
            label=TASK_LABEL[task].split(" (")[0],
        )
    axes[1].axvline(rec["best_epoch"], color=INK["muted"], linestyle=":")
    axes[1].set_title("Early-stopping loss per task", loc="left", fontsize=11)
    for ax in axes:
        ax.set_xlabel("Epoch")
        ax.legend(fontsize=8)
    fig.suptitle("Multi-task model: loss curves (seed 0)", x=0.01, ha="left", fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    save_figure(fig, FIG / "phase06_mtl_loss_curves.png")


def plot_embedding(emb: pd.DataFrame) -> None:
    """PCA of the learned district embeddings, labelled and coloured by province."""
    provinces = sorted(emb["province"].unique())
    markers = ["o", "s", "^", "D", "v", "P", "X", "*", "h"]
    fig, ax = plt.subplots(figsize=(9, 7))
    for i, prov in enumerate(provinces):
        part = emb[emb["province"] == prov]
        ax.scatter(
            part["pc1"],
            part["pc2"],
            s=60,
            color=CATEGORICAL[i % 7],
            marker=markers[i % 9],
            edgecolor="white",
            linewidth=1,
            label=prov,
        )
        for _, r in part.iterrows():
            ax.annotate(
                f"{r['district']} ({r['train_rows']})",
                (r["pc1"], r["pc2"]),
                textcoords="offset points",
                xytext=(5, 4),
                fontsize=7.5,
                color=INK["secondary"],
            )
    ax.set_xlabel("Principal component 1")
    ax.set_ylabel("Principal component 2")
    ax.legend(fontsize=8, title="Province", title_fontsize=8, loc="best")
    ax.set_title("Learned district embeddings (PCA, seed 0; training rows in brackets)", loc="left")
    save_figure(fig, FIG / "phase06_entity_embedding_pca.png")


def stage2_summary(selected: str) -> pd.DataFrame:
    """Stage-2 single-task network vs the selected multi-output network, per weak task."""
    d = json.loads((OUT / "decisions.json").read_text("utf-8"))
    rows = []
    for task, info in d.get("stage2", {}).items():
        single = [r for r in cv.read_log() if r["step"] == "stage2_final" and r["variant"] == task]
        multi = records("final", selected)
        metric = PRIMARY[task][0]
        p_multi = load_predictions("final", selected, "-", 0)
        p_single = np.load(
            resolve_path(load_config("project")["paths"]["processed"])
            / "phase06_predictions"
            / f"stage2_final__{info['selected']}__{task}__s0.npz"
        )
        diff, low, high = paired_bootstrap_diff(
            p_multi[f"held_y_{task}"],
            p_single[f"held_pred_{task}"],
            p_multi[f"held_pred_{task}"],
            _oriented(task),
            n=2000,
            seed=0,
        )
        train_vals = [primary(r, task, "train_metrics") for r in single]
        val_vals = primary_by_seed(single, task)
        gap = (
            (np.mean(val_vals) - np.mean(train_vals)) / np.mean(train_vals)
            if task == "zscore"
            else np.mean(train_vals) - np.mean(val_vals)
        )
        rows.append(
            {
                "task": task,
                "stage2_model": info["selected"],
                "config_id": info["config_id"],
                "metric": metric,
                "stage2_validation": mean_sd(val_vals),
                "multi_output_validation": mean_sd(primary_by_seed(multi, task)),
                "diff_stage2_minus_multi_higher_is_better": diff,
                "ci_low": low,
                "ci_high": high,
                "train_validation_gap": gap,
                "n_params": single[0]["n_params"],
                "best_epoch_mean": np.mean([r["best_epoch"] for r in single]),
                **{
                    f"validation_{k}": v
                    for k, v in seed_summary(single).set_index("metric")["mean"].items()
                },
            }
        )
    return pd.DataFrame(rows)


def analyse() -> None:
    """Run every analysis and write tables, figures and a summary."""
    apply_style()
    configs, _, selected, seeds = context()
    long_table, wide_table = validation_tables(configs)
    long_table.to_csv(OUT / "validation_metrics_long.csv", index=False)
    wide_table.to_csv(OUT / "validation_primary.csv", index=False)
    gaps = gap_table(configs)
    gaps.to_csv(OUT / "train_validation_gap.csv", index=False)
    stability = cv_stability()
    stability.to_csv(OUT / "cv_stability.csv", index=False)
    lc = learning_curves(configs)
    lc.to_csv(OUT / "learning_curves.csv", index=False)
    calib, curves, temps = calibration(configs)
    calib.to_csv(OUT / "calibration_validation.csv", index=False)
    (OUT / "temperatures_seed0.json").write_text(json.dumps(temps, indent=2), "utf-8")
    (OUT / "reliability_bins_seed0.json").write_text(json.dumps(curves, indent=2), "utf-8")

    transfer = negative_transfer(sorted({selected, "mtl"}))
    transfer.to_csv(OUT / "negative_transfer.csv", index=False)
    d = json.loads((OUT / "decisions.json").read_text("utf-8"))
    weak_a = d["architecture"]["weakness_a"]
    weak_b = transfer[(transfer["model"] == selected) & transfer["negative_transfer"]][
        "task"
    ].tolist()
    weakness = {
        "selected": selected,
        "rule_a": weak_a,
        "rule_b_negative_transfer_tasks": weak_b,
        "weak_tasks": sorted(
            {t for t, v in weak_a.items() if not v["meets_minimum"]} | set(weak_b)
        ),
    }
    (OUT / "weakness.json").write_text(json.dumps(weakness, indent=2), "utf-8")

    checks: dict[str, Any] = {}
    variant_table("check_reg_dnn", "reg_dnn").to_csv(
        OUT / "check_reg_dnn_ablation.csv", index=False
    )
    variant_table("check_wide_deep", "wide_deep").to_csv(
        OUT / "check_wide_deep_ablation.csv", index=False
    )
    cross_importance(seeds).to_csv(OUT / "check_wide_deep_cross_importance.csv", index=False)
    masks, mask_stats = tabnet_masks(seeds)
    masks.to_csv(OUT / "check_tabnet_mask_importance.csv")
    checks["tabnet"] = mask_stats | {
        "seconds_mean": float(np.mean([r["seconds"] for r in records("final", "tabnet")]))
    }
    mtl_weights(seeds).to_csv(OUT / "check_mtl_loss_weights.csv")
    compare, emb, geometry, _ = entity_checks(seeds)
    compare.to_csv(OUT / "check_entity_vs_onehot.csv")
    emb.to_csv(OUT / "check_entity_embedding_pca.csv", index=False)
    checks["entity_geometry"] = geometry
    ae_checks(seeds).to_csv(OUT / "check_ae_reconstruction.csv")
    variant_table("check_ae", "ae_mlp").to_csv(OUT / "check_ae_variants.csv", index=False)
    variant_table("check_resnet", "resnet").to_csv(OUT / "check_resnet_vs_dnn.csv", index=False)
    checks["loss_smoothness"] = {
        "resnet": smoothness(records("final", "resnet")),
        "reg_dnn_same_depth": smoothness(records("check_resnet", "resnet")),
    }
    (OUT / "checks_summary.json").write_text(json.dumps(checks, indent=2, default=float), "utf-8")

    stage2 = stage2_summary(selected)
    if not stage2.empty:
        stage2.to_csv(OUT / "stage2_validation.csv", index=False)

    plot_cv_comparison(configs)
    plot_learning_curves(lc)
    plot_reliability(curves, selected)
    plot_mtl_losses()
    plot_embedding(emb)
    logger.info("Phase 6 analysis written to %s", OUT)
