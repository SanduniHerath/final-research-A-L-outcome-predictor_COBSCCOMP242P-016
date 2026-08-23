"""Phase 6 orchestration: feature-set choice, er4 choice, random search, architecture selection.

    python -m src.models.run_phase06 --step all      # or features / er4 / search / select

Every step is resumable (finished runs are read from reports/phase06/runs.jsonl) and every
decision is written to reports/phase06/decisions.json with the numbers behind it. Only
training-split cross-validation is used here; the test split is never read.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

import pandas as pd

from src.evaluation.criteria import load_criteria, require_locked
from src.models import cv
from src.utils.config import load_config, resolve_path
from src.utils.logging_setup import get_logger

logger = get_logger(__name__)

MODELS = list(load_config("models")["models"])
OUT = resolve_path(load_config("project")["paths"]["reports"]) / "phase06"


def decisions() -> dict[str, Any]:
    """Decisions recorded so far."""
    path = OUT / "decisions.json"
    return json.loads(path.read_text("utf-8")) if path.exists() else {}


def record_decision(key: str, value: Any) -> None:
    """Add or replace one decision."""
    data = decisions()
    data[key] = value
    (OUT / "decisions.json").write_text(json.dumps(data, indent=2, default=str), "utf-8")


def feature_sets() -> dict[str, list[str]]:
    """The three candidate feature sets from Phase 4."""
    path = (
        resolve_path(load_config("project")["paths"]["reports"]) / "phase04" / "feature_sets.json"
    )
    return json.loads(path.read_text("utf-8"))["sets"]


def default_cfg(model: str) -> dict[str, Any]:
    """Default configuration of a model."""
    return dict(load_config("models")["models"][model]["default"])


def compare_variants(
    records: list[dict[str, Any]], sizes: dict[str, int]
) -> tuple[str, pd.DataFrame]:
    """Rank variants within each model, average over models; ties -> fewer columns."""
    table = cv.primary_table(records, ["model", "variant"])
    per_model = []
    for model, part in table.groupby("model"):
        ranks = cv.mean_rank(part, "variant").reset_index()
        ranks["model"] = model
        per_model.append(ranks)
    ranks = pd.concat(per_model)
    summary = (
        ranks.groupby("variant")["mean_rank"]
        .agg(["mean", "std"])
        .rename(columns={"mean": "mean_rank_over_models", "std": "sd_over_models"})
    )
    summary["columns"] = [sizes[v] for v in summary.index]
    summary = summary.sort_values(["mean_rank_over_models", "columns"])
    return str(summary.index[0]), summary


def step_feature_sets(cache: dict[str, Any]) -> list[str]:
    """Step 1: compare the three feature sets with every model's default configuration."""
    sets = feature_sets()
    jobs = [
        cv.make_job("feature_sets", m, default_cfg(m), cols, split, 0, variant=name)
        for m in MODELS
        for name, cols in sets.items()
        for split in cv.fold_keys(cache)
    ]
    records = cv.run_jobs(jobs, cache, cv.n_workers())
    chosen, summary = compare_variants(records, {k: len(v) for k, v in sets.items()})
    summary.to_csv(OUT / "step1_feature_sets.csv")
    record_decision("feature_set", {"chosen": chosen, "summary": summary.round(4).to_dict()})
    logger.info("Feature set chosen: %s\n%s", chosen, summary.round(3))
    return sets[chosen]


def er4_variants(columns: list[str]) -> dict[str, list[str]]:
    """Effort regulation with er4 (full scale) and without er4 (er1-er3 index)."""
    with_er4 = [c for c in columns if c != "effort_regulation_index_no_er4"]
    without = [c for c in columns if c not in ("effort_regulation_index", "er4")]
    if "effort_regulation_index_no_er4" not in without:
        without.append("effort_regulation_index_no_er4")
    return {"with_er4": with_er4, "without_er4": without}


