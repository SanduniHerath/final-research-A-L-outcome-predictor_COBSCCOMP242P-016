"""Clean the main survey file reproducibly (Phase 3).

Every step returns the changed table and log entries describing what changed, so the
cleaning log lists each change with its reason. The raw file is never modified.
Rows are never deleted; doubtful values are flagged for the researcher instead.
"""

from __future__ import annotations

import re
from typing import Any

import numpy as np
import pandas as pd

from src.data.load import ID_COLUMN

LogEntry = dict[str, Any]

AL_SUBJECTS = {
    "al_biology": "Biology",
    "al_chemistry": "Chemistry",
    "al_physics": "Physics",
    "al_combined_maths": "Combined Maths",
    "al_ict": "ICT",
    "al_agri_science": "Agri Science",
}
NOT_TAKEN = "Not Taken"


def _entry(step: str, column: str, ids: pd.Series, detail: str) -> LogEntry:
    """Build one cleaning-log entry."""
    id_list = list(ids)
    return {
        "step": step,
        "column": column,
        "rows_affected": len(id_list),
        "respondent_ids": "; ".join(id_list[:20]) + (" ..." if len(id_list) > 20 else ""),
        "detail": detail,
    }


def strip_whitespace(data: pd.DataFrame) -> tuple[pd.DataFrame, list[LogEntry]]:
    """Remove leading and trailing spaces from every text cell."""
    result, log = data.copy(), []
    for column in result.columns:
        text = result[column]
        is_text = text.map(lambda v: isinstance(v, str))
        if not is_text.any():
            continue
        stripped = text.where(~is_text, text.map(lambda v: v.strip() if isinstance(v, str) else v))
        changed = is_text & (stripped != text)
        if changed.any():
            values = sorted(set(text[changed].astype(str)))
            log.append(
                _entry("strip_whitespace", column, result.loc[changed, ID_COLUMN], f"{values}")
            )
            result[column] = stripped
    return result, log


def apply_corrections(
    data: pd.DataFrame, corrections: list[dict[str, str]]
) -> tuple[pd.DataFrame, list[LogEntry]]:
    """Replace exact wrong values with their corrections, logging each with its reason."""
    result, log = data.copy(), []
    for fix in corrections:
        mask = result[fix["column"]] == fix["from"]
        if mask.any():
            result.loc[mask, fix["column"]] = fix["to"]
            log.append(
                _entry(
                    "value_correction",
                    fix["column"],
                    result.loc[mask, ID_COLUMN],
                    f"'{fix['from']}' -> '{fix['to']}': {fix['reason']}",
                )
            )
    return result, log


def check_allowed_values(data: pd.DataFrame, specs: list[dict[str, Any]]) -> list[LogEntry]:
    """Flag answers that are not among the form's options (single choice, grid, scale)."""
    log = []
    checked = {"multiple_choice", "dropdown", "choice_grid", "linear_scale"}
    for spec in specs:
        if spec["form_type"] not in checked or "options" not in spec:
            continue
        allowed = {str(o) for o in spec["options"]}
        values = data[spec["name"]]
        bad = values.notna() & ~values.astype(str).isin(allowed)
        if bad.any():
            log.append(
                _entry(
                    "flag_unknown_option",
                    spec["name"],
                    data.loc[bad, ID_COLUMN],
                    f"values not in the form: {sorted(set(values[bad].astype(str)))}",
                )
            )
    return log


def slug(text: str) -> str:
    """Turn an option label into a short column-name fragment."""
    text = re.sub(r"\(.*?\)", "", text).lower()
    return re.sub(r"[^a-z0-9]+", "_", text).strip("_")


def split_multiselect(cell: object, options: list[str]) -> tuple[set[str], str]:
    """Return the selected options in a tick-all cell and any text that matches no option.

    Google Forms joins ticked options with ", ", but some options contain commas
    themselves, so options are matched as whole items (longest first) instead of
    splitting on commas.
    """
    if not isinstance(cell, str):
        return set(), ""
    remaining = cell
    chosen: set[str] = set()
    for option in sorted(options, key=len, reverse=True):
        pattern = r"(^|, )" + re.escape(option) + r"(?=, |$)"
        if re.search(pattern, remaining):
            chosen.add(option)
            remaining = re.sub(pattern, "", remaining, count=1)
    leftover = remaining.strip(", ").strip()
    return chosen, leftover


