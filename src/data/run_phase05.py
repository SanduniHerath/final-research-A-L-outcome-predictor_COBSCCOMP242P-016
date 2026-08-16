"""Run Phase 5: class balance per split, imbalance handling and cross-validation folds.

    python -m src.data.run_phase05

The test split is used only to COUNT its target labels (the brief asks for class balance
in every split). :func:`target_labels_by_split` reads nothing else from test rows.
"""

from __future__ import annotations

import json
import sys
import textwrap

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.model_selection import RepeatedStratifiedKFold

from src.data.imbalance import class_weights, imbalance_ratio, needs_weights
from src.data.labels import assign_band
from src.data.load import ID_COLUMN
from src.data.split import SPLIT_COLUMN, modelling_rows, verify_split
from src.utils.config import get_seed, load_config, resolve_path
from src.utils.logging_setup import get_logger
from src.utils.plot_style import CATEGORICAL, INK, apply_style, save_figure

logger = get_logger(__name__)

CLASS_TARGETS = ["zscore_band", "university_group", "degree_category"]
SPLITS = ["train", "validation", "test"]
COUNT_ONLY = ["zscore", "university_group", "degree_category", "gender"]


def target_labels_by_split() -> pd.DataFrame:
    """Return ID, split, stratum and ONLY the target labels (plus gender for fairness counts)."""
    split = pd.read_csv(resolve_path(load_config("split")["files"]["split"]))
    verify_split(split)
    labels = modelling_rows()[[ID_COLUMN, *COUNT_ONLY]]
    table = split.merge(labels, on=ID_COLUMN, how="left", validate="one_to_one")
    edges = json.loads(
        (
            resolve_path(load_config("project")["paths"]["processed"]) / "zscore_band_edges.json"
        ).read_text("utf-8")
    )["edges"]
    table["zscore_band"] = assign_band(table["zscore"], edges).astype(int)
    return table


def balance_table(table: pd.DataFrame, target: str) -> pd.DataFrame:
    """Counts and shares of each class per split."""
    counts = pd.crosstab(table[target], table[SPLIT_COLUMN])[SPLITS]
    shares = counts / counts.sum()
    out = counts.add_suffix("_n").join(shares.round(4).add_suffix("_share"))
    out["max_share_gap"] = shares.max(axis=1) - shares.min(axis=1)
    return out


def zscore_summary(table: pd.DataFrame) -> pd.DataFrame:
    """Mean, SD, quartiles and range of the Z-score per split."""
    return table.groupby(SPLIT_COLUMN)["zscore"].describe().loc[SPLITS].round(4)


def make_folds(train: pd.DataFrame, folds: int, repeats: int, seed: int) -> pd.DataFrame:
    """Assign every training row to a validation fold in each repeat (stratified by stratum)."""
    splitter = RepeatedStratifiedKFold(n_splits=folds, n_repeats=repeats, random_state=seed)
    rows = []
    for i, (_, val_idx) in enumerate(splitter.split(train, train["stratum"])):
        repeat, fold = divmod(i, folds)
        for idx in val_idx:
            rows.append({ID_COLUMN: train[ID_COLUMN].iat[idx], "repeat": repeat, "fold": fold})
    return pd.DataFrame(rows).sort_values(["repeat", "fold", ID_COLUMN]).reset_index(drop=True)


def fold_balance(train: pd.DataFrame, folds: pd.DataFrame) -> pd.DataFrame:
    """Largest difference between a fold's class share and the whole training share."""
    merged = folds.merge(train, on=ID_COLUMN)
    rows = []
    for target in CLASS_TARGETS:
        overall = train[target].value_counts(normalize=True)
        for (repeat, fold), part in merged.groupby(["repeat", "fold"]):
            share = part[target].value_counts(normalize=True).reindex(overall.index, fill_value=0)
            rows.append(
                {
                    "target": target,
                    "repeat": repeat,
                    "fold": fold,
                    "rows": len(part),
                    "max_abs_share_diff": float((share - overall).abs().max()),
                }
            )
    return pd.DataFrame(rows)


