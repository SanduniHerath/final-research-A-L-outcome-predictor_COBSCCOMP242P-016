"""Phase 8: interpret the results with figures.

    python -m src.explain.run_phase08

Explanations are computed on the VALIDATION split with training rows as the background, so
the test set is not read again. The Z-score residual plot and the gender check use the test
predictions saved once in Phase 7. No model is retrained or changed.
"""

from __future__ import annotations

import json
import re
import sys
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

from src.evaluation.criteria import require_locked
from src.explain.core import (
    ChosenSystem,
    display_name,
    group_columns,
    grouped_permutation_importance,
    load_network,
    mean_abs_shap,
    network_function,
    shap_explain,
)
from src.models.data import TASKS, class_names, encode_targets
from src.utils.config import get_seed, load_config, resolve_path
from src.utils.logging_setup import get_logger
from src.utils.plot_style import CATEGORICAL, INK, apply_style, save_figure

logger = get_logger(__name__)
PATHS = load_config("project")["paths"]
OUT = resolve_path(PATHS["reports"]) / "phase08"
FIG = resolve_path(PATHS["figures"])
P6 = resolve_path(PATHS["reports"]) / "phase06"
TASK_TITLE = {
    "zscore": "Z-score",
    "zscore_band": "Z-score band",
    "university_group": "University group",
    "degree_category": "Degree category",
}


