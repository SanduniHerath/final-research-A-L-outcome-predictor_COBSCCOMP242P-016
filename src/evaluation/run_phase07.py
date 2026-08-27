"""Phase 7: evaluate once on the locked test set.

    python -m src.evaluation.run_phase07              # opens the test set ONCE, then analyses
    python -m src.evaluation.run_phase07 --analyse    # re-analyse the saved test predictions only

The first run is the only code that unlocks the test split. It writes every model's test
predictions to data/processed/phase07_test_predictions.npz and an access record to
reports/phase07/test_access.json; any later attempt to open the test set again refuses.
Nothing here changes a model, a threshold or a rule.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
import torch

from src.data.split import TEST_UNLOCK_WORD, ids_digest, load_split_rows
from src.evaluation.criteria import require_locked
from src.features.run_phase04 import add_targets
from src.models.cv import band_edges
from src.models.data import TASKS, make_model_data
from src.models.train import predict
from src.utils.config import load_config, resolve_path
from src.utils.logging_setup import get_logger

logger = get_logger(__name__)

PATHS = load_config("project")["paths"]
OUT = resolve_path(PATHS["reports"]) / "phase07"
PRED_FILE = resolve_path(PATHS["processed"]) / "phase07_test_predictions.npz"
ACCESS_FILE = OUT / "test_access.json"
DRY_OUT = resolve_path(PATHS["reports"]) / "phase07_dryrun_validation"
DRY_PRED_FILE = resolve_path(PATHS["processed"]) / "phase07_dryrun_validation_predictions.npz"
P6 = resolve_path(PATHS["reports"]) / "phase06"
MODELS_DIR = resolve_path(PATHS["models"]) / "phase06"


class TestAlreadyOpenedError(RuntimeError):
    """Raised when the test set would be opened a second time."""


def phase6_context() -> tuple[list[str], dict[str, Any], list[int]]:
    """Final input columns, Phase 6 decisions and the seeds."""
    columns = json.loads((P6 / "final_columns.json").read_text("utf-8"))
    decisions = json.loads((P6 / "decisions.json").read_text("utf-8"))
    return columns, decisions, load_config("models")["budget"]["seeds"]


def model_files(decisions: dict[str, Any], seeds: list[int]) -> dict[str, str]:
    """``{name: saved model file}`` for every network evaluated on the test set."""
    files = {}
    for model in decisions["configs"]:
        for seed in seeds:
            files[f"{model}__s{seed}"] = f"final__{model}__-__s{seed}.pt"
    for model in sorted({decisions["architecture"]["selected"], "mtl"}):
        for task in TASKS:
            for seed in seeds:
                files[f"single_{model}_{task}__s{seed}"] = (
                    f"single_task__{model}__{task}__s{seed}.pt"
                )
    for task, info in decisions.get("stage2", {}).items():
        for seed in seeds:
            files[f"stage2_{task}_{info['selected']}__s{seed}"] = (
                f"stage2_final__{info['selected']}__{task}__s{seed}.pt"
            )
    return files


def predict_rows(rows: pd.DataFrame, pred_file: Path) -> list[str]:
    """Predict with every saved network for ``rows`` and save predictions and labels."""
    columns, decisions, seeds = phase6_context()
    pipe = joblib.load(resolve_path(PATHS["models"]) / "feature_pipeline.joblib")
    features = pipe.transform(rows)
    targets = add_targets(rows, band_edges())
    crosses = load_config("models")["wide_crosses"]
    arrays: dict[str, np.ndarray] = {}
    data_cache: dict[str, Any] = {}
    files = model_files(decisions, seeds)
    for name, file in files.items():
        model = torch.load(MODELS_DIR / file, weights_only=False)
        if model.name not in data_cache:
            data_cache[model.name] = make_model_data(
                features, targets, model.name, columns, crosses
            )
        for task, value in predict(model, data_cache[model.name]).items():
            arrays[f"pred__{name}__{task}"] = value
    any_data = next(iter(data_cache.values()))
    for task in TASKS:
        arrays[f"y__{task}"] = any_data.targets[task]
    arrays["gender"] = np.array(rows["gender"].astype(str).tolist(), dtype=str)
    arrays["subject_combination"] = np.array(
        rows["al_subject_combination"].astype(str).tolist(), dtype=str
    )
    pred_file.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(pred_file, **arrays)
    return sorted(files)


def open_test_once() -> None:
    """Unlock the test split ONCE, predict with every saved network, record the access."""
    if ACCESS_FILE.exists() or PRED_FILE.exists():
        raise TestAlreadyOpenedError(
            f"The test set was already opened ({ACCESS_FILE}). Use --analyse to re-analyse."
        )
    OUT.mkdir(parents=True, exist_ok=True)
    rows = load_split_rows("test", unlock_test=TEST_UNLOCK_WORD)
    networks = predict_rows(rows, PRED_FILE)
    record = {
        "opened_at_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "test_rows": len(rows),
        "test_ids_sha256": ids_digest(rows["respondent_id"]),
        "networks_evaluated": networks,
        "note": "Test set opened once. No model, threshold or rule was changed afterwards.",
    }
    ACCESS_FILE.write_text(json.dumps(record, indent=2), "utf-8")
    logger.info("Test set opened once: %d rows, %d networks", len(rows), len(networks))


def dry_run_on_validation() -> None:
    """Run the whole Phase 7 analysis on the VALIDATION split (debugging; never reads test)."""
    rows = load_split_rows("validation")
    predict_rows(rows, DRY_PRED_FILE)


def main() -> int:
    """Open the test set once (first run) and analyse the saved predictions."""
    parser = argparse.ArgumentParser(description="Phase 7 test evaluation")
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--analyse", action="store_true", help="only re-analyse saved test predictions"
    )
    group.add_argument("--dry-run", action="store_true", help="debug run on the validation split")
    args = parser.parse_args()
    require_locked()
    from src.evaluation.phase07_analysis import analyse

    if args.dry_run:
        dry_run_on_validation()
        analyse(DRY_PRED_FILE, DRY_OUT, "validation (dry run)")
        return 0
    if not args.analyse:
        open_test_once()
    analyse(PRED_FILE, OUT, "test")
    return 0


if __name__ == "__main__":
    sys.exit(main())