def expand_multiselect(
    data: pd.DataFrame, column: str, options: list[str], prefix: str
) -> tuple[pd.DataFrame, list[LogEntry]]:
    """Add one 0/1 column per option and a ``<column>_skipped`` indicator for blank cells."""
    result, log = data.copy(), []
    recognised = [*options, "None"]  # "None" is a valid answer but needs no column of its own
    parsed = result[column].apply(lambda cell: split_multiselect(cell, recognised))
    skipped = result[column].isna()
    for option in options:
        name = f"{prefix}_{slug(option)}"
        result[name] = parsed.apply(lambda p, o=option: int(o in p[0])).astype("Int64")
        result.loc[skipped, name] = pd.NA
    result[f"{column}_skipped"] = skipped.astype(int)
    leftovers = parsed.apply(lambda p: p[1])
    other = leftovers != ""
    result[f"{prefix}_other_text"] = other.astype(int)
    if other.any():
        log.append(
            _entry(
                "multiselect_other_text",
                column,
                result.loc[other, ID_COLUMN],
                f"{other.sum()} cells contain write-in text; kept as {prefix}_other_text = 1",
            )
        )
    if skipped.any():
        log.append(
            _entry(
                "skipped_question",
                column,
                result.loc[skipped, ID_COLUMN],
                "blank although required in the form; kept as missing with a skipped indicator",
            )
        )
    return result, log


def mark_skipped(data: pd.DataFrame, columns: list[str]) -> tuple[pd.DataFrame, list[LogEntry]]:
    """Add ``<column>_skipped`` indicators for single-answer questions left blank."""
    result, log = data.copy(), []
    for column in columns:
        if f"{column}_skipped" in result.columns:
            continue
        skipped = result[column].isna()
        result[f"{column}_skipped"] = skipped.astype(int)
        if skipped.any():
            log.append(
                _entry(
                    "skipped_question",
                    column,
                    result.loc[skipped, ID_COLUMN],
                    "blank although required in the form; kept as missing with a skipped indicator",
                )
            )
    return result, log


def subject_combination(data: pd.DataFrame) -> tuple[pd.Series, list[LogEntry]]:
    """Return the A/L subjects taken (e.g. "Biology + Chemistry + Physics") per respondent.

    Only whether a subject was taken is used; the grades are outcomes and are not read.
    """
    taken = data[list(AL_SUBJECTS)].ne(NOT_TAKEN)
    combo = taken.apply(
        lambda row: " + ".join(name for col, name in AL_SUBJECTS.items() if row[col]), axis=1
    )
    log = []
    not_three = taken.sum(axis=1) != 3
    if not_three.any():
        log.append(
            _entry(
                "flag_subject_count",
                "al_*",
                data.loc[not_three, ID_COLUMN],
                "number of A/L subjects taken is not 3",
            )
        )
    return combo.rename("al_subject_combination"), log


def check_zscore(
    data: pd.DataFrame, valid_range: list[float], iqr_multiplier: float
) -> tuple[pd.Series, list[LogEntry]]:
    """Convert the Z-score to numbers and flag non-numeric, out-of-range and extreme values."""
    z = pd.to_numeric(data["zscore"], errors="coerce")
    log = []
    bad = z.isna() & data["zscore"].notna()
    if bad.any():
        log.append(_entry("flag_zscore_text", "zscore", data.loc[bad, ID_COLUMN], "not a number"))
    out = z.notna() & ~z.between(*valid_range)
    if out.any():
        log.append(
            _entry(
                "flag_zscore_range", "zscore", data.loc[out, ID_COLUMN], f"outside {valid_range}"
            )
        )
    q1, q3 = z.quantile([0.25, 0.75])
    low, high = q1 - iqr_multiplier * (q3 - q1), q3 + iqr_multiplier * (q3 - q1)
    extreme = z.notna() & ~z.between(low, high)
    log.append(
        _entry(
            "check_zscore_extremes",
            "zscore",
            data.loc[extreme, ID_COLUMN],
            f"{extreme.sum()} values outside [{low:.2f}, {high:.2f}] "
            f"(quartiles -/+ {iqr_multiplier} x IQR); flag only",
        )
    )
    return z.rename("zscore"), log


