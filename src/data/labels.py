"""Build the prediction targets from the cleaned survey (Phase 3).

The Z-score band is defined by a rule (tertiles) whose edges are computed on the
training split only, in Phase 5; :func:`band_edges` and :func:`assign_band` implement it.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


def invert_groups(groups: dict[str, list[str]]) -> dict[str, str]:
    """Turn ``{group: [members]}`` into ``{member: group}``, rejecting members listed twice."""
    mapping: dict[str, str] = {}
    for group, members in groups.items():
        for member in members:
            if member in mapping:
                raise ValueError(f"{member!r} is listed in more than one group")
            mapping[member] = group
    return mapping


def map_to_groups(values: pd.Series, groups: dict[str, list[str]]) -> pd.Series:
    """Map each value to its group.

    Raises:
        ValueError: If any value is not listed in any group.
    """
    mapping = invert_groups(groups)
    unknown = sorted(set(values.dropna()) - set(mapping))
    if unknown:
        raise ValueError(f"Values without a group: {unknown}")
    return values.map(mapping)


def band_edges(train_z: pd.Series, n_bands: int) -> list[float]:
    """Return the inner edges that split the training Z-scores into equal-sized bands."""
    quantiles = np.linspace(0, 1, n_bands + 1)[1:-1]
    return [float(q) for q in np.quantile(train_z.dropna(), quantiles)]


def assign_band(z: pd.Series, edges: list[float]) -> pd.Series:
    """Return band numbers 0..n-1. A value equal to an edge goes to the higher band."""
    bands = np.searchsorted(np.asarray(edges), z.to_numpy(), side="right")
    return pd.Series(bands, index=z.index, name="zscore_band").where(z.notna())


def goal_status(target: pd.Series, outcome: pd.Series, not_applicable: list[str]) -> pd.Series:
    """Return "reached", "not reached" or missing (no usable target) for each respondent."""
    status = np.where(target == outcome, "reached", "not reached")
    result = pd.Series(status, index=target.index, name="goal_status", dtype=object)
    return result.where(~target.isin(not_applicable) & target.notna())


def make_labels(clean: pd.DataFrame, cfg: dict[str, Any]) -> pd.DataFrame:
    """Add university_group, degree_category and goal_status to the cleaned table."""
    targets = cfg["targets"]
    result = clean.copy()
    result["university_group"] = map_to_groups(
        result["university"], targets["university_group"]["groups"]
    )
    result["degree_category"] = map_to_groups(
        result["degree_program"], targets["degree_category"]["groups"]
    )
    goal = cfg["goal_status"]
    known = set(goal["target_to_category"]) | set(goal["not_applicable"])
    unknown = sorted(set(result[goal["target_column"]].dropna()) - known)
    if unknown:
        raise ValueError(f"Target options without a category: {unknown}")
    result["target_category"] = result[goal["target_column"]].map(goal["target_to_category"])
    result["goal_status"] = goal_status(
        result["target_category"].fillna(result[goal["target_column"]]),
        result[goal["outcome_column"]],
        goal["not_applicable"],
    )
    result["target_combination_observed"] = combination_observed(
        result["target_category"], result["degree_category"], result["al_subject_combination"]
    )
    return result


def combination_observed(
    target_category: pd.Series, outcome_category: pd.Series, combination: pd.Series
) -> pd.Series:
    """Return 1 if any respondent reached the target category with the same A/L subjects.

    A data-derived consistency check, not an admission rule: 0 means nobody in this
    dataset entered that category with those subjects; missing means there is no target,
    or nobody in the dataset is enrolled in the target category at all (cannot check).
    """
    observed = set(zip(outcome_category, combination, strict=True))
    present = set(outcome_category.dropna())
    flags = [
        pd.NA if pd.isna(t) or t not in present else int((t, c) in observed)
        for t, c in zip(target_category, combination, strict=True)
    ]
    return pd.Series(flags, index=target_category.index, dtype="Int64")


def class_counts(labels: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """Return counts and shares of each class for the given label columns."""
    frames = []
    for column in columns:
        counts = labels[column].value_counts(dropna=False)
        frames.append(
            pd.DataFrame(
                {
                    "target": column,
                    "class": counts.index.astype(str),
                    "count": counts.to_numpy(),
                    "share": np.round(counts.to_numpy() / len(labels), 4),
                }
            )
        )
    return pd.concat(frames, ignore_index=True)


def small_classes(counts: pd.DataFrame, minimum: int) -> pd.DataFrame:
    """Return the classes below the minimum size (candidates for merging)."""
    return counts[counts["count"] < minimum]