def step_er4(cache: dict[str, Any], columns: list[str]) -> list[str]:
    """Step 1b: decide on the effort-regulation score with or without er4 (Phase 1 decision)."""
    variants = er4_variants(columns)
    jobs = [
        cv.make_job("er4", m, default_cfg(m), cols, split, 0, variant=name)
        for m in MODELS
        for name, cols in variants.items()
        for split in cv.fold_keys(cache)
    ]
    records = cv.run_jobs(jobs, cache, cv.n_workers())
    # tie -> with_er4 (the full validated scale): give it the smaller tie-break value
    chosen, summary = compare_variants(records, {"with_er4": 0, "without_er4": 1})
    summary.to_csv(OUT / "step1b_er4.csv")
    record_decision(
        "er4",
        {"chosen": chosen, "summary": summary.round(4).to_dict(), "columns": len(variants[chosen])},
    )
    logger.info("er4 variant chosen: %s\n%s", chosen, summary.round(3))
    return variants[chosen]


def step_search(cache: dict[str, Any], columns: list[str]) -> dict[str, dict[str, Any]]:
    """Step 2: random search (same budget per model), scored by 15-fold CV."""
    mc = load_config("models")
    n, seed = mc["budget"]["random_search_configs"], mc["budget"]["search_seed"]
    configs = {m: cv.search_configs(m, n, seed) for m in MODELS}
    jobs = [
        cv.make_job("search", m, cfg, columns, split, 0, config_id=cid)
        for m in MODELS
        for cid, cfg in configs[m]
        for split in cv.fold_keys(cache)
    ]
    records = cv.run_jobs(jobs, cache, cv.n_workers())
    table = cv.primary_table(records, ["model", "config_id"])
    chosen: dict[str, dict[str, Any]] = {}
    rows = []
    for model, part in table.groupby("model"):
        ranks = cv.mean_rank(part, "config_id")
        best = cv.pick_with_tie_rule(ranks)
        cfg = dict(configs[model])[best]
        chosen[model] = {"config_id": best, "cfg": cfg}
        for cid, r in ranks.iterrows():
            rows.append({"model": model, "config_id": cid, **r.to_dict(), "chosen": cid == best})
    pd.DataFrame(rows).to_csv(OUT / "step2_search_ranks.csv", index=False)
    (OUT / "chosen_configs.json").write_text(json.dumps(chosen, indent=2), "utf-8")
    record_decision("configs", chosen)
    return chosen


def cv_summary(records: list[dict[str, Any]]) -> pd.DataFrame:
    """Mean and SD over folds of the primary metric (and its baseline) per model and task."""
    table = cv.primary_table(records, ["model"])
    g = table.groupby(["model", "task"])
    out = (
        g["value"]
        .agg(cv_mean="mean", cv_sd="std")
        .join(g["baseline"].agg(baseline_mean="mean"))
        .join(g["train_value"].agg(train_mean="mean"))
    )
    return out.reset_index()


def weakness_a(summary: pd.DataFrame, model: str) -> dict[str, Any]:
    """Locked rule (a): CV primary metric must meet the target's minimum against the baseline."""
    targets = load_criteria()["targets"]
    result = {}
    for _, row in summary[summary["model"] == model].iterrows():
        task = row["task"]
        minimum = targets[task]["minimum"]
        if task == "zscore":
            reduction = 1 - row["cv_mean"] / row["baseline_mean"]
            ok = reduction >= minimum["mae_reduction_vs_baseline"]
            result[task] = {"mae_reduction": round(reduction, 4), "meets_minimum": bool(ok)}
        else:
            gain = row["cv_mean"] - row["baseline_mean"]
            ok = gain >= minimum["macro_f1_gain_vs_baseline"]
            result[task] = {"macro_f1_gain": round(gain, 4), "meets_minimum": bool(ok)}
    return result


def step_select(chosen: dict[str, dict[str, Any]]) -> str:
    """Step 3: pick the architecture (mean rank; 1-SD tie -> fewest parameters)."""
    records = [
        r
        for r in cv.read_log()
        if r["step"] == "search" and r["config_id"] == chosen[r["model"]]["config_id"]
    ]
    table = cv.primary_table(records, ["model"])
    ranks = cv.mean_rank(table, "model")
    selected = cv.pick_with_tie_rule(ranks)
    ranks.to_csv(OUT / "step3_architecture_ranks.csv")
    summary = cv_summary(records)
    summary.to_csv(OUT / "cv_summary_tuned.csv", index=False)
    record_decision(
        "architecture",
        {
            "selected": selected,
            "ranks": ranks.round(4).to_dict(),
            "weakness_a": weakness_a(summary, selected),
        },
    )
    logger.info("Architecture selected: %s\n%s", selected, ranks.round(3))
    return selected