def flag_rare_combinations(data: pd.DataFrame, share: float) -> list[LogEntry]:
    """Flag degree programmes reached with an A/L subject combination that is very rare for them."""
    table = pd.crosstab(data["degree_program"], data["al_subject_combination"], normalize="index")
    log = []
    for degree, row in table.iterrows():
        for combo, value in row.items():
            if 0 < value < share:
                mask = (data["degree_program"] == degree) & (
                    data["al_subject_combination"] == combo
                )
                log.append(
                    _entry(
                        "flag_rare_combination",
                        "degree_program",
                        data.loc[mask, ID_COLUMN],
                        f"{degree} with {combo} ({value:.1%} of {degree} students); "
                        "researcher to check",
                    )
                )
    return log


def count_duplicates(data: pd.DataFrame) -> list[LogEntry]:
    """Log rows whose answers (all columns except ID and timestamp) duplicate an earlier row."""
    answers = data.drop(columns=[ID_COLUMN, "timestamp"], errors="ignore")
    duplicated = answers.duplicated(keep="first")
    return [
        _entry(
            "check_duplicates",
            "all",
            data.loc[duplicated, ID_COLUMN],
            f"{duplicated.sum()} exact duplicate rows",
        )
    ]


def clean_survey(
    raw: pd.DataFrame, specs: list[dict[str, Any]], cfg: dict[str, Any]
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Run every cleaning step in order and return (clean table, cleaning log)."""
    log: list[LogEntry] = []
    data, entries = strip_whitespace(raw)
    log += entries
    data, entries = apply_corrections(data, cfg["value_corrections"])
    log += entries
    log += check_allowed_values(data, specs)
    log += count_duplicates(data)

    options = {s["name"]: s.get("options", []) for s in specs}
    prefixes = {
        "stream_influences": "stream_influence",
        "school_activities": "school_activity",
        "leadership_roles": "leadership",
    }
    for column, prefix in prefixes.items():
        opts = [o for o in options[column] if o and o != "None"]
        data, entries = expand_multiselect(data, column, opts, prefix)
        log += entries
    data, entries = mark_skipped(data, cfg["skipped_as_missing"])
    log += entries

    combo, entries = subject_combination(data)
    data["al_subject_combination"] = combo
    log += entries
    data["zscore"], entries = check_zscore(data, cfg["zscore_range"], cfg["outlier_iqr_multiplier"])
    log += entries
    log += flag_rare_combinations(data, cfg["rare_combination_share"])
    data, entries = mark_excluded(data, cfg.get("exclude_from_modelling", []))
    log += entries

    data["al_exam_year"] = data["al_exam_year"].astype(str)
    data = data.drop(columns=["timestamp"])
    log.append(
        _entry(
            "drop_column",
            "timestamp",
            pd.Series([], dtype=str),
            "submission time removed for privacy",
        )
    )
    return data, pd.DataFrame(log)


def mark_excluded(
    data: pd.DataFrame, exclusions: list[dict[str, str]]
) -> tuple[pd.DataFrame, list[LogEntry]]:
    """Add ``exclude_from_modelling`` (0/1); listed rows stay in the file, unedited.

    Raises:
        ValueError: If a listed respondent ID does not exist.
    """
    result, log = data.copy(), []
    result["exclude_from_modelling"] = 0
    for item in exclusions:
        mask = result[ID_COLUMN] == item["respondent_id"]
        if not mask.any():
            raise ValueError(f"Unknown respondent_id in exclusions: {item['respondent_id']}")
        result.loc[mask, "exclude_from_modelling"] = 1
        log.append(
            _entry("exclude_from_modelling", "row", result.loc[mask, ID_COLUMN], item["reason"])
        )
    return result, log


def missing_summary(data: pd.DataFrame) -> pd.DataFrame:
    """Return missing-value counts and shares for columns that have any."""
    counts = data.isna().sum()
    counts = counts[counts > 0]
    return pd.DataFrame({"missing": counts, "share": np.round(counts / len(data), 4)})
