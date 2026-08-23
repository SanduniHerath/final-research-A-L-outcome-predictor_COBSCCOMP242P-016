"""Phase 6, part 2: final training on the training split, validation metrics and model checks.

    python -m src.models.run_phase06_final --part train     # train everything needed (resumable)
    python -m src.models.run_phase06_final --part analyse   # tables, checks and figures

Uses the configurations chosen in part 1 (reports/phase06/decisions.json). Every model is
trained on the training split (early stopping on a part of it) and scored on the validation
split. The test split is never read.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

import numpy as np
import pandas as pd

from src.evaluation.criteria import require_locked
from src.models import cv
from src.models.data import TASKS
from src.utils.config import load_config, resolve_path
from src.utils.logging_setup import get_logger

logger = get_logger(__name__)

OUT = resolve_path(load_config("project")["paths"]["reports"]) / "phase06"
SPLIT = "trainval"


def context() -> tuple[dict[str, Any], list[str], str, list[int]]:
    """Chosen configs, final columns, selected architecture and the seeds."""
    d = json.loads((OUT / "decisions.json").read_text("utf-8"))
    columns = json.loads((OUT / "final_columns.json").read_text("utf-8"))
    seeds = load_config("models")["budget"]["seeds"]
    return d["configs"], columns, d["architecture"]["selected"], seeds


def tag(step: str, model: str, variant: str, seed: int) -> str:
    """File name stem for a saved model."""
    return f"{step}__{model}__{variant}__s{seed}".replace("+", "-")


def district_onehots() -> list[str]:
    """The 25 district one-hot column names (from the Phase 4 'full' feature set)."""
    path = (
        resolve_path(load_config("project")["paths"]["reports"]) / "phase04" / "feature_sets.json"
    )
    full = json.loads(path.read_text("utf-8"))["sets"]["full"]
    return [c for c in full if c.startswith("al_district_")]


def final_jobs() -> list[dict[str, Any]]:
    """Every training run of part 2."""
    configs, columns, selected, seeds = context()
    mc = load_config("models")
    jobs: list[dict[str, Any]] = []

    def add(
        step: str,
        model: str,
        cfg: dict[str, Any],
        seed: int,
        variant: str = "-",
        tasks: list[str] | None = None,
        save: bool = True,
        **extra: Any,
    ) -> None:
        job = cv.make_job(
            step,
            model,
            cfg,
            extra.pop("columns_override", columns),
            SPLIT,
            seed,
            config_id=configs.get(model, {}).get("config_id", "-"),
            variant=variant,
            tasks=tasks,
            keep_history=True,
            **extra,
        )
        if save:
            job["save_tag"] = tag(step, model, variant, seed)
        jobs.append(job)

    for model, chosen in configs.items():
        for seed in seeds:
            add("final", model, chosen["cfg"], seed)
        for fraction in mc["budget"]["learning_curve_fractions"]:
            add(
                "learning_curve",
                model,
                chosen["cfg"],
                0,
                variant=f"{fraction:.1f}",
                save=False,
                train_fraction=fraction,
            )
    for model in sorted({selected, "mtl"}):
        for task in TASKS:
            for seed in seeds:
                add("single_task", model, configs[model]["cfg"], seed, variant=task, tasks=[task])

    reg = configs["reg_dnn"]["cfg"]
    for name, change in {
        "no_dropout_no_l2": {"dropout": 0.0, "weight_decay": 0.0},
        "dropout_only": {"weight_decay": 0.0},
        "l2_only": {"dropout": 0.0},
    }.items():
        for seed in seeds:
            add("check_reg_dnn", "reg_dnn", reg | change, seed, variant=name, save=False)

    wd = configs["wide_deep"]["cfg"]
    for name, change, extra in (
        ("wide_only", {"use_deep": False}, {}),
        ("deep_only", {"use_wide": False}, {}),
        ("both_without_crosses", {}, {"crosses": []}),
    ):
        for seed in seeds:
            add(
                "check_wide_deep", "wide_deep", wd | change, seed, variant=name, save=False, **extra
            )

    ent = configs["entity_mlp"]["cfg"]
    for seed in seeds:
        add(
            "check_entity",
            "entity_mlp",
            ent,
            seed,
            variant="one_hot_version",
            build_as="mlp_dropout",
        )
        # The filtered feature set has no district columns, so "one_hot_version" above is the
        # same network WITHOUT district. This run adds the 25 district one-hot columns: the
        # like-for-like comparison with the district embedding (found and added in Phase 6).
        add(
            "check_entity",
            "entity_mlp",
            ent,
            seed,
            variant="one_hot_with_district",
            build_as="mlp_dropout",
            columns_override=columns + district_onehots(),
        )

    ae = configs["ae_mlp"]["cfg"]
    for seed in seeds:
        add(
            "check_ae",
            "ae_mlp",
            ae,
            seed,
            variant="without_autoencoder",
            build_as="mlp_dropout",
            save=False,
        )
    for size in mc["checks"]["ae_bottlenecks"]:
        if size == ae["bottleneck"]:
            continue
        for seed in seeds:
            add("check_ae", "ae_mlp", ae | {"bottleneck": size}, seed, variant=f"bottleneck_{size}")

    res = configs["resnet"]["cfg"]
    same_depth = {
        "layers": 1 + 2 * res["blocks"],
        "units": res["units"],
        "dropout": res["dropout"],
        "weight_decay": res["weight_decay"],
        "lr": res["lr"],
        "batch_size": res["batch_size"],
        "patience": res["patience"],
    }
    for seed in seeds:
        add(
            "check_resnet",
            "resnet",
            same_depth,
            seed,
            variant="reg_dnn_same_depth",
            build_as="reg_dnn",
        )
    return jobs


def train_all() -> None:
    """Run (or resume) every part-2 training job in parallel."""
    cache = cv.build_fold_cache()
    jobs = final_jobs()
    logger.info("Part 2: %d training runs", len(jobs))
    cv.run_jobs(jobs, cache, cv.n_workers())


# ---- analysis helpers ------------------------------------------------------------------------
def records(
    step: str, model: str | None = None, variant: str | None = None
) -> list[dict[str, Any]]:
    """Logged runs of one step (optionally one model / variant)."""
    return [
        r
        for r in cv.read_log()
        if r["step"] == step
        and r["split"] == SPLIT
        and (model is None or r["model"] == model)
        and (variant is None or r["variant"] == variant)
    ]


def scalar_metrics(rec: dict[str, Any], task: str, which: str = "metrics") -> dict[str, float]:
    """The single-number metrics of one task in one run."""
    return {
        k: v for k, v in rec[which][task].items() if isinstance(v, (int, float)) and v is not None
    }


def seed_summary(recs: list[dict[str, Any]]) -> pd.DataFrame:
    """Mean and SD over seeds of every scalar validation metric, per task."""
    rows = []
    for task in recs[0]["tasks"].split("+"):
        frame = pd.DataFrame([scalar_metrics(r, task) for r in recs])
        for metric in frame.columns:
            rows.append(
                {
                    "task": task,
                    "metric": metric,
                    "mean": frame[metric].mean(),
                    "sd": frame[metric].std(),
                    "n_seeds": len(frame),
                }
            )
    return pd.DataFrame(rows)


def load_predictions(step: str, model: str, variant: str, seed: int) -> dict[str, np.ndarray]:
    """Saved validation/train predictions of one run."""
    path = (
        resolve_path(load_config("project")["paths"]["processed"])
        / "phase06_predictions"
        / f"{tag(step, model, variant, seed)}.npz"
    )
    with np.load(path) as data:
        return {k: data[k] for k in data.files}


def load_model(step: str, model: str, variant: str, seed: int) -> Any:
    """Saved fitted network of one run."""
    import torch

    path = (
        resolve_path(load_config("project")["paths"]["models"])
        / "phase06"
        / f"{tag(step, model, variant, seed)}.pt"
    )
    return torch.load(path, weights_only=False)


def main() -> int:
    """Train or analyse."""
    parser = argparse.ArgumentParser(description="Phase 6 part 2")
    parser.add_argument("--part", choices=["train", "analyse", "all"], default="all")
    args = parser.parse_args()
    require_locked()
    if args.part in ("train", "all"):
        train_all()
    if args.part in ("analyse", "all"):
        from src.models.phase06_analysis import analyse

        analyse()
    return 0


if __name__ == "__main__":
    sys.exit(main())
