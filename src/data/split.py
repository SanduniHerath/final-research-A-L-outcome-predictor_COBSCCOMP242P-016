"""Create, lock and load the train / validation / test split.

    python -m src.data.split          # create once (refuses if a split already exists)

The test set stays locked until Phase 7: :func:`load_split_rows` refuses to return
test rows unless it is called with ``unlock_test="PHASE7"``.
"""

from __future__ import annotations

import hashlib
import json
import sys
from typing import Any

import pandas as pd
from sklearn.model_selection import train_test_split

from src.data.load import ID_COLUMN
from src.utils.config import get_seed, load_config, resolve_path
from src.utils.logging_setup import get_logger

logger = get_logger(__name__)

SPLIT_COLUMN = "split"
TEST_UNLOCK_WORD = "PHASE7"


class TestSetLockedError(RuntimeError):
    """Raised when code asks for the test set before Phase 7."""


def stratification_key(data: pd.DataFrame, min_size: int) -> pd.Series:
    """Return degree category x Z-score third, merging small strata within each degree.

    A stratum smaller than ``min_size`` is merged into the largest other third of the
    same degree category, so every stratum can be split three ways.
    """
    third = pd.qcut(data["zscore"], 3, labels=["z1", "z2", "z3"]).astype(str)
    key = data["degree_category"].astype(str) + " | " + third
    sizes = key.value_counts()
    for small in sizes[sizes < min_size].index:
        degree = small.split(" | ")[0]
        siblings = sizes[[k for k in sizes.index if k.startswith(degree + " | ") and k != small]]
        if siblings.empty:
            continue
        key = key.replace(small, siblings.idxmax())
        sizes = key.value_counts()
    return key.rename("stratum")


def make_split(data: pd.DataFrame, cfg: dict[str, Any], seed: int) -> pd.DataFrame:
    """Return ``respondent_id``, ``stratum`` and ``split`` for every modelling row."""
    key = stratification_key(data, cfg["stratify"]["min_stratum_size"])
    p = cfg["proportions"]
    rest_ids, test_ids = train_test_split(
        data[ID_COLUMN], test_size=p["test"], stratify=key, random_state=seed
    )
    rest_key = key.loc[rest_ids.index]
    train_ids, val_ids = train_test_split(
        rest_ids,
        test_size=p["validation"] / (p["train"] + p["validation"]),
        stratify=rest_key,
        random_state=seed,
    )
    split = pd.Series("train", index=data.index, name=SPLIT_COLUMN)
    split.loc[val_ids.index] = "validation"
    split.loc[test_ids.index] = "test"
    return pd.DataFrame({ID_COLUMN: data[ID_COLUMN], "stratum": key, SPLIT_COLUMN: split})


def ids_digest(ids: pd.Series) -> str:
    """SHA-256 of the sorted IDs joined by newlines."""
    return hashlib.sha256("\n".join(sorted(ids)).encode("utf-8")).hexdigest()


def modelling_rows() -> pd.DataFrame:
    """Return the labelled rows that may be used for modelling."""
    path = resolve_path(load_config("project")["paths"]["interim"]) / "survey_labeled.csv"
    data = pd.read_csv(path)
    return data[data["exclude_from_modelling"] == 0].reset_index(drop=True)


def create() -> dict[str, Any]:
    """Create the split once, save it and write the lock record."""
    cfg = load_config("split")
    split_path, lock_path = resolve_path(cfg["files"]["split"]), resolve_path(cfg["files"]["lock"])
    if split_path.exists() or lock_path.exists():
        raise FileExistsError("A split already exists; it is created only once.")
    data = modelling_rows()
    table = make_split(data, cfg, get_seed())
    split_path.parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(split_path, index=False)
    counts = table[SPLIT_COLUMN].value_counts().to_dict()
    record = {
        "seed": get_seed(),
        "rows": len(table),
        "counts": counts,
        "test_ids_sha256": ids_digest(table.loc[table[SPLIT_COLUMN] == "test", ID_COLUMN]),
        "split_file_rows_sha256": ids_digest(table[ID_COLUMN] + ":" + table[SPLIT_COLUMN]),
    }
    lock_path.write_text(json.dumps(record, indent=2), encoding="utf-8")
    return record


def verify_split(table: pd.DataFrame) -> None:
    """Raise ``ValueError`` if the split file differs from its lock record."""
    lock = json.loads(resolve_path(load_config("split")["files"]["lock"]).read_text("utf-8"))
    if ids_digest(table[ID_COLUMN] + ":" + table[SPLIT_COLUMN]) != lock["split_file_rows_sha256"]:
        raise ValueError("Split file does not match configs/split.lock.json")


def load_split_rows(name: str, unlock_test: str | None = None) -> pd.DataFrame:
    """Return the labelled modelling rows of one split ("train", "validation" or "test").

    Raises:
        TestSetLockedError: If ``name == "test"`` without the Phase 7 unlock word.
    """
    if name == "test" and unlock_test != TEST_UNLOCK_WORD:
        raise TestSetLockedError("The test set is locked until Phase 7.")
    table = pd.read_csv(resolve_path(load_config("split")["files"]["split"]))
    verify_split(table)
    ids = table.loc[table[SPLIT_COLUMN] == name, ID_COLUMN]
    data = modelling_rows()
    return data[data[ID_COLUMN].isin(ids)].reset_index(drop=True)


def main() -> int:
    """Create the split."""
    record = create()
    logger.info("Split created and locked: %s", record)
    return 0


if __name__ == "__main__":
    sys.exit(main())
