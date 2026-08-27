"""Phase 7 analysis of saved predictions: metrics with bootstrap CIs, criteria and hypotheses.

Every confidence interval is a 2,000-sample percentile bootstrap (95 %). The SAME resampled
rows are used for every system and the baseline, so differences are paired (Phase 2 rules).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from joblib import Parallel, delayed
from sklearn import metrics as skm

from src.evaluation.criteria import load_criteria
from src.evaluation.metrics import (
    PRIMARY,
    baseline_predictions,
    expected_calibration_error,
    reliability_curve,
    target_metrics,
)
from src.models.data import TASKS, class_names, encode_targets
from src.utils.config import load_config, resolve_path
from src.utils.logging_setup import get_logger
from src.utils.plot_style import CATEGORICAL, INK, apply_style, save_figure

logger = get_logger(__name__)
PATHS = load_config("project")["paths"]
P6 = resolve_path(PATHS["reports"]) / "phase06"
CLASS_TASKS = ["zscore_band", "university_group", "degree_category"]
N_CLASSES = {"zscore_band": 3, "university_group": 5, "degree_category": 7}
CHOSEN = "chosen_system"
BASELINE = "trivial_baseline"
LABEL = {
    "mlp": "MLP",
    "reg_dnn": "Regularised DNN",
    "wide_deep": "Wide & Deep",
    "tabnet": "TabNet",
    "mtl": "Multi-task",
    "entity_mlp": "Entity-embedding MLP",
    "ae_mlp": "Autoencoder + MLP",
    "resnet": "ResNet-style",
    CHOSEN: "Chosen system",
    BASELINE: "Trivial baseline",
    "stage2_zscore_mlp": "Stage-2 MLP (Z-score only)",
}
SCALAR_SKIP = {"per_class_precision", "per_class_recall", "confusion_matrix"}


# ---- data ------------------------------------------------------------------------------------
def load(
    pred_file: Path,
) -> tuple[dict[str, np.ndarray], dict[str, dict[str, np.ndarray]], dict[str, Any]]:
    """Labels, predictions per system (seed 0 and all seeds) and extra row information."""
    data = np.load(pred_file, allow_pickle=False)
    y = {t: data[f"y__{t}"] for t in TASKS}
    decisions = json.loads((P6 / "decisions.json").read_text("utf-8"))
    selected = decisions["architecture"]["selected"]
    systems: dict[str, dict[str, np.ndarray]] = {}
    seeds: dict[str, dict[str, list[np.ndarray]]] = {}
    for key in data.files:
        if not key.startswith("pred__"):
            continue
        name, task = key[len("pred__") :].rsplit("__", 1)
        system, seed = name.rsplit("__s", 1) if "__s" in name else (name, "0")
        seeds.setdefault(system, {}).setdefault(task, []).append(data[key])
        if seed == "0":
            systems.setdefault(system, {})[task] = data[key]
    chosen = {t: systems[selected][t] for t in CLASS_TASKS}
    stage2 = decisions.get("stage2", {})
    z_source = f"stage2_zscore_{stage2['zscore']['selected']}" if "zscore" in stage2 else selected
    chosen["zscore"] = systems[z_source]["zscore"]
    systems[CHOSEN] = chosen
    train = pd.read_csv(resolve_path(PATHS["processed"]) / "features_train.csv")
    train_y = encode_targets(train)
    systems[BASELINE] = {
        t: baseline_predictions(
            train_y[t],
            len(y[t]),
            "regression" if t == "zscore" else "classification",
            N_CLASSES.get(t),
        )
        for t in TASKS
    }
    extra = {
        "gender": data["gender"],
        "subject_combination": data["subject_combination"],
        "selected": selected,
        "z_source": z_source,
        "seed_predictions": seeds,
    }
    return y, systems, extra


def scalar(metrics: dict[str, Any]) -> dict[str, float]:
    """Only the single-number metrics."""
    return {k: float(v) for k, v in metrics.items() if k not in SCALAR_SKIP and v is not None}


def boot_one(task: str, y: np.ndarray, pred: np.ndarray, idx: np.ndarray) -> pd.DataFrame:
    """Every scalar metric on every bootstrap resample (rows = resamples)."""
    rows = []
    for rows_idx in idx:
        try:
            rows.append(scalar(target_metrics(task, y[rows_idx], pred[rows_idx])))
        except ValueError:
            rows.append({})
    return pd.DataFrame(rows)


def bootstrap_all(
    y: dict[str, np.ndarray], systems: dict[str, dict[str, np.ndarray]], n: int, seed: int
) -> dict[tuple[str, str], pd.DataFrame]:
    """Bootstrap distributions for every (system, task), using one shared set of resamples."""
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(y["zscore"]), size=(n, len(y["zscore"])))
    jobs = [(s, t) for s, preds in systems.items() for t in preds]
    results = Parallel(n_jobs=min(14, len(jobs)))(
        delayed(boot_one)(t, y[t], systems[s][t], idx) for s, t in jobs
    )
    return dict(zip(jobs, results, strict=True))


def fmt(point: float, low: float, high: float) -> str:
    """'0.123 [0.100, 0.150]'."""
    return f"{point:.3f} [{low:.3f}, {high:.3f}]"


def ci(series: pd.Series) -> tuple[float, float]:
    """95 % percentile interval."""
    low, high = np.nanpercentile(series.to_numpy(dtype=float), [2.5, 97.5])
    return float(low), float(high)


# ---- tables ----------------------------------------------------------------------------------
def results_tables(
    y: dict[str, np.ndarray],
    systems: dict[str, dict[str, np.ndarray]],
    boots: dict[tuple[str, str], pd.DataFrame],
) -> dict[str, pd.DataFrame]:
    """One table per target: rows = systems, columns = metrics as 'point [low, high]'."""
    tables = {}
    for task in TASKS:
        rows = []
        for system, preds in systems.items():
            if task not in preds:
                continue
            point = scalar(target_metrics(task, y[task], preds[task]))
            boot = boots[(system, task)]
            row = {"system": LABEL.get(system, system)}
            for metric, value in point.items():
                low, high = ci(boot[metric]) if metric in boot else (np.nan, np.nan)
                row[metric] = fmt(value, low, high)
            rows.append(row)
        tables[task] = pd.DataFrame(rows)
    return tables


def full_metrics(
    y: dict[str, np.ndarray], systems: dict[str, dict[str, np.ndarray]]
) -> dict[str, Any]:
    """Per-class precision / recall and confusion matrices (point values) for every system."""
    out = {}
    for system, preds in systems.items():
        out[system] = {
            t: {k: v for k, v in target_metrics(t, y[t], preds[t]).items() if k in SCALAR_SKIP}
            for t in preds
        }
    return out


def seed_spread(
    y: dict[str, np.ndarray], seeds: dict[str, dict[str, list[np.ndarray]]]
) -> pd.DataFrame:
    """Primary test metric over the 5 seeds (mean, SD) - predictions are never averaged."""
    rows = []
    for system, tasks in seeds.items():
        for task, preds in tasks.items():
            values = [target_metrics(task, y[task], p)[PRIMARY[task][0]] for p in preds]
            rows.append(
                {
                    "system": system,
                    "task": task,
                    "metric": PRIMARY[task][0],
                    "mean": np.mean(values),
                    "sd": np.std(values, ddof=1),
                    "n_seeds": len(values),
                }
            )
    return pd.DataFrame(rows)


# ---- success criteria ------------------------------------------------------------------------
def verdict(point: float, low: float, threshold: float) -> str:
    """Locked rule: met / partly met / not met for a 'higher is better' statistic."""
    if point < threshold:
        return "not met"
    return "met" if low >= threshold else "partly met"


def criteria_for(
    system: str,
    y: dict[str, np.ndarray],
    systems: dict[str, dict[str, np.ndarray]],
    boots: dict[tuple[str, str], pd.DataFrame],
) -> list[dict[str, Any]]:
    """Every locked minimum for one system, with point value, CI and verdict."""
    crit = load_criteria()["targets"]
    rows = []
    for task, spec in crit.items():
        if task not in systems[system]:
            continue
        m, b = boots[(system, task)], boots[(BASELINE, task)]
        pm = scalar(target_metrics(task, y[task], systems[system][task]))
        pb = scalar(target_metrics(task, y[task], systems[BASELINE][task]))
        mins = spec["minimum"]

        def add(name: str, point: float, dist: pd.Series, threshold: float) -> None:
            low, high = ci(dist)
            rows.append(
                {
                    "system": system,
                    "target": task,  # noqa: B023 - add() is called within this iteration
                    "criterion": name,
                    "value": point,
                    "ci_low": low,
                    "ci_high": high,
                    "threshold": threshold,
                    "verdict": verdict(point, low, threshold),
                }
            )

        if task == "zscore":
            add(
                "MAE reduction vs baseline",
                1 - pm["mae"] / pb["mae"],
                1 - m["mae"] / b["mae"],
                mins["mae_reduction_vs_baseline"],
            )
            add("R-squared CI lower bound > 0", pm["r2"], m["r2"], 0.0)
            add("Spearman CI lower bound > 0", pm["spearman"], m["spearman"], 0.0)
        else:
            k = N_CLASSES[task]
            add(
                "macro F1 gain vs baseline",
                pm["macro_f1"] - pb["macro_f1"],
                m["macro_f1"] - b["macro_f1"],
                mins["macro_f1_gain_vs_baseline"],
            )
            add(
                "balanced accuracy CI lower bound > chance",
                pm["balanced_accuracy"],
                m["balanced_accuracy"],
                1 / k,
            )
            if "qwk_ci_lower_above" in mins:
                add("QWK CI lower bound > 0", pm["qwk"], m["qwk"], 0.0)
            add(
                "ROC-AUC CI lower bound > 0.5", pm["roc_auc_ovr_macro"], m["roc_auc_ovr_macro"], 0.5
            )
            add(
                "log loss below baseline (baseline minus model)",
                pb["log_loss"] - pm["log_loss"],
                b["log_loss"] - m["log_loss"],
                0.0,
            )
    return rows


def apply_temperature(proba: np.ndarray, t: float) -> np.ndarray:
    """Temperature-scaled probabilities."""
    z = np.log(np.clip(proba, 1e-12, 1)) / t
    z = z - z.max(axis=1, keepdims=True)
    return np.exp(z) / np.exp(z).sum(axis=1, keepdims=True)


def calibration(
    y: dict[str, np.ndarray],
    systems: dict[str, dict[str, np.ndarray]],
    selected: str,
    n: int,
    seed: int,
) -> pd.DataFrame:
    """ECE and Brier skill score with CIs, before and after the validation-fitted temperature."""
    calib = load_criteria()["calibration"]
    temps = json.loads((P6 / "temperatures_seed0.json").read_text("utf-8"))
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(y["zscore"]), size=(n, len(y["zscore"])))
    rows = []
    for system, preds in systems.items():
        if system == BASELINE:
            continue
        source = selected if system == CHOSEN else system
        for task in CLASS_TASKS:
            if task not in preds or source not in temps:
                continue
            base = systems[BASELINE][task]
            for scaled in (False, True):
                p = apply_temperature(preds[task], temps[source][task]) if scaled else preds[task]
                yy = y[task]
                ece = expected_calibration_error(yy, p, calib["ece_bins"])
                brier = target_metrics(task, yy, p)["brier"]
                bb = target_metrics(task, yy, base)["brier"]
                eces, bss = [], []
                for r in idx:
                    eces.append(expected_calibration_error(yy[r], p[r], calib["ece_bins"]))
                    b_r = ((base[r] - np.eye(p.shape[1])[yy[r]]) ** 2).sum(1).mean()
                    m_r = ((p[r] - np.eye(p.shape[1])[yy[r]]) ** 2).sum(1).mean()
                    bss.append(1 - m_r / b_r)
                e_low, e_high = np.percentile(eces, [2.5, 97.5])
                s_low, s_high = np.percentile(bss, [2.5, 97.5])
                rows.append(
                    {
                        "system": system,
                        "target": task,
                        "temperature": temps[source][task] if scaled else 1.0,
                        "scaled": scaled,
                        "ece": ece,
                        "ece_ci": f"[{e_low:.3f}, {e_high:.3f}]",
                        "ece_meets_max": bool(ece <= calib["max_ece"]),
                        "brier_skill": 1 - brier / bb,
                        "brier_skill_ci": f"[{s_low:.3f}, {s_high:.3f}]",
                        "brier_skill_ci_lower_above_0": bool(s_low > 0),
                    }
                )
    return pd.DataFrame(rows)


# ---- comparisons -----------------------------------------------------------------------------
def oriented(task: str, values: pd.Series | float) -> pd.Series | float:
    """Primary metric oriented so higher is better."""
    return -values if PRIMARY[task][1] == "lower" else values


def compare_to_chosen(
    boots: dict[tuple[str, str], pd.DataFrame], systems: dict[str, Any], y: dict[str, np.ndarray]
) -> pd.DataFrame:
    """Paired difference (system minus chosen, higher = system better) for every system and task."""
    rows = []
    for system, preds in systems.items():
        if system in (CHOSEN, BASELINE):
            continue
        for task in preds:
            name = PRIMARY[task][0]
            diff = oriented(task, boots[(system, task)][name]) - oriented(
                task, boots[(CHOSEN, task)][name]
            )
            point = oriented(task, target_metrics(task, y[task], preds[task])[name]) - oriented(
                task, target_metrics(task, y[task], systems[CHOSEN][task])[name]
            )
            low, high = ci(diff)
            rows.append(
                {
                    "system": system,
                    "target": task,
                    "metric": name,
                    "diff_vs_chosen": point,
                    "ci_low": low,
                    "ci_high": high,
                    "result": "better"
                    if low > 0
                    else "worse"
                    if high < 0
                    else "not distinguishable",
                }
            )
    return pd.DataFrame(rows)


def negative_transfer(
    boots: dict[tuple[str, str], pd.DataFrame],
    systems: dict[str, Any],
    y: dict[str, np.ndarray],
    selected: str,
) -> pd.DataFrame:
    """H6 on test: multi-output network minus single-task network of the same architecture."""
    rows = []
    for model in sorted({selected, "mtl"}):
        for task in TASKS:
            single = f"single_{model}_{task}"
            if single not in systems:
                continue
            name = PRIMARY[task][0]
            diff = oriented(task, boots[(model, task)][name]) - oriented(
                task, boots[(single, task)][name]
            )
            point = oriented(
                task, target_metrics(task, y[task], systems[model][task])[name]
            ) - oriented(task, target_metrics(task, y[task], systems[single][task])[name])
            low, high = ci(diff)
            rows.append(
                {
                    "model": model,
                    "target": task,
                    "metric": name,
                    "multi_minus_single": point,
                    "ci_low": low,
                    "ci_high": high,
                    "result": "positive transfer"
                    if low > 0
                    else "negative transfer"
                    if high < 0
                    else "no difference detected",
                }
            )
    return pd.DataFrame(rows)


def group_score(task: str, yy: np.ndarray, pp: np.ndarray) -> float:
    """Primary metric inside a subgroup: MAE, or macro F1 over the classes PRESENT in the subgroup.

    Averaging over all classes would count classes that cannot occur in the subgroup
    (e.g. Engineering among Biology students) as zero and understate the score.
    """
    if task == "zscore":
        return float(np.mean(np.abs(yy - pp)))
    return float(
        skm.f1_score(yy, pp.argmax(axis=1), labels=np.unique(yy), average="macro", zero_division=0)
    )


def training_groups(column: str) -> pd.DataFrame:
    """Training rows with their group label and encoded targets (for within-group baselines)."""
    from src.data.split import load_split_rows
    from src.features.run_phase04 import add_targets
    from src.models.cv import band_edges

    rows = load_split_rows("train")
    targets = encode_targets(add_targets(rows, band_edges()))
    frame = pd.DataFrame({t: targets[t] for t in TASKS})
    frame["group"] = rows[column].astype(str).to_numpy()
    return frame


def by_group(
    y: dict[str, np.ndarray],
    preds: dict[str, np.ndarray],
    groups: np.ndarray,
    train: pd.DataFrame,
    n: int,
    seed: int,
) -> pd.DataFrame:
    """Chosen system within each group, with bootstrap CIs and a within-group baseline.

    The baseline predicts, for every member of the group, the training mean Z-score or the
    most common training class *of that same group*.
    """
    rng = np.random.default_rng(seed)
    rows = []
    for group in sorted(set(groups)):
        mask = groups == group
        part = train[train["group"] == group]
        for task in TASKS:
            yy, pp = y[task][mask], preds[task][mask]
            name = "mae" if task == "zscore" else "macro_f1_present_classes"
            point = group_score(task, yy, pp)
            values = []
            for _ in range(n):
                r = rng.integers(0, mask.sum(), mask.sum())
                values.append(group_score(task, yy[r], pp[r]))
            low, high = np.percentile(values, [2.5, 97.5])
            row = {
                "group": group,
                "n": int(mask.sum()),
                "target": task,
                "metric": name,
                "value": point,
                "ci": f"[{low:.3f}, {high:.3f}]",
            }
            if task == "zscore":
                row["baseline_within_group"] = float(np.mean(np.abs(yy - part[task].mean())))
            else:
                majority = part[task].mode().iloc[0]
                row["accuracy"] = float((pp.argmax(axis=1) == yy).mean())
                row["baseline_accuracy_within_group"] = float((yy == majority).mean())
            rows.append(row)
    return pd.DataFrame(rows)


# ---- hypotheses ------------------------------------------------------------------------------
def hypotheses(criteria: pd.DataFrame, calib: pd.DataFrame, transfer: pd.DataFrame) -> pd.DataFrame:
    """H1-H6 verdicts for the chosen system (Phase 2, locked)."""
    c = criteria[criteria["system"] == CHOSEN]
    rows = []
    for hid, task in (
        ("H1", "zscore"),
        ("H2", "zscore_band"),
        ("H3", "university_group"),
        ("H4", "degree_category"),
    ):
        part = c[c["target"] == task]
        primary = part.iloc[0]
        all_met = bool((part["verdict"] == "met").all())
        status = (
            "Supported"
            if all_met
            else "Partly supported"
            if primary["verdict"] != "not met"
            else "Not supported"
        )
        rows.append(
            {
                "hypothesis": hid,
                "target": task,
                "result": status,
                "evidence": f"{primary['criterion']}: {primary['value']:.3f} "
                f"[{primary['ci_low']:.3f}, {primary['ci_high']:.3f}] vs {primary['threshold']}; "
                f"other minima met: {int((part['verdict'] == 'met').sum())}/{len(part)}",
            }
        )
    raw = calib[(calib["system"] == CHOSEN) & ~calib["scaled"]]
    ok = raw["ece_meets_max"].all() and raw["brier_skill_ci_lower_above_0"].all()
    scaled = calib[(calib["system"] == CHOSEN) & calib["scaled"]]
    ok_scaled = scaled["ece_meets_max"].all() and scaled["brier_skill_ci_lower_above_0"].all()
    rows.append(
        {
            "hypothesis": "H5",
            "target": "calibration",
            "result": "Supported"
            if ok
            else "Supported after temperature scaling"
            if ok_scaled
            else "Not supported",
            "evidence": "; ".join(
                f"{r.target}: ECE {r.ece:.3f} {r.ece_ci}, "
                f"BSS {r.brier_skill:.3f} {r.brier_skill_ci}"
                for r in raw.itertuples()
            ),
        }
    )
    found = transfer[transfer["result"] != "no difference detected"]
    rows.append(
        {
            "hypothesis": "H6",
            "target": "multi-task vs single-task",
            "result": "Supported (difference found)"
            if not found.empty
            else "Not supported (no difference detected)",
            "evidence": "; ".join(
                f"{r.model}/{r.target}: {r.result}" for r in transfer.itertuples()
            ),
        }
    )
    return pd.DataFrame(rows)


# ---- figures ---------------------------------------------------------------------------------
def plot_comparison(
    y: dict[str, np.ndarray], systems: dict[str, Any], boots: dict, out: Path, label: str
) -> None:
    """Primary metric per system with 95 % bootstrap CIs, one panel per target."""
    order = [
        "mlp",
        "reg_dnn",
        "wide_deep",
        "tabnet",
        "mtl",
        "entity_mlp",
        "ae_mlp",
        "resnet",
        "stage2_zscore_mlp",
        CHOSEN,
        BASELINE,
    ]
    fig, axes = plt.subplots(2, 2, figsize=(12, 8.5))
    for ax, task in zip(axes.ravel(), TASKS, strict=True):
        names = [s for s in order if s in systems and task in systems[s]]
        metric = PRIMARY[task][0]
        points, lows, highs = [], [], []
        for s in names:
            p = target_metrics(task, y[task], systems[s][task])[metric]
            lo, hi = ci(boots[(s, task)][metric])
            points.append(p)
            lows.append(p - lo)
            highs.append(hi - p)
        pos = np.arange(len(names))
        colours = [
            CATEGORICAL[1] if s == CHOSEN else INK["muted"] if s == BASELINE else CATEGORICAL[0]
            for s in names
        ]
        ax.barh(
            pos,
            points,
            xerr=[lows, highs],
            color=colours,
            height=0.6,
            error_kw={"ecolor": INK["secondary"], "capsize": 3},
        )
        ax.set_yticks(pos)
        ax.set_yticklabels([LABEL.get(s, s) for s in names], fontsize=8.5)
        ax.invert_yaxis()
        ax.grid(axis="y", visible=False)
        ax.set_title(
            f"{task.replace('_', ' ').capitalize()} ({metric}"
            f"{', lower is better' if task == 'zscore' else ''})",
            loc="left",
            fontsize=11,
        )
    fig.suptitle(
        f"Results on the {label} set (seed 0, 95 % bootstrap CIs)",
        x=0.01,
        ha="left",
        fontweight="bold",
    )
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    save_figure(fig, out / "comparison.png")


def plot_confusions(full: dict[str, Any], out: Path, label: str) -> None:
    """Confusion matrices of the chosen system (rows = true, columns = predicted)."""
    names = class_names()
    fig, axes = plt.subplots(1, 3, figsize=(16, 5.5), gridspec_kw={"width_ratios": [3, 5, 7]})
    for ax, task in zip(axes, CLASS_TASKS, strict=True):
        cm = np.array(full[CHOSEN][task]["confusion_matrix"])
        ax.imshow(cm, cmap="Blues")
        labels = (
            [f"Band {int(c) + 1}" for c in names[task]] if task == "zscore_band" else names[task]
        )
        short = [
            lbl.replace("Computing, IT, AI or Data Science", "Computing")
            .replace(" or ", "/")
            .replace("Agriculture/Food Science", "Agri/Food")
            .replace("Allied Health Sciences", "Allied Health")
            .replace("North Central and North Western", "NC & NW")
            .replace("Northern and Eastern", "N & E")
            .replace("Central and Highlands", "Central/Highl.")
            for lbl in labels
        ]
        ax.set_xticks(range(len(short)))
        ax.set_xticklabels(short, rotation=45, ha="right", fontsize=8)
        ax.set_yticks(range(len(short)))
        ax.set_yticklabels(short, fontsize=8)
        ax.grid(False)
        for i in range(cm.shape[0]):
            for j in range(cm.shape[1]):
                ax.text(
                    j,
                    i,
                    cm[i, j],
                    ha="center",
                    va="center",
                    fontsize=8,
                    color="white" if cm[i, j] > cm.max() * 0.5 else INK["primary"],
                )
        ax.set_xlabel("Predicted")
        ax.set_ylabel("True")
        ax.set_title(task.replace("_", " ").capitalize(), loc="left", fontsize=11)
    fig.suptitle(
        f"Chosen system: confusion matrices on the {label} set",
        x=0.01,
        ha="left",
        fontweight="bold",
    )
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    save_figure(fig, out / "confusion_matrices.png")


def plot_reliability(
    y: dict[str, np.ndarray], systems: dict[str, Any], selected: str, out: Path, label: str
) -> None:
    """Reliability of the chosen system, before and after the validation-fitted temperature."""
    temps = json.loads((P6 / "temperatures_seed0.json").read_text("utf-8"))[selected]
    fig, axes = plt.subplots(1, 3, figsize=(14, 4.6))
    for ax, task in zip(axes, CLASS_TASKS, strict=True):
        ax.plot([0, 1], [0, 1], color=INK["muted"], linestyle=":", label="Perfect")
        for scaled, colour, name in (
            (False, CATEGORICAL[0], "As trained"),
            (True, CATEGORICAL[1], f"Temperature {temps[task]:.2f}"),
        ):
            p = (
                apply_temperature(systems[CHOSEN][task], temps[task])
                if scaled
                else systems[CHOSEN][task]
            )
            bins = pd.DataFrame(reliability_curve(y[task], p))
            ax.plot(bins["confidence"], bins["accuracy"], marker="o", color=colour, label=name)
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.set_xlabel("Predicted confidence")
        ax.set_ylabel("Observed accuracy")
        ax.set_title(task.replace("_", " ").capitalize(), loc="left", fontsize=11)
        ax.legend(fontsize=8, loc="upper left")
    fig.suptitle(
        f"Chosen system: reliability on the {label} set", x=0.01, ha="left", fontweight="bold"
    )
    fig.tight_layout(rect=(0, 0, 1, 0.92))
    save_figure(fig, out / "reliability.png")


# ---- main ------------------------------------------------------------------------------------
def analyse(pred_file: Path, out: Path, label: str) -> None:
    """Compute every Phase 7 table and figure from saved predictions."""
    apply_style()
    out.mkdir(parents=True, exist_ok=True)
    rules = load_criteria()["general"]["confidence_intervals"]
    n, seed = rules["resamples"], 0
    y, systems, extra = load(pred_file)
    boots = bootstrap_all(y, systems, n, seed)

    for task, table in results_tables(y, systems, boots).items():
        table.to_csv(out / f"results_{task}.csv", index=False)
    (out / "per_class_and_confusion.json").write_text(
        json.dumps(full_metrics(y, systems), indent=1), "utf-8"
    )
    seed_spread(y, extra["seed_predictions"]).to_csv(out / "seed_spread.csv", index=False)

    criteria = pd.DataFrame(
        [row for s in systems if s != BASELINE for row in criteria_for(s, y, systems, boots)]
    )
    criteria.to_csv(out / "success_criteria.csv", index=False)
    calib = calibration(y, systems, extra["selected"], n, seed)
    calib.to_csv(out / "calibration.csv", index=False)
    comparison = compare_to_chosen(boots, systems, y)
    comparison.to_csv(out / "comparison_with_chosen.csv", index=False)
    transfer = negative_transfer(boots, systems, y, extra["selected"])
    transfer.to_csv(out / "negative_transfer.csv", index=False)
    by_group(
        y,
        systems[CHOSEN],
        extra["subject_combination"],
        training_groups("al_subject_combination"),
        n,
        seed,
    ).to_csv(out / "chosen_by_subject_combination.csv", index=False)
    by_group(y, systems[CHOSEN], extra["gender"], training_groups("gender"), n, seed).to_csv(
        out / "chosen_by_gender.csv", index=False
    )
    hyp = hypotheses(criteria, calib, transfer)
    hyp.to_csv(out / "hypotheses.csv", index=False)

    full = full_metrics(y, systems)
    plot_comparison(y, systems, boots, out, label)
    plot_confusions(full, out, label)
    plot_reliability(y, systems, extra["selected"], out, label)
    summary = {
        "label": label,
        "rows": int(len(y["zscore"])),
        "chosen_z_source": extra["z_source"],
        "hypotheses": hyp.set_index("hypothesis")["result"].to_dict(),
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2), "utf-8")
    logger.info("Phase 7 analysis (%s) written to %s: %s", label, out, summary["hypotheses"])