def step_stage2(cache: dict[str, Any], columns: list[str]) -> dict[str, Any]:
    """Stage 2 of the locked rule: a single-task network for every weak task.

    For each weak task (reports/phase06/weakness.json) every architecture gets the same
    random search with a single output head (same 20 configurations, 15 folds). The
    configuration and then the architecture are chosen by the same mean-rank and
    one-SD rules. The chosen network is then trained with 5 seeds on the training split
    and scored on validation.
    """
    weak = json.loads((OUT / "weakness.json").read_text("utf-8"))["weak_tasks"]
    mc = load_config("models")
    n, seed = mc["budget"]["random_search_configs"], mc["budget"]["search_seed"]
    result: dict[str, Any] = {}
    for task in weak:
        configs = {m: dict(cv.search_configs(m, n, seed)) for m in MODELS}
        jobs = [
            cv.make_job(
                "stage2_search",
                m,
                cfg,
                columns,
                split,
                0,
                config_id=cid,
                variant=task,
                tasks=[task],
            )
            for m in MODELS
            for cid, cfg in configs[m].items()
            for split in cv.fold_keys(cache)
        ]
        records = cv.run_jobs(jobs, cache, cv.n_workers())
        table = cv.primary_table(records, ["model", "config_id"])
        chosen = {}
        for model, part in table.groupby("model"):
            chosen[model] = cv.pick_with_tie_rule(cv.mean_rank(part, "config_id"))
        best_runs = [r for r in records if r["config_id"] == chosen[r["model"]]]
        ranks = cv.mean_rank(cv.primary_table(best_runs, ["model"]), "model")
        selected = cv.pick_with_tie_rule(ranks)
        ranks.to_csv(OUT / f"stage2_{task}_architecture_ranks.csv")
        summary = cv_summary(best_runs)
        summary.to_csv(OUT / f"stage2_{task}_cv_summary.csv", index=False)
        cfg = configs[selected][chosen[selected]]
        final = []
        for s in mc["budget"]["seeds"]:
            job = cv.make_job(
                "stage2_final",
                selected,
                cfg,
                columns,
                "trainval",
                s,
                config_id=chosen[selected],
                variant=task,
                tasks=[task],
                keep_history=True,
            )
            job["save_tag"] = f"stage2_final__{selected}__{task}__s{s}"
            final.append(job)
        cv.run_jobs(final, cache, cv.n_workers())
        result[task] = {
            "selected": selected,
            "config_id": chosen[selected],
            "cfg": cfg,
            "configs": chosen,
            "ranks": ranks.round(4).to_dict(),
        }
        logger.info("Stage 2 for %s: %s (%s)\n%s", task, selected, chosen[selected], ranks.round(3))
    record_decision("stage2", result)
    return result


def main() -> int:
    """Run the requested steps."""
    parser = argparse.ArgumentParser(description="Phase 6 model training and tuning.")
    parser.add_argument(
        "--step", default="all", choices=["all", "features", "er4", "search", "select", "stage2"]
    )
    args = parser.parse_args()
    require_locked()
    OUT.mkdir(parents=True, exist_ok=True)
    cache = cv.build_fold_cache()
    d = decisions()
    if args.step == "stage2":
        columns = json.loads((OUT / "final_columns.json").read_text("utf-8"))
        step_stage2(cache, columns)
        return 0
    if args.step in ("all", "features"):
        columns = step_feature_sets(cache)
    else:
        columns = feature_sets()[d["feature_set"]["chosen"]]
    if args.step in ("all", "er4"):
        columns = step_er4(cache, columns)
    elif "er4" in d:
        columns = er4_variants(columns)[d["er4"]["chosen"]]
    (OUT / "final_columns.json").write_text(json.dumps(columns, indent=2), "utf-8")
    if args.step in ("all", "search"):
        chosen = step_search(cache, columns)
    else:
        chosen = decisions().get("configs", {})
    if args.step in ("all", "select"):
        step_select(chosen)
    return 0


if __name__ == "__main__":
    sys.exit(main())
