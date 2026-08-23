"""Cross-validation inside the training split, run log and random search (Phase 6).

The feature pipeline is re-fitted on the training part of every fold, so nothing is
learned from the held-out rows. The Z-score band edges stay the frozen training edges
(they define labels, not features). The test split is never read here.
"""

from __future__ import annotations

import json
import math
import os
import time
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd

from src.data.split import load_split_rows
from src.evaluation.metrics import PRIMARY, baseline_predictions, target_metrics
from src.features.build import FeaturePipeline
from src.features.run_phase04 import add_targets
from src.models.data import TASKS, ModelData, dims_for, make_model_data
from src.models.train import fit, predict
from src.utils.config import load_config, resolve_path

N_DISTRICTS = 25
CACHE_FILE = "cv_cache.joblib"


def band_edges() -> list[float]:
    """Frozen Z-score band edges from the training split (Phase 4)."""
    path = resolve_path(load_config("project")["paths"]["processed"]) / "zscore_band_edges.json"
    return json.loads(path.read_text("utf-8"))["edges"]


def build_fold_cache() -> dict[str, Any]:
    """Fit the feature pipeline inside each of the 15 folds and keep the transformed tables."""
    processed = resolve_path(load_config("project")["paths"]["processed"])
    cache_path = processed / CACHE_FILE
    if cache_path.exists():
        return joblib.load(cache_path)
    cfg = load_config("features")
    train = load_split_rows("train")
    folds = pd.read_csv(resolve_path(load_config("split")["cv_files"]["folds"]))
    edges = band_edges()
    cache: dict[str, Any] = {}
    for (repeat, fold), part in folds.groupby(["repeat", "fold"]):
        held_ids = set(part["respondent_id"])
        held = train[train["respondent_id"].isin(held_ids)].reset_index(drop=True)
        fit_rows = train[~train["respondent_id"].isin(held_ids)].reset_index(drop=True)
        pipe = FeaturePipeline(cfg).fit(fit_rows)
        cache[f"r{repeat}f{fold}"] = {
            "train_x": pipe.transform(fit_rows),
            "train_y": add_targets(fit_rows, edges),
            "held_x": pipe.transform(held),
            "held_y": add_targets(held, edges),
        }
    tr = pd.read_csv(processed / "features_train.csv")
    va = pd.read_csv(processed / "features_validation.csv")
    cache["trainval"] = {"train_x": tr, "train_y": tr, "held_x": va, "held_y": va}
    joblib.dump(cache, cache_path)
    return cache


def fold_keys(cache: dict[str, Any]) -> list[str]:
    """The 15 cross-validation fold keys (excludes the train -> validation entry)."""
    return sorted(k for k in cache if k != "trainval")


# ---- run log ---------------------------------------------------------------------------------
def log_path() -> Path:
    """reports/phase06/runs.jsonl - one JSON record per training run."""
    path = resolve_path(load_config("project")["paths"]["reports"]) / "phase06" / "runs.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def run_key(rec: dict[str, Any]) -> str:
    """Identity of a run, used to skip runs already in the log (resume)."""
    return "|".join(
        str(rec[k]) for k in ("step", "model", "config_id", "variant", "split", "seed", "tasks")
    )


def read_log() -> list[dict[str, Any]]:
    """All logged runs."""
    path = log_path()
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text("utf-8").splitlines() if line.strip()]


def append_log(records: list[dict[str, Any]]) -> None:
    """Append run records to the log."""
    with log_path().open("a", encoding="utf-8") as handle:
        for rec in records:
            handle.write(json.dumps(rec, default=float) + "\n")


# ---- one run ---------------------------------------------------------------------------------
def _clean(value: Any) -> Any:
    if isinstance(value, float) and math.isnan(value):
        return None
    return value


