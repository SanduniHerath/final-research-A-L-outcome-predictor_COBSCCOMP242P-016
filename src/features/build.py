"""Turn cleaned survey answers into model features (Phase 4).

Two steps:

1. :func:`encode_raw` - fixed rules, nothing learned: ordinal codes, the reversed
   er4, 0/1 columns and the composites that are plain means or counts.
2. :class:`FeaturePipeline` - everything learned from data (imputation values,
   standardisation, skew transforms, one-hot categories, district index). It is
   fitted on the training split only and then applied unchanged to other splits.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.preprocessing import OneHotEncoder, PowerTransformer, StandardScaler

GRADE_COLUMNS_KEY = "grades"
UNKNOWN_DISTRICT = 0


def _ordinal_map(order: list[str]) -> dict[str, int]:
    """Return ``{label: position}`` for an ordered list of answer labels."""
    return {label: code for code, label in enumerate(order)}


def _code(series: pd.Series, mapping: dict[str, int], name: str) -> pd.Series:
    """Map labels to codes; raise if a non-missing label is not in the mapping."""
    unknown = sorted(set(series.dropna().astype(str)) - set(mapping))
    if unknown:
        raise ValueError(f"{name}: labels without an ordinal code: {unknown}")
    return series.astype("string").map(mapping).astype("Float64").astype(float)


RAW_MULTISELECT = {"stream_influences", "school_activities", "leadership_roles"}
DERIVED_SUFFIXES = ("_skipped", "_count")


def binary_columns(data: pd.DataFrame, prefixes: list[str]) -> list[str]:
    """Return the 0/1 option columns created in Phase 3 for the tick-all questions.

    Excludes the raw text columns (e.g. ``leadership_roles``), the skipped indicators
    and the count composites, which share the same prefixes.
    """
    return [
        c
        for c in data.columns
        if any(c.startswith(p) for p in prefixes)
        and c not in RAW_MULTISELECT
        and not c.endswith(DERIVED_SUFFIXES)
    ]


def encode_raw(data: pd.DataFrame, cfg: dict[str, Any]) -> pd.DataFrame:
    """Apply the fixed encoding rules (nothing is learned from data here).

    Returns:
        Numeric ordinal codes, 1-5 scales (er4 reversed), 0/1 option columns, skipped
        indicators, the nominal columns as text, and the mean/count composites.
    """
    ordinal = cfg["ordinal"]
    out = pd.DataFrame(index=data.index)
    grade_map = _ordinal_map(ordinal[GRADE_COLUMNS_KEY]["order"])
    for column in ordinal[GRADE_COLUMNS_KEY]["columns"]:
        out[column] = _code(data[column], grade_map, column)
    for column, spec in ordinal.items():
        if column in (GRADE_COLUMNS_KEY, "numeric_scales"):
            continue
        out[column] = _code(data[column], _ordinal_map(spec["order"]), column)
    for column in ordinal["numeric_scales"]["columns"]:
        out[column] = pd.to_numeric(data[column]).astype(float)
    for column in cfg["reverse_coded"]:
        out[column] = 6 - out[column]

    for column in binary_columns(data, cfg["binary_prefixes"]):
        out[column] = pd.to_numeric(data[column]).astype(float)
    for column in cfg["skipped_indicators"]:
        out[column] = data[column].astype(float)
    for column in cfg["nominal_onehot"] + cfg["nominal_many"]:
        out[column] = data[column].astype(str)
    return add_fixed_composites(out, cfg)


def add_fixed_composites(encoded: pd.DataFrame, cfg: dict[str, Any]) -> pd.DataFrame:
    """Add the composites that are plain means or counts of already-encoded columns."""
    comp = cfg["composites"]
    out = encoded.copy()
    a_code = len(cfg["ordinal"][GRADE_COLUMNS_KEY]["order"]) - 1
    for name in (
        "ol_core_mean",
        "ol_all_mean",
        "ol_sci_maths_mean",
        "self_efficacy_index",
        "effort_regulation_index",
        "effort_regulation_index_no_er4",
        "interest_index",
    ):
        out[name] = out[comp[name]["columns"]].mean(axis=1)
    out["ol_n_A"] = (out[comp["ol_n_A"]["columns"]] == a_code).sum(axis=1).astype(float)
    out["motivation_index"] = out[["self_efficacy_index", "interest_index"]].mean(axis=1)
    goal_scale = len(cfg["ordinal"]["career_goal_clear"]["order"]) - 1
    out["goal_clarity_index"] = (
        out["career_goal_clear"] / goal_scale + out["stream_influence_career_goals"]
    ) / 2
    for name, prefix in (
        ("activity_count", "school_activity_"),
        ("leadership_count", "leadership_"),
    ):
        options = [c for c in binary_columns(out, [prefix]) if not c.endswith("_other_text")]
        out[name] = out[options].sum(axis=1, min_count=1)
    return out


@dataclass
class FeaturePipeline:
    """Learned part of the feature engineering. Fit on training rows only."""

    cfg: dict[str, Any]
    numeric_: list[str] = field(default_factory=list)
    binary_: list[str] = field(default_factory=list)
    dropped_constant_: list[str] = field(default_factory=list)
    medians_: dict[str, float] = field(default_factory=dict)
    binary_means_: dict[str, float] = field(default_factory=dict)
    standardise_for_composite_: dict[str, tuple[float, float]] = field(default_factory=dict)
    skewed_: list[str] = field(default_factory=list)
    skew_table_: pd.DataFrame | None = None
    power_: PowerTransformer | None = None
    scaler_: StandardScaler | None = None
    onehot_: OneHotEncoder | None = None
    district_index_: dict[str, int] = field(default_factory=dict)
    fitted_rows_: int = 0

    # ---- helpers -------------------------------------------------------------------------
    def _with_standardised_composites(self, encoded: pd.DataFrame) -> pd.DataFrame:
        """Add effort_index and school_performance_index using training means and SDs."""
        out = encoded.copy()

        def z(column: str) -> pd.Series:
            mean, sd = self.standardise_for_composite_[column]
            return (out[column] - mean) / sd

        out["effort_index"] = (z("effort_regulation_index") + z("g11_self_study_hours")) / 2
        out["school_performance_index"] = (z("g6_11_perf_rating") + z("class_rank_freq")) / 2
        return out

    # ---- fit / transform -----------------------------------------------------------------
    def fit(self, train: pd.DataFrame) -> FeaturePipeline:
        """Learn every data-dependent setting from the training rows."""
        cfg = self.cfg
        encoded = encode_raw(train, cfg)
        for column in (
            "effort_regulation_index",
            "g11_self_study_hours",
            "g6_11_perf_rating",
            "class_rank_freq",
        ):
            values = encoded[column]
            self.standardise_for_composite_[column] = (float(values.mean()), float(values.std()))
        encoded = self._with_standardised_composites(encoded)

        nominal = cfg["nominal_onehot"] + cfg["nominal_many"]
        candidates_binary = (
            binary_columns(encoded, cfg["binary_prefixes"]) + cfg["skipped_indicators"]
        )
        candidates_numeric = [c for c in encoded.columns if c not in nominal + candidates_binary]
        self.dropped_constant_ = [
            c
            for c in candidates_numeric + candidates_binary
            if encoded[c].nunique(dropna=True) <= 1
        ]
        self.numeric_ = [c for c in candidates_numeric if c not in self.dropped_constant_]
        self.binary_ = [c for c in candidates_binary if c not in self.dropped_constant_]

        self.medians_ = {c: float(encoded[c].median()) for c in self.numeric_}
        self.binary_means_ = {c: float(encoded[c].mean()) for c in self.binary_}
        numeric = encoded[self.numeric_].fillna(self.medians_)

        skew = numeric.apply(lambda s: stats.skew(s, bias=False))
        threshold = cfg["skew"]["threshold"]
        self.skewed_ = [c for c in self.numeric_ if abs(skew[c]) > threshold]
        self.skew_table_ = pd.DataFrame(
            {"skew_train": skew, "transformed": [c in self.skewed_ for c in skew.index]}
        )
        if self.skewed_:
            self.power_ = PowerTransformer(method="yeo-johnson", standardize=False)
            numeric[self.skewed_] = self.power_.fit_transform(numeric[self.skewed_])
        self.scaler_ = StandardScaler().fit(numeric)

        self.onehot_ = OneHotEncoder(handle_unknown="ignore", sparse_output=False)
        self.onehot_.fit(encoded[nominal])
        districts = sorted(encoded[cfg["nominal_many"][0]].unique())
        self.district_index_ = {d: i + 1 for i, d in enumerate(districts)}  # 0 = unknown
        self.fitted_rows_ = len(train)
        return self

    def transform(self, data: pd.DataFrame) -> pd.DataFrame:
        """Return the model feature table (numeric scaled, 0/1, one-hot, district index)."""
        if self.scaler_ is None or self.onehot_ is None:
            raise RuntimeError("FeaturePipeline must be fitted first")
        cfg = self.cfg
        encoded = self._with_standardised_composites(encode_raw(data, cfg))
        numeric = encoded[self.numeric_].fillna(self.medians_)
        if self.power_ is not None:
            numeric[self.skewed_] = self.power_.transform(numeric[self.skewed_])
        numeric = pd.DataFrame(
            self.scaler_.transform(numeric), columns=self.numeric_, index=data.index
        )
        binary = encoded[self.binary_].fillna(self.binary_means_)
        nominal = cfg["nominal_onehot"] + cfg["nominal_many"]
        onehot = pd.DataFrame(
            self.onehot_.transform(encoded[nominal]),
            columns=self.onehot_.get_feature_names_out(nominal),
            index=data.index,
        )
        district = encoded[cfg["nominal_many"][0]].map(self.district_index_)
        district = district.fillna(UNKNOWN_DISTRICT).astype(int).rename("al_district_index")
        return pd.concat([numeric, binary, onehot, district], axis=1)

    def fit_transform(self, train: pd.DataFrame) -> pd.DataFrame:
        """Fit on the training rows and return their features."""
        return self.fit(train).transform(train)

    @property
    def onehot_names(self) -> list[str]:
        """Names of all one-hot columns."""
        nominal = self.cfg["nominal_onehot"] + self.cfg["nominal_many"]
        return list(self.onehot_.get_feature_names_out(nominal)) if self.onehot_ else []


def scale_items(cfg: dict[str, Any]) -> list[str]:
    """Items that the 'composites' feature set replaces by their indices."""
    comp = cfg["composites"]
    items = set()
    for name in ("self_efficacy_index", "effort_regulation_index", "interest_index"):
        items.update(comp[name]["columns"])
    return sorted(items)


def onehot_groups(names: list[str], nominal: list[str]) -> dict[str, list[str]]:
    """Group one-hot column names by their source column."""
    return {n: [c for c in names if c.startswith(n + "_")] for n in nominal}


def as_array(features: pd.DataFrame, columns: list[str]) -> np.ndarray:
    """Return the chosen feature columns as a float32 array for the networks."""
    return features[columns].to_numpy(dtype=np.float32)
