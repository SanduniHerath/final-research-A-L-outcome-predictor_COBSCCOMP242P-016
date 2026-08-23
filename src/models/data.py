"""Turn feature tables into model inputs and encoded targets (Phase 6)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from src.utils.config import load_config

TASKS = ["zscore", "zscore_band", "university_group", "degree_category"]
DISTRICT_PREFIX = "al_district_"
DISTRICT_INDEX = "al_district_index"


def class_names() -> dict[str, list[str]]:
    """Fixed class order for each classification target (from configs/labels.yaml)."""
    targets = load_config("labels")["targets"]
    return {
        "zscore_band": ["0", "1", "2"],
        "university_group": list(targets["university_group"]["groups"]),
        "degree_category": list(targets["degree_category"]["groups"]),
    }


def encode_targets(table: pd.DataFrame) -> dict[str, np.ndarray]:
    """Return the four targets as arrays (Z-score as float, classes as indices)."""
    names = class_names()
    out = {"zscore": table["zscore"].to_numpy(dtype=np.float32)}
    for task, order in names.items():
        index = {name: i for i, name in enumerate(order)}
        values = table[task].astype(str).map(index)
        if values.isna().any():
            raise ValueError(f"{task}: labels outside {order}")
        out[task] = values.to_numpy(dtype=np.int64)
    return out


def model_columns(model: str, feature_set: list[str]) -> list[str]:
    """Input columns; the entity-embedding MLP uses a district index, not one-hots."""
    if model == "entity_mlp":
        return [c for c in feature_set if not c.startswith(DISTRICT_PREFIX)]
    return list(feature_set)


def cross_features(table: pd.DataFrame, crosses: list[list[str]]) -> pd.DataFrame:
    """Hand-made products for the wide part. ``prefix*`` expands to every matching column."""
    out = {}
    for left, right in crosses:
        lefts = (
            [c for c in table.columns if c.startswith(left[:-1])] if left.endswith("*") else [left]
        )
        if right not in table.columns:
            continue
        for col in lefts:
            if col in table.columns:
                out[f"{col}__x__{right}"] = table[col] * table[right]
    return pd.DataFrame(out, index=table.index)


@dataclass
class ModelData:
    """Inputs and targets for one set of rows."""

    x: np.ndarray
    targets: dict[str, np.ndarray]
    district: np.ndarray | None = None
    wide: np.ndarray | None = None
    columns: list[str] = field(default_factory=list)

    def __len__(self) -> int:  # noqa: D105
        return len(self.x)

    def subset(self, idx: np.ndarray) -> ModelData:
        """Rows ``idx`` of every array."""
        return ModelData(
            x=self.x[idx],
            targets={k: v[idx] for k, v in self.targets.items()},
            district=None if self.district is None else self.district[idx],
            wide=None if self.wide is None else self.wide[idx],
            columns=self.columns,
        )


def make_model_data(
    features: pd.DataFrame,
    targets: pd.DataFrame,
    model: str,
    feature_set: list[str],
    crosses: list[list[str]] | None = None,
) -> ModelData:
    """Build :class:`ModelData` for one model from a feature table and its target table.

    Columns missing from ``features`` (e.g. a district absent from one fold's training rows)
    are added as zeros, so every fold has the same columns.
    """
    cols = model_columns(model, feature_set)
    x = features.reindex(columns=cols, fill_value=0.0).to_numpy(dtype=np.float32)
    district = features[DISTRICT_INDEX].to_numpy(dtype=np.int64) if model == "entity_mlp" else None
    wide = None
    if model == "wide_deep":
        base = features.reindex(columns=cols, fill_value=0.0)
        wide_table = pd.concat([base, cross_features(base, crosses or [])], axis=1)
        wide = wide_table.to_numpy(dtype=np.float32)
    return ModelData(
        x=x, targets=encode_targets(targets), district=district, wide=wide, columns=cols
    )


def dims_for(data: ModelData, n_districts: int) -> dict[str, Any]:
    """Input sizes needed by :func:`src.models.networks.build_network`."""
    return {
        "in_dim": data.x.shape[1],
        "wide_dim": None if data.wide is None else data.wide.shape[1],
        "n_districts": n_districts,
    }