def evaluate_run(job: dict[str, Any], entry: dict[str, Any]) -> dict[str, Any]:
    """Train one configuration on one fold and score the held-out rows (worker function)."""
    import torch

    torch.set_num_threads(1)
    mc = load_config("models")
    name = job["build_as"]
    columns = job["columns"]
    crosses = job.get("crosses", mc["wide_crosses"])
    train = make_model_data(entry["train_x"], entry["train_y"], name, columns, crosses)
    held = make_model_data(entry["held_x"], entry["held_y"], name, columns, crosses)
    if job.get("train_fraction", 1.0) < 1.0:
        keep = np.sort(
            np.random.default_rng(job["seed"]).permutation(len(train))[
                : max(20, round(job["train_fraction"] * len(train)))
            ]
        )
        train = train.subset(keep)
    model = fit(
        name,
        job["cfg"],
        train,
        job["tasks_list"],
        job["seed"],
        dims_for(train, N_DISTRICTS),
        mc["training"]["max_epochs"],
        mc["training"]["early_stopping_fraction"],
    )
    held_pred, train_pred = predict(model, held), predict(model, train)
    metrics, train_metrics, baseline = {}, {}, {}
    for task in job["tasks_list"]:
        metrics[task] = {
            k: _clean(v)
            for k, v in target_metrics(task, held.targets[task], held_pred[task]).items()
        }
        train_metrics[task] = {
            k: _clean(v)
            for k, v in target_metrics(task, train.targets[task], train_pred[task]).items()
        }
        kind = "regression" if task == "zscore" else "classification"
        n_classes = None if task == "zscore" else held_pred[task].shape[1]
        base = baseline_predictions(train.targets[task], len(held), kind, n_classes)
        baseline[task] = {
            k: _clean(v) for k, v in target_metrics(task, held.targets[task], base).items()
        }
    record = {
        k: job[k] for k in ("step", "model", "config_id", "variant", "split", "seed", "tasks")
    }
    record.update(
        {
            "cfg": job["cfg"],
            "n_columns": len(columns),
            "metrics": metrics,
            "train_metrics": train_metrics,
            "baseline": baseline,
            "epochs_run": model.epochs_run,
            "best_epoch": model.best_epoch,
            "seconds": round(model.seconds, 2),
            "n_params": model.n_params,
            "finished": time.time(),
        }
    )
    if job.get("keep_history"):
        record["history"] = model.history
        record["ae_history"] = model.ae_history
    if job.get("save_tag"):
        save_model(job["save_tag"], model, held, held_pred, train, train_pred)
    return record


def save_model(
    tag: str,
    model: Any,
    held: ModelData,
    held_pred: dict[str, np.ndarray],
    train: ModelData,
    train_pred: dict[str, np.ndarray],
) -> None:
    """Save a fitted network (models/phase06) and its predictions (data/processed)."""
    import torch

    paths = load_config("project")["paths"]
    model_dir = resolve_path(paths["models"]) / "phase06"
    pred_dir = resolve_path(paths["processed"]) / "phase06_predictions"
    model_dir.mkdir(parents=True, exist_ok=True)
    pred_dir.mkdir(parents=True, exist_ok=True)
    torch.save(model, model_dir / f"{tag}.pt")
    arrays = {f"held_pred_{t}": v for t, v in held_pred.items()}
    arrays |= {f"held_y_{t}": v for t, v in held.targets.items()}
    arrays |= {f"train_pred_{t}": v for t, v in train_pred.items()}
    arrays |= {f"train_y_{t}": v for t, v in train.targets.items()}
    np.savez_compressed(pred_dir / f"{tag}.npz", **arrays)


def run_jobs(
    jobs: list[dict[str, Any]], cache: dict[str, Any], n_jobs: int
) -> list[dict[str, Any]]:
    """Run every job not yet in the log, in parallel, appending results as they finish."""
    from joblib import Parallel, delayed

    done = {run_key(r) for r in read_log()}
    todo = [j for j in jobs if run_key(j) not in done]
    batch = max(n_jobs * 4, 1)
    for start in range(0, len(todo), batch):
        chunk = todo[start : start + batch]
        results = Parallel(n_jobs=n_jobs, backend="loky")(
            delayed(evaluate_run)(job, cache[job["split"]]) for job in chunk
        )
        append_log(results)
    return [r for r in read_log() if run_key(r) in {run_key(j) for j in jobs}]