def load_rows() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Training and validation feature tables (with targets) from Phase 4."""
    processed = resolve_path(PATHS["processed"])
    return pd.read_csv(processed / "features_train.csv"), pd.read_csv(
        processed / "features_validation.csv"
    )


# ---- SHAP ------------------------------------------------------------------------------------
def shap_all(
    system: ChosenSystem, x: np.ndarray, background: np.ndarray, cfg: dict[str, Any]
) -> dict[str, Any]:
    """SHAP values of the chosen system for every task, with the additivity check."""
    out = {}
    for task in TASKS:
        f = system.task_function(task)
        expl = shap_explain(f, x, background, cfg["max_evals"], get_seed())
        pred = f(x)
        total = expl.base_values + expl.values.sum(axis=1)
        out[task] = {
            "values": expl.values,
            "base": expl.base_values,
            "additivity_max_error": float(np.max(np.abs(total - pred))),
        }
    return out


def importance_table(shap_out: dict[str, Any], x: np.ndarray, columns: list[str]) -> pd.DataFrame:
    """Mean |SHAP| per feature and task; for the Z-score also its direction (Spearman)."""
    rows = []
    for task, res in shap_out.items():
        imp = mean_abs_shap(res["values"])
        for j, col in enumerate(columns):
            direction = np.nan
            if task == "zscore" and np.std(x[:, j]) > 0:
                direction = stats.spearmanr(x[:, j], res["values"][:, j]).statistic
            rows.append(
                {
                    "task": task,
                    "feature": col,
                    "label": display_name(col),
                    "mean_abs_shap": float(imp[j]),
                    "direction_spearman": direction,
                }
            )
    table = pd.DataFrame(rows)
    table["share"] = table["mean_abs_shap"] / table.groupby("task")["mean_abs_shap"].transform(
        "sum"
    )
    return table.sort_values(["task", "mean_abs_shap"], ascending=[True, False])


def plot_shap_bars(table: pd.DataFrame, top: int = 12) -> None:
    """Top features by mean |SHAP| for each target."""
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    for ax, task in zip(axes.ravel(), TASKS, strict=True):
        part = table[table["task"] == task].head(top).iloc[::-1]
        colours = [CATEGORICAL[0]] * len(part)
        if task == "zscore":
            colours = [
                CATEGORICAL[0] if d >= 0 else CATEGORICAL[1]
                for d in part["direction_spearman"].fillna(0)
            ]
        ax.barh(part["label"], part["share"] * 100, color=colours, height=0.65)
        ax.set_xlabel("Share of total importance (%)")
        unit = "Z-score points" if task == "zscore" else "probability"
        ax.set_title(f"{TASK_TITLE[task]} (mean |SHAP| in {unit})", loc="left", fontsize=11)
        ax.grid(axis="y", visible=False)
        ax.tick_params(axis="y", labelsize=8.5)
    handles = [
        plt.Rectangle((0, 0), 1, 1, color=CATEGORICAL[0]),
        plt.Rectangle((0, 0), 1, 1, color=CATEGORICAL[1]),
    ]
    axes[0, 0].legend(
        handles,
        ["Higher value -> higher Z-score", "Higher value -> lower Z-score"],
        loc="lower right",
        fontsize=8,
    )
    fig.suptitle(
        "What the chosen system relies on (SHAP, validation students; association, not cause)",
        x=0.01,
        ha="left",
        fontweight="bold",
    )
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    save_figure(fig, FIG / "phase08_shap_importance.png")


def plot_zscore_beeswarm(
    values: np.ndarray, x: np.ndarray, columns: list[str], top: int = 12
) -> None:
    """Dot plot of SHAP values for the Z-score: each dot is a student, colour = feature value."""
    order = np.argsort(np.abs(values).mean(axis=0))[::-1][:top]
    fig, ax = plt.subplots(figsize=(10, 7))
    rng = np.random.default_rng(0)
    for rank, j in enumerate(order[::-1]):
        v = x[:, j]
        colour = (v - v.min()) / (v.max() - v.min() + 1e-9)
        ax.scatter(
            values[:, j],
            rank + rng.uniform(-0.25, 0.25, len(v)),
            c=colour,
            cmap="coolwarm",
            s=12,
            alpha=0.8,
            edgecolor="none",
        )
    ax.set_yticks(range(len(order)))
    ax.set_yticklabels([display_name(columns[j]) for j in order[::-1]], fontsize=8.5)
    ax.axvline(0, color=INK["muted"], linewidth=0.8)
    ax.set_xlabel("Contribution to the predicted Z-score (Z-score points)")
    ax.grid(axis="y", visible=False)
    sm = plt.cm.ScalarMappable(cmap="coolwarm")
    cbar = fig.colorbar(sm, ax=ax, fraction=0.03, pad=0.02)
    cbar.set_ticks([0, 1])
    cbar.set_ticklabels(["low answer", "high answer"])
    ax.set_title(
        "Z-score: how each answer moves the prediction (one dot per validation student)", loc="left"
    )
    save_figure(fig, FIG / "phase08_shap_zscore_beeswarm.png")


# ---- H7: grouped permutation importance ------------------------------------------------------
def h7(
    system: ChosenSystem, val: pd.DataFrame, columns: list[str], cfg: dict[str, Any]
) -> pd.DataFrame:
    """Grouped permutation importance of the five question groups for every target."""
    groups = group_columns(columns, load_config("explain")["groups"])
    index = {g: [columns.index(c) for c in cols] for g, cols in groups.items()}
    x = val[columns].to_numpy(dtype=np.float32)
    y = encode_targets(val)
    frames = [
        grouped_permutation_importance(
            system.task_function(t), t, x, y[t], index, cfg["bootstrap"], cfg["level"], get_seed()
        )
        for t in TASKS
    ]
    return pd.concat(frames, ignore_index=True)


def plot_h7(table: pd.DataFrame) -> None:
    """Importance of each question group with 95 % CI, one panel per target."""
    fig, axes = plt.subplots(2, 2, figsize=(13, 8))
    for ax, task in zip(axes.ravel(), TASKS, strict=True):
        part = table[table["task"] == task].sort_values("importance")
        y = np.arange(len(part))
        ax.barh(
            y,
            part["importance"],
            xerr=[part["importance"] - part["ci_low"], part["ci_high"] - part["importance"]],
            color=[CATEGORICAL[0] if s else INK["muted"] for s in part["supported"]],
            height=0.6,
            error_kw={"ecolor": INK["secondary"], "capsize": 3},
        )
        ax.set_yticks(y)
        ax.set_yticklabels(part["group"], fontsize=9)
        ax.axvline(0, color=INK["muted"], linewidth=0.8)
        metric = "MAE increase" if task == "zscore" else "macro F1 drop"
        ax.set_title(
            f"{TASK_TITLE[task]} ({metric} when the group is shuffled)", loc="left", fontsize=10.5
        )
        ax.grid(axis="y", visible=False)
    fig.suptitle(
        "H7 - grouped permutation importance (validation, 95 % CI; blue = CI above 0)",
        x=0.01,
        ha="left",
        fontweight="bold",
    )
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    save_figure(fig, FIG / "phase08_h7_group_importance.png")


# ---- TabNet masks vs SHAP --------------------------------------------------------------------
def tabnet_vs_shap(
    val: pd.DataFrame, background: np.ndarray, columns: list[str], cfg: dict[str, Any]
) -> tuple[pd.DataFrame, dict[str, float]]:
    """TabNet attention-mask importance vs SHAP importance of the same network (seed 0)."""
    model = load_network("final__tabnet__-__s0.pt")
    x = val[columns].to_numpy(dtype=np.float32)
    masks = pd.read_csv(P6 / "check_tabnet_mask_importance.csv", index_col=0)["seed0"]
    shap_imp = np.zeros(len(columns))
    for task in TASKS:
        expl = shap_explain(
            network_function(model, task), x, background, cfg["max_evals"], get_seed()
        )
        imp = mean_abs_shap(expl.values)
        shap_imp += imp / imp.sum()
    shap_imp /= len(TASKS)
    table = pd.DataFrame(
        {
            "feature": columns,
            "label": [display_name(c) for c in columns],
            "mask_importance": masks.reindex(columns).to_numpy(),
            "shap_importance": shap_imp,
        }
    )
    rho = stats.spearmanr(table["mask_importance"], table["shap_importance"]).statistic
    top10 = len(
        set(table.nlargest(10, "mask_importance")["feature"])
        & set(table.nlargest(10, "shap_importance")["feature"])
    )
    return table.sort_values("shap_importance", ascending=False), {
        "spearman": float(rho),
        "top10_overlap": top10 / 10,
    }


def plot_tabnet(table: pd.DataFrame, agree: dict[str, float], top: int = 15) -> None:
    """TabNet mask importance next to SHAP importance (shares of the total)."""
    part = table.head(top).iloc[::-1]
    y = np.arange(len(part))
    fig, ax = plt.subplots(figsize=(10, 7))
    ax.barh(y + 0.2, part["shap_importance"] * 100, height=0.38, color=CATEGORICAL[0], label="SHAP")
    ax.barh(
        y - 0.2,
        part["mask_importance"] * 100,
        height=0.38,
        color=CATEGORICAL[1],
        label="TabNet attention masks",
    )
    ax.set_yticks(y)
    ax.set_yticklabels(part["label"], fontsize=8.5)
    ax.set_xlabel("Share of total importance (%)")
    ax.grid(axis="y", visible=False)
    ax.legend(loc="lower right")
    ax.set_title(
        f"TabNet: attention-mask vs SHAP importance (Spearman {agree['spearman']:.2f}, "
        f"top-10 overlap {agree['top10_overlap']:.0%})",
        loc="left",
        fontsize=11,
    )
    save_figure(fig, FIG / "phase08_tabnet_mask_vs_shap.png")


# ---- partial dependence ----------------------------------------------------------------------
def original_scale(system: ChosenSystem, column: str, z: np.ndarray) -> np.ndarray | None:
    """Map standardised values of a numeric feature back to the answer scale (None for 0/1)."""
    pipe = system.pipeline
    if column not in pipe.numeric_:
        return None
    j = pipe.numeric_.index(column)
    return z * pipe.scaler_.scale_[j] + pipe.scaler_.mean_[j]


def partial_dependence(
    system: ChosenSystem, val: pd.DataFrame, features: list[str], points: int
) -> dict[str, Any]:
    """Average predicted Z-score as one feature is set to each grid value (others unchanged)."""
    columns = system.columns
    x = val[columns].to_numpy(dtype=np.float32)
    f = system.task_function("zscore")
    out = {}
    for col in features:
        j = columns.index(col)
        grid = (
            np.unique(x[:, j])
            if len(np.unique(x[:, j])) <= points
            else np.quantile(x[:, j], np.linspace(0.05, 0.95, points))
        )
        curves = []
        for value in grid:
            xx = x.copy()
            xx[:, j] = value
            curves.append(f(xx))
        curves = np.array(curves)
        out[col] = {
            "grid": grid,
            "original": original_scale(system, col, grid),
            "mean": curves.mean(axis=1),
            "ice": curves[:, :40],
        }
    return out


def plot_pdp(pdp: dict[str, Any]) -> None:
    """Partial dependence (bold) with 40 individual curves (thin) for the top Z-score features."""
    n = len(pdp)
    fig, axes = plt.subplots(2, (n + 1) // 2, figsize=(5 * ((n + 1) // 2), 8.5))
    for ax, (col, res) in zip(axes.ravel(), pdp.items(), strict=False):
        xs = res["original"] if res["original"] is not None else res["grid"]
        ax.plot(xs, res["ice"], color=CATEGORICAL[0], alpha=0.12, linewidth=0.8)
        ax.plot(
            xs,
            res["mean"],
            color=CATEGORICAL[1],
            linewidth=2.5,
            marker="o",
            markersize=4,
            label="Average",
        )
        ax.set_title(display_name(col), loc="left", fontsize=10)
        ax.set_xlabel(
            "Answer (original scale)" if res["original"] is not None else "0 = no, 1 = yes"
        )
        ax.set_ylabel("Predicted Z-score")
    for ax in axes.ravel()[n:]:
        ax.axis("off")
    axes.ravel()[0].legend(fontsize=8)
    fig.suptitle(
        "Partial dependence of the predicted Z-score (validation students; association, not cause)",
        x=0.01,
        ha="left",
        fontweight="bold",
    )
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    save_figure(fig, FIG / "phase08_partial_dependence.png")


# ---- test-set figures from saved Phase 7 predictions ----------------------------------------
def test_predictions() -> dict[str, np.ndarray]:
    """Saved Phase 7 test predictions (the test set is not re-read)."""
    with np.load(resolve_path(PATHS["processed"]) / "phase07_test_predictions.npz") as data:
        return {k: data[k] for k in data.files}


def plot_residuals(pred: dict[str, np.ndarray]) -> dict[str, float]:
    """Predicted vs actual Z-score and residuals of the chosen Z-score network (test set)."""
    key = next(
        k for k in pred if k.startswith("pred__stage2_zscore") and k.endswith("__s0__zscore")
    )
    y, p = pred["y__zscore"], pred[key]
    res = y - p
    fig, axes = plt.subplots(1, 2, figsize=(13, 5.2))
    axes[0].scatter(p, y, s=18, color=CATEGORICAL[0], alpha=0.75, edgecolor="white", linewidth=0.5)
    lims = [min(p.min(), y.min()) - 0.05, max(p.max(), y.max()) + 0.05]
    axes[0].plot(lims, lims, color=INK["muted"], linestyle=":", label="Perfect prediction")
    axes[0].set_xlabel("Predicted Z-score")
    axes[0].set_ylabel("Actual Z-score")
    axes[0].legend(loc="upper left")
    axes[0].set_title("Predicted vs actual", loc="left", fontsize=11)
    axes[1].scatter(
        p, res, s=18, color=CATEGORICAL[0], alpha=0.75, edgecolor="white", linewidth=0.5
    )
    axes[1].axhline(0, color=INK["muted"], linestyle=":")
    slope = np.polyfit(p, res, 1)
    xs = np.linspace(p.min(), p.max(), 50)
    axes[1].plot(
        xs,
        np.polyval(slope, xs),
        color=CATEGORICAL[1],
        linewidth=2,
        label="Linear trend of residuals",
    )
    axes[1].set_xlabel("Predicted Z-score")
    axes[1].set_ylabel("Actual minus predicted")
    axes[1].legend(loc="upper left")
    axes[1].set_title("Residuals", loc="left", fontsize=11)
    fig.suptitle(
        "Chosen Z-score network on the test set (153 students)",
        x=0.01,
        ha="left",
        fontweight="bold",
    )
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    save_figure(fig, FIG / "phase08_zscore_residuals.png")
    low, high = np.quantile(y, [1 / 3, 2 / 3])
    return {
        "residual_sd": float(res.std(ddof=1)),
        "share_within_0_2": float((np.abs(res) <= 0.2).mean()),
        "share_within_0_4": float((np.abs(res) <= 0.4).mean()),
        "residual_trend_slope": float(slope[0]),
        # grouped by ACTUAL score (shows regression to the mean, expected for any model)
        "mean_residual_lowest_actual_third": float(res[y <= low].mean()),
        "mean_residual_highest_actual_third": float(res[y >= high].mean()),
        # grouped by PREDICTED score (the bias a user would experience)
        "mean_residual_lowest_predicted_third": float(res[p <= np.quantile(p, 1 / 3)].mean()),
        "mean_residual_highest_predicted_third": float(res[p >= np.quantile(p, 2 / 3)].mean()),
    }


def parse_mean(cell: str) -> tuple[float, float]:
    """'0.123 ± 0.004' -> (0.123, 0.004)."""
    m = re.match(r"([\d.]+)\s*±\s*([\d.]+)", str(cell))
    return (float(m.group(1)), float(m.group(2))) if m else (float(cell), 0.0)


def plot_ablations() -> None:
    """Ablation charts: dropout / L2, Wide & Deep parts, autoencoder size (validation, 5 seeds)."""
    panels = [
        (
            "check_reg_dnn_ablation.csv",
            "Regularised DNN: dropout and L2",
            {
                "tuned": "Dropout + L2",
                "dropout_only": "Dropout only",
                "l2_only": "L2 only",
                "no_dropout_no_l2": "Neither",
            },
        ),
        (
            "check_wide_deep_ablation.csv",
            "Wide & Deep: parts and crosses",
            {
                "tuned": "Wide + deep",
                "wide_only": "Wide only",
                "deep_only": "Deep only",
                "both_without_crosses": "Both, no crosses",
            },
        ),
        (
            "check_ae_variants.csv",
            "Autoencoder + MLP: bottleneck size",
            {
                "bottleneck_8": "Bottleneck 8",
                "bottleneck_16": "Bottleneck 16",
                "bottleneck_24": "Bottleneck 24",
                "tuned": "Bottleneck 32 (tuned)",
                "without_autoencoder": "No autoencoder",
            },
        ),
    ]
    tasks = ["zscore", "zscore_band", "degree_category"]
    fig, axes = plt.subplots(3, 3, figsize=(15, 11))
    for row, (file, title, names) in enumerate(panels):
        table = pd.read_csv(P6 / file).set_index("variant")
        order = [v for v in names if v in table.index]
        for col, task in enumerate(tasks):
            ax = axes[row, col]
            means, sds = zip(*(parse_mean(table.loc[v, task]) for v in order), strict=True)
            # dots, not bars: the axis is zoomed in, and bars not starting at zero would mislead
            ax.errorbar(
                means,
                range(len(order)),
                xerr=sds,
                fmt="o",
                color=CATEGORICAL[col],
                ecolor=INK["secondary"],
                capsize=3,
                markersize=8,
            )
            ax.set_yticks(range(len(order)))
            ax.set_yticklabels(
                [names[v] for v in order] if col == 0 else [""] * len(order), fontsize=9
            )
            ax.invert_yaxis()
            ax.grid(axis="y", visible=False)
            lo = min(m - s for m, s in zip(means, sds, strict=True))
            ax.set_xlim(
                max(0, lo - 0.05), max(m + s for m, s in zip(means, sds, strict=True)) + 0.02
            )
            if row == 0:
                ax.set_title(
                    f"{TASK_TITLE[task]} "
                    f"({'MAE, lower better' if task == 'zscore' else 'macro F1'})",
                    loc="left",
                    fontsize=10.5,
                )
        axes[row, 0].set_ylabel(title, fontsize=10, fontweight="bold")
    fig.suptitle(
        "Ablations on the validation split (mean ± SD over 5 seeds)",
        x=0.01,
        ha="left",
        fontweight="bold",
    )
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    save_figure(fig, FIG / "phase08_ablations.png")


def gender_check(pred: dict[str, np.ndarray]) -> pd.DataFrame:
    """Degree-category mix and per-class recall of the chosen system by gender (test set)."""
    names = class_names()["degree_category"]
    decisions = json.loads((P6 / "decisions.json").read_text("utf-8"))
    key = f"pred__{decisions['architecture']['selected']}__s0__degree_category"
    y, p, g = pred["y__degree_category"], pred[key].argmax(axis=1), pred["gender"]
    rows = []
    for k, name in enumerate(names):
        row = {"degree_category": name}
        for gender in ("Female", "Male"):
            mask = (g == gender) & (y == k)
            row[f"{gender}_n"] = int(mask.sum())
            row[f"{gender}_recall"] = float((p[mask] == k).mean()) if mask.any() else np.nan
        rows.append(row)
    return pd.DataFrame(rows)


def main() -> int:
    """Run every Phase 8 analysis and figure."""
    require_locked()
    apply_style()
    OUT.mkdir(parents=True, exist_ok=True)
    cfg = load_config("explain")
    system = ChosenSystem.load()
    columns = system.columns
    train, val = load_rows()
    background = (
        train[columns]
        .sample(cfg["shap"]["background_rows"], random_state=get_seed())
        .to_numpy(np.float32)
    )
    x = val[columns].to_numpy(dtype=np.float32)

    shap_out = shap_all(system, x, background, cfg["shap"])
    table = importance_table(shap_out, x, columns)
    table.to_csv(OUT / "shap_importance.csv", index=False)
    np.savez_compressed(
        resolve_path(PATHS["processed"]) / "phase08_shap_validation.npz",
        **{f"{t}__values": r["values"] for t, r in shap_out.items()},
        **{f"{t}__base": r["base"] for t, r in shap_out.items()},
    )
    plot_shap_bars(table)
    plot_zscore_beeswarm(shap_out["zscore"]["values"], x, columns)

    groups = h7(system, val, columns, cfg["permutation_importance"])
    groups.to_csv(OUT / "h7_group_importance.csv", index=False)
    plot_h7(groups)

    tab, agree = tabnet_vs_shap(val, background, columns, cfg["shap"])
    tab.to_csv(OUT / "tabnet_mask_vs_shap.csv", index=False)
    plot_tabnet(tab, agree)

    top = (
        table[table["task"] == "zscore"]
        .head(cfg["partial_dependence"]["top_features"])["feature"]
        .tolist()
    )
    pdp = partial_dependence(system, val, top, cfg["partial_dependence"]["grid_points"])
    plot_pdp(pdp)
    pd.DataFrame(
        [
            {
                "feature": c,
                "grid_original": [
                    round(float(v), 3)
                    for v in (r["original"] if r["original"] is not None else r["grid"])
                ],
                "mean_prediction": [round(float(v), 4) for v in r["mean"]],
            }
            for c, r in pdp.items()
        ]
    ).to_csv(OUT / "partial_dependence.csv", index=False)

    pred = test_predictions()
    residuals = plot_residuals(pred)
    plot_ablations()
    gender_check(pred).to_csv(OUT / "gender_degree_check.csv", index=False)

    summary = {
        "additivity_max_error": {t: r["additivity_max_error"] for t, r in shap_out.items()},
        "tabnet_mask_vs_shap": agree,
        "zscore_residuals_test": residuals,
        "h7_supported": groups.groupby("task")
        .apply(lambda d: d.loc[d["supported"], "group"].tolist())
        .to_dict(),
        "pdp_features": top,
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2, default=float), "utf-8")
    logger.info("Phase 8 written: %s", summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
