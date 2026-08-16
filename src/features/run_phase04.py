"""Run Phase 4: fit the feature pipeline on the training split and test feature selection.

    python -m src.features.run_phase04

Only the training and validation splits are read; the test split stays locked.
Outputs:
    models/feature_pipeline.joblib            fitted pipeline (training rows only)
    data/processed/features_{train,validation}.csv  features + targets (not committed)
    data/processed/zscore_band_edges.json     band edges from the training split
    reports/phase04/*.csv, *.json             catalogue, skew, relevance, redundancy, feature sets
    reports/figures/phase04_relevance.png
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import joblib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.data.labels import assign_band, band_edges
from src.data.load import ID_COLUMN
from src.data.split import load_split_rows
from src.features.build import FeaturePipeline, add_fixed_composites, encode_raw, scale_items
from src.features.selection import redundancy_table, redundant_to_drop, relevance_table
from src.utils.config import load_config, resolve_path
from src.utils.logging_setup import get_logger
from src.utils.plot_style import INK, apply_style, save_figure

logger = get_logger(__name__)

TARGETS = {
    "zscore": "numeric",
    "zscore_band": "class",
    "university_group": "class",
    "degree_category": "class",
}
COMPOSITES = [
    "ol_core_mean",
    "ol_all_mean",
    "ol_n_A",
    "ol_sci_maths_mean",
    "self_efficacy_index",
    "effort_regulation_index",
    "effort_regulation_index_no_er4",
    "interest_index",
    "motivation_index",
    "effort_index",
    "goal_clarity_index",
    "activity_count",
    "leadership_count",
    "school_performance_index",
]


def add_targets(rows: pd.DataFrame, edges: list[float]) -> pd.DataFrame:
    """Return the four targets for a split, using the frozen training band edges."""
    return pd.DataFrame(
        {
            ID_COLUMN: rows[ID_COLUMN],
            "zscore": rows["zscore"],
            "zscore_band": assign_band(rows["zscore"], edges).astype(int),
            "university_group": rows["university_group"],
            "degree_category": rows["degree_category"],
        }
    )


def source_level_features(
    train: pd.DataFrame, pipe: FeaturePipeline
) -> tuple[pd.DataFrame, dict[str, str]]:
    """Return training features at question level (nominals unexpanded) and their kinds.

    Associations are measured on the encoded but unscaled values; scaling does not change
    rank-based measures, and nominal questions are tested as one variable, not per dummy.
    """
    cfg = pipe.cfg
    encoded = pipe._with_standardised_composites(add_fixed_composites(encode_raw(train, cfg), cfg))
    encoded = encoded.fillna(pipe.medians_).fillna(pipe.binary_means_)
    kinds = {c: "ordinal" for c in pipe.numeric_}
    kinds.update({c: "binary" for c in pipe.binary_})
    kinds.update({c: "nominal" for c in cfg["nominal_onehot"] + cfg["nominal_many"]})
    return encoded[list(kinds)], kinds


def feature_catalogue(pipe: FeaturePipeline, cfg: dict[str, Any]) -> pd.DataFrame:
    """One row per model feature: name, source, type, formula and reason."""
    comp = cfg["composites"]
    rows = []
    for name in pipe.numeric_:
        if name in comp:
            rows.append(
                {
                    "feature": name,
                    "source": ", ".join(comp[name]["columns"]),
                    "type": "composite (standardised)",
                    "formula": comp[name]["formula"],
                    "reason": comp[name]["reason"],
                }
            )
        else:
            transform = "Yeo-Johnson, " if name in pipe.skewed_ else ""
            rows.append(
                {
                    "feature": name,
                    "source": name,
                    "type": "ordinal (standardised)",
                    "formula": f"ordinal code, {transform}median-imputed, standardised",
                    "reason": "answer to the questionnaire item",
                }
            )
    for name in pipe.binary_:
        rows.append(
            {
                "feature": name,
                "source": name,
                "type": "0/1",
                "formula": "0/1; skipped answers filled with the training share",
                "reason": "ticked option or skipped-question indicator",
            }
        )
    for name in pipe.onehot_names:
        rows.append(
            {
                "feature": name,
                "source": name.split("_")[0],
                "type": "one-hot",
                "formula": "1 if this category, else 0; unseen categories all 0",
                "reason": "nominal answer",
            }
        )
    rows.append(
        {
            "feature": "al_district_index",
            "source": "al_district",
            "type": "integer index",
            "formula": "1..25 by training districts, 0 = unknown",
            "reason": "input for the entity-embedding model only",
        }
    )
    return pd.DataFrame(rows)


def feature_sets(
    pipe: FeaturePipeline, relevance: pd.DataFrame, drop: list[str]
) -> dict[str, list[str]]:
    """Return the three candidate feature sets (model-ready column names)."""
    cfg = pipe.cfg
    onehot_by_source = {
        src: [c for c in pipe.onehot_names if c.startswith(src + "_")]
        for src in cfg["nominal_onehot"] + cfg["nominal_many"]
    }
    full = pipe.numeric_ + pipe.binary_ + pipe.onehot_names
    items = set(scale_items(cfg))
    composites = [c for c in full if c not in items]
    keep_sources = set(relevance.loc[relevance["significant"], "feature"]) - set(drop)
    filtered = [c for c in pipe.numeric_ + pipe.binary_ if c in keep_sources]
    for src, cols in onehot_by_source.items():
        if src in keep_sources:
            filtered += cols
    return {"full": full, "composites": composites, "filtered": filtered}


def plot_relevance(relevance: pd.DataFrame, path: Path, top: int = 25) -> None:
    """Heatmap of absolute effect sizes for the features most associated with any target."""
    pivot = relevance.pivot_table(index="feature", columns="target", values="abs_effect")
    pivot = pivot[list(TARGETS)]
    order = pivot.max(axis=1).sort_values(ascending=False).index[:top]
    data = pivot.loc[order]
    sig = relevance.pivot_table(index="feature", columns="target", values="significant")
    sig = sig.loc[order][list(TARGETS)]
    vmax = max(0.5, float(np.nanmax(data.to_numpy())))
    fig, ax = plt.subplots(figsize=(8, 10))
    image = ax.imshow(data.to_numpy(), cmap="Blues", vmin=0, vmax=vmax, aspect="auto")
    ax.set_xticks(range(len(TARGETS)))
    ax.set_xticklabels(["Z-score", "Z-score\nband", "University\ngroup", "Degree\ncategory"])
    ax.xaxis.tick_top()
    ax.set_yticks(range(len(order)))
    ax.set_yticklabels(order, fontsize=9)
    ax.grid(False)
    for i in range(len(order)):
        for j in range(len(TARGETS)):
            value = data.iat[i, j]
            star = "*" if bool(sig.iat[i, j]) else ""
            ax.text(
                j,
                i,
                f"{value:.2f}{star}",
                ha="center",
                va="center",
                fontsize=8,
                color="white" if value > 0.45 * vmax else INK["primary"],
            )
    fig.colorbar(image, ax=ax, fraction=0.04, pad=0.03, label="Effect size (absolute)")
    ax.set_title(
        "Strongest training-set associations (* = significant after FDR correction)",
        loc="left",
        pad=36,
    )
    ax.text(
        0,
        -0.02,
        "Measures: Spearman / point-biserial (Z-score); epsilon-squared or Cramer's V "
        "(class targets).\nAssociation, not causation.",
        transform=ax.transAxes,
        fontsize=8,
        va="top",
        color=INK["secondary"],
    )
    save_figure(fig, path)


def main() -> int:
    """Fit the pipeline on training rows, write features and the selection report."""
    cfg = load_config("features")
    labels_cfg = load_config("labels")
    paths = load_config("project")["paths"]
    out = resolve_path(paths["reports"]) / "phase04"
    out.mkdir(parents=True, exist_ok=True)
    processed = resolve_path(paths["processed"])
    apply_style()

    train, validation = load_split_rows("train"), load_split_rows("validation")
    edges = band_edges(train["zscore"], labels_cfg["targets"]["zscore_band"]["n_bands"])
    (processed / "zscore_band_edges.json").write_text(
        json.dumps({"edges": edges, "fitted_on": "train", "rows": len(train)}, indent=2), "utf-8"
    )

    pipe = FeaturePipeline(cfg).fit(train)
    joblib.dump(pipe, resolve_path(paths["models"]) / "feature_pipeline.joblib")
    for name, rows in (("train", train), ("validation", validation)):
        features = pipe.transform(rows)
        table = pd.concat([add_targets(rows, edges), features], axis=1)
        table.to_csv(processed / f"features_{name}.csv", index=False)

    feature_catalogue(pipe, cfg).to_csv(out / "feature_catalogue.csv", index=False)
    pipe.skew_table_.to_csv(out / "skew_train.csv")

    source, kinds = source_level_features(train, pipe)
    targets = add_targets(train, edges)
    relevance = relevance_table(source, kinds, targets, TARGETS, cfg["selection"]["alpha"])
    relevance.sort_values(["target", "abs_effect"], ascending=[True, False]).to_csv(
        out / "relevance_train.csv", index=False
    )
    numeric_source = source[[c for c, k in kinds.items() if k == "ordinal"]]
    pairs = redundancy_table(numeric_source, cfg["selection"]["redundancy_abs_spearman"])
    pairs.to_csv(out / "redundancy_train.csv", index=False)
    preferred = COMPOSITES + [c for c in pipe.numeric_ if c not in COMPOSITES]
    drop = redundant_to_drop(pairs, preferred)
    sets = feature_sets(pipe, relevance, drop)
    (out / "feature_sets.json").write_text(
        json.dumps(
            {
                "redundant_dropped_in_filtered": drop,
                "sizes": {k: len(v) for k, v in sets.items()},
                "sets": sets,
            },
            indent=2,
        ),
        "utf-8",
    )
    plot_relevance(relevance, resolve_path(paths["figures"]) / "phase04_relevance.png")

    summary = {
        "train_rows": len(train),
        "validation_rows": len(validation),
        "band_edges": edges,
        "band_counts_train": targets["zscore_band"].value_counts().sort_index().to_dict(),
        "features_total": len(sets["full"]) + 1,
        "numeric": len(pipe.numeric_),
        "binary": len(pipe.binary_),
        "onehot": len(pipe.onehot_names),
        "dropped_constant": pipe.dropped_constant_,
        "skew_transformed": pipe.skewed_,
        "significant_pairs": int(relevance["significant"].sum()),
        "tests": len(relevance),
        "redundant_pairs": len(pairs),
        "feature_set_sizes": {k: len(v) for k, v in sets.items()},
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2, default=str), "utf-8")
    logger.info("Phase 4 summary: %s", summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