def make_job(
    step: str,
    model: str,
    cfg: dict[str, Any],
    columns: list[str],
    split: str,
    seed: int,
    config_id: str = "default",
    variant: str = "-",
    tasks: list[str] | None = None,
    build_as: str | None = None,
    **extra: Any,
) -> dict[str, Any]:
    """Describe one training run."""
    tasks = list(tasks or TASKS)
    return {
        "step": step,
        "model": model,
        "config_id": config_id,
        "variant": variant,
        "split": split,
        "seed": seed,
        "tasks": "+".join(tasks),
        "tasks_list": tasks,
        "cfg": cfg,
        "columns": columns,
        "build_as": build_as or model,
        **extra,
    }


# ---- random search ---------------------------------------------------------------------------
def sample_config(space: dict[str, Any], rng: np.random.Generator) -> dict[str, Any]:
    """Draw one configuration from a search space."""
    cfg: dict[str, Any] = {}
    for key, spec in space.items():
        kind, values = next(iter(spec.items()))
        if kind == "choice":
            cfg[key] = values[int(rng.integers(len(values)))]
        elif kind == "int":
            cfg[key] = int(rng.integers(values[0], values[1] + 1))
        elif kind == "uniform":
            cfg[key] = round(float(rng.uniform(*values)), 4)
        elif kind == "loguniform":
            cfg[key] = float(
                f"{math.exp(rng.uniform(math.log(values[0]), math.log(values[1]))):.3g}"
            )
        else:
            raise ValueError(f"Unknown search kind {kind!r}")
    return cfg


def search_configs(model: str, n: int, seed: int) -> list[tuple[str, dict[str, Any]]]:
    """``n`` configurations for a model: the default plus ``n - 1`` random draws (seeded)."""
    spec = load_config("models")["models"][model]
    rng = np.random.default_rng([seed, sum(map(ord, model))])
    configs = [("c00", dict(spec["default"]))]
    fixed = {k: v for k, v in spec["default"].items() if k not in spec["space"]}
    for i in range(1, n):
        configs.append((f"c{i:02d}", fixed | sample_config(spec["space"], rng)))
    return configs


# ---- summaries -------------------------------------------------------------------------------
def primary_table(records: list[dict[str, Any]], group: list[str]) -> pd.DataFrame:
    """One row per run and task: primary metric, oriented score and baseline."""
    rows = []
    for r in records:
        for task in r["tasks"].split("+"):
            name, direction = PRIMARY[task]
            value, base = r["metrics"][task][name], r["baseline"][task][name]
            rows.append(
                {
                    **{g: r[g] for g in group},
                    "split": r["split"],
                    "task": task,
                    "value": value,
                    "baseline": base,
                    "score": -value if direction == "lower" else value,
                    "train_value": r["train_metrics"][task][name],
                    "n_params": r["n_params"],
                }
            )
    return pd.DataFrame(rows)


def mean_rank(table: pd.DataFrame, candidate: str) -> pd.DataFrame:
    """Rank candidates within each (fold, task) by score, then average over folds and tasks.

    Returns one row per candidate with the mean rank, the SD over folds of the per-fold mean
    rank, and the mean number of parameters. Rank 1 is best.
    """
    t = table.copy()
    t["rank"] = t.groupby(["split", "task"])["score"].rank(ascending=False, method="average")
    per_fold = t.groupby([candidate, "split"])["rank"].mean().reset_index()
    out = per_fold.groupby(candidate)["rank"].agg(mean_rank="mean", sd_rank="std")
    out["n_params"] = t.groupby(candidate)["n_params"].mean()
    return out.sort_values("mean_rank")


def pick_with_tie_rule(ranks: pd.DataFrame) -> str:
    """Best mean rank; candidates within one SD of the best are tied -> fewest parameters."""
    best = ranks.iloc[0]
    tied = ranks[
        ranks["mean_rank"]
        <= best["mean_rank"] + (best["sd_rank"] if not np.isnan(best["sd_rank"]) else 0)
    ]
    return str(tied["n_params"].idxmin())


def n_workers() -> int:
    """Parallel workers from configs/models.yaml, capped by the CPU count."""
    return min(load_config("models")["training"]["n_jobs"], os.cpu_count() or 1)


__all__ = [
    "ModelData",
    "build_fold_cache",
    "evaluate_run",
    "fold_keys",
    "make_job",
    "mean_rank",
    "pick_with_tie_rule",
    "primary_table",
    "read_log",
    "run_jobs",
    "search_configs",
]
