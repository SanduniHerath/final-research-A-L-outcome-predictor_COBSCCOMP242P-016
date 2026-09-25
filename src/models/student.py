"""One student's answers -> the 34 model inputs (used by the Phase 9 app).

The app asks only the questions the final model needs (Phase 6 filtered set), plus the A/L
district and the target degree for the gap analysis. The answers are turned into a one-row table
shaped like the cleaned survey and passed through the SAME training-fitted feature pipeline, so a
student in the app is encoded exactly like a respondent in the data (checked by a unit test).

Questions the final model does not use (e.g. Grade 5 result, tuition, activities, leadership) are
left blank; the pipeline fills them with training values, and they do not reach the 34 inputs.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from src.data.clean import slug
from src.utils.config import load_config

GRADES = ["A", "B", "C", "S", "W"]
SCALE_ITEMS = ["se1", "se2", "se3", "se4", "er1", "er2", "er3", "er4",
               "int1", "int2", "int3", "int4"]  # fmt: skip
GRADE_FIELDS = ["ol_religion", "ol_first_language", "ol_english", "ol_maths", "ol_history",
                "ol_science", "ol_cat1", "ol_cat2", "ol_cat3"]  # fmt: skip
SUBJECT_COMBINATIONS = [
    "Biology + Chemistry + Physics",
    "Biology + Chemistry + Agri Science",
    "Chemistry + Physics + Combined Maths",
    "Physics + Combined Maths + ICT",
]
STREAM_INFLUENCE_OPTIONS = ["Personal Interest", "Parents", "Teachers", "Friends", "Career Goals"]

# Fields the app asks for (all required). The order is the order of the form.
MODEL_FIELDS = (
    ["ol_school_type", "g6_11_perf_rating", "class_rank_freq"]
    + GRADE_FIELDS
    + ["g11_self_study_hours"]
    + SCALE_ITEMS
    + ["career_goal_clear", "stream_influences", "al_subject_combination"]
)
GAP_FIELDS = ["al_district", "al_target_degree"]


def _form_columns() -> dict[str, dict[str, Any]]:
    return {c["name"]: c for c in load_config("columns")["columns"]}


def questions() -> list[dict[str, Any]]:
    """Question text and allowed answers for every app field (from the live form wording)."""
    form = _form_columns()
    out = []
    for name in MODEL_FIELDS + GAP_FIELDS:
        if name == "al_subject_combination":
            out.append(
                {
                    "name": name,
                    "label": "Which A/L subjects have you chosen (or plan to choose)?",
                    "type": "single",
                    "options": SUBJECT_COMBINATIONS,
                }
            )
            continue
        col = form[name]
        kind = "multi" if col["form_type"] == "checkboxes" else "single"
        options = [str(o) for o in col.get("options", [])]
        if name == "al_target_degree":
            label = "Which degree are you aiming for?"
        elif name == "al_district":
            label = "In which district will you sit the A/L examination?"
        else:
            label = col["label"]
        out.append({"name": name, "label": label, "type": kind, "options": options})
    return out


def validate(profile: dict[str, Any], require_gap_fields: bool = False) -> None:
    """Raise ``ValueError`` listing every missing or invalid answer."""
    allowed = {q["name"]: q for q in questions()}
    needed = MODEL_FIELDS + (GAP_FIELDS if require_gap_fields else [])
    problems = []
    for name in needed:
        value = profile.get(name)
        options = allowed[name]["options"]
        if value is None or value == "":
            problems.append(f"{name}: missing")
        elif allowed[name]["type"] == "multi":
            values = value if isinstance(value, list) else [value]
            bad = [v for v in values if v not in options]
            if bad:
                problems.append(f"{name}: not allowed {bad}")
        elif str(value) not in options:
            problems.append(f"{name}: '{value}' not in {options}")
    if problems:
        raise ValueError("; ".join(problems))


def to_survey_row(profile: dict[str, Any], pipeline: Any) -> pd.DataFrame:
    """One-row table shaped like the cleaned survey (Phase 3), ready for ``pipeline.transform``."""
    cfg = pipeline.cfg
    row: dict[str, Any] = {}
    for name in MODEL_FIELDS:
        if name != "stream_influences":
            row[name] = profile[name]
    for name in ("g6_11_perf_rating", *SCALE_ITEMS):
        row[name] = int(profile[name])
    row["al_district"] = profile.get("al_district", np.nan)

    # Questions the final model does not use: blank -> training value inside the pipeline.
    for name in cfg["ordinal"]:
        if name not in ("grades", "numeric_scales") and name not in row:
            row[name] = np.nan
    for name in cfg["ordinal"]["numeric_scales"]["columns"]:
        row.setdefault(name, np.nan)
    for name in cfg["nominal_onehot"]:
        row.setdefault(name, np.nan)
    for name in pipeline.binary_ + cfg["skipped_indicators"]:
        row.setdefault(name, np.nan)

    chosen = profile["stream_influences"]
    chosen = chosen if isinstance(chosen, list) else [chosen]
    for option in STREAM_INFLUENCE_OPTIONS:
        row[f"stream_influence_{slug(option)}"] = float(option in chosen)
    row["stream_influences_skipped"] = 0.0
    return pd.DataFrame([row])


def to_features(profile: dict[str, Any], pipeline: Any, columns: list[str]) -> np.ndarray:
    """The 34 standardised model inputs for one student, shape (1, 34)."""
    validate(profile)
    table = pipeline.transform(to_survey_row(profile, pipeline))
    return table[columns].to_numpy(dtype=np.float32)


def profile_from_survey(row: pd.Series) -> dict[str, Any]:
    """Rebuild app answers from a cleaned survey row (used to test the encoding)."""
    profile = {name: row[name] for name in MODEL_FIELDS if name != "stream_influences"}
    profile["stream_influences"] = [
        o for o in STREAM_INFLUENCE_OPTIONS if row.get(f"stream_influence_{slug(o)}", 0) == 1
    ]
    for name in GAP_FIELDS:
        profile[name] = row[name]
    for name in ("g6_11_perf_rating", *SCALE_ITEMS):
        profile[name] = int(profile[name])
    return profile


__all__ = [
    "GRADES",
    "MODEL_FIELDS",
    "SUBJECT_COMBINATIONS",
    "profile_from_survey",
    "questions",
    "to_features",
    "to_survey_row",
    "validate",
]