def plot_balance(table: pd.DataFrame, path: object) -> None:
    """Small multiples: class shares per split for the three class targets."""
    titles = {
        "zscore_band": "Z-score band",
        "university_group": "University group",
        "degree_category": "Degree category",
    }
    fig, axes = plt.subplots(1, 3, figsize=(15, 5.2), gridspec_kw={"width_ratios": [3, 5, 7]})
    for ax, target in zip(axes, CLASS_TARGETS, strict=True):
        shares = pd.crosstab(table[target], table[SPLIT_COLUMN], normalize="columns")[SPLITS]
        labels = [f"Band {int(c) + 1}" if target == "zscore_band" else str(c) for c in shares.index]
        x = np.arange(len(shares))
        width = 0.26
        for k, split in enumerate(SPLITS):
            ax.bar(
                x + (k - 1) * width,
                shares[split] * 100,
                width=width - 0.03,
                color=CATEGORICAL[k],
                label=split.capitalize(),
            )
        ax.set_xticks(x)
        ax.set_xticklabels([textwrap.fill(lbl, 12) for lbl in labels], fontsize=8.5)
        ax.set_title(titles[target], loc="left", fontsize=11)
        ax.set_ylabel("Share of split (%)")
        ax.grid(axis="x", visible=False)
    handles, names = axes[0].get_legend_handles_labels()
    fig.legend(handles, names, loc="upper right", ncol=3, frameon=False)
    fig.suptitle(
        "Class balance in train (709), validation (152) and test (153)",
        x=0.01,
        ha="left",
        fontweight="bold",
        color=INK["primary"],
    )
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    save_figure(fig, path)


def main() -> int:
    """Write balance tables, imbalance handling, CV folds and the balance figure."""
    cfg = load_config("split")
    paths = load_config("project")["paths"]
    out = resolve_path(paths["reports"]) / "phase05"
    out.mkdir(parents=True, exist_ok=True)
    apply_style()

    table = target_labels_by_split()
    summary: dict[str, object] = {"rows": table[SPLIT_COLUMN].value_counts()[SPLITS].to_dict()}
    for target in [*CLASS_TARGETS, "gender"]:
        balance = balance_table(table, target)
        balance.to_csv(out / f"balance_{target}.csv")
        summary[f"max_share_gap_{target}"] = round(float(balance["max_share_gap"].max()), 4)
    zscore_summary(table).to_csv(out / "zscore_by_split.csv")

    train = table[table[SPLIT_COLUMN] == "train"].reset_index(drop=True)
    threshold = cfg["imbalance"]["weight_if_ratio_above"]
    imbalance = {}
    for target in CLASS_TARGETS:
        labels = train[target].astype(str)
        imbalance[target] = {
            "ratio": round(imbalance_ratio(labels), 3),
            "weighted": needs_weights(labels, threshold),
            "weights_full_training_split": {
                k: round(v, 4) for k, v in class_weights(labels).items()
            },
        }
    (out / "imbalance_train.json").write_text(json.dumps(imbalance, indent=2), "utf-8")

    cv = cfg["cross_validation"]
    folds = make_folds(train, cv["folds"], cv["repeats"], get_seed())
    folds_path = resolve_path(cfg["cv_files"]["folds"])
    folds.to_csv(folds_path, index=False)
    fb = fold_balance(train, folds)
    fb.to_csv(out / "fold_balance.csv", index=False)
    summary["fold_sizes"] = sorted(folds.groupby(["repeat", "fold"]).size().unique().tolist())
    summary["fold_max_share_diff"] = (
        fb.groupby("target")["max_abs_share_diff"].max().round(4).to_dict()
    )
    summary["imbalance"] = {t: (v["ratio"], v["weighted"]) for t, v in imbalance.items()}

    plot_balance(table, resolve_path(paths["figures"]) / "phase05_class_balance.png")
    (out / "summary.json").write_text(json.dumps(summary, indent=2, default=str), "utf-8")
    logger.info("Phase 5 summary: %s", summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
