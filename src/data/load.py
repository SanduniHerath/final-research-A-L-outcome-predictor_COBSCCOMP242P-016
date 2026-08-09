"""Load the raw survey files with short column names.

The raw files are never modified. Two details matter:

* The Google Form offers an answer literally called "None" (e.g. tuition subjects,
  activities, leadership). pandas treats the text "None" as missing by default, so
  only truly empty cells are read as missing here.
* Each column is checked against the expected start of its header text so that a
  re-ordered or different file is caught immediately.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from src.utils.config import load_config, resolve_path
from src.utils.logging_setup import get_logger

logger = get_logger(__name__)

ID_COLUMN = "respondent_id"
_ID_PREFIX = {"survey": "M", "pilot": "P"}


def column_specs() -> list[dict[str, Any]]:
    """Return the column dictionary from ``configs/columns.yaml``, ordered by position."""
    return sorted(load_config("columns")["columns"], key=lambda c: c["position"])


def short_names() -> list[str]:
    """Return the short names of the 53 survey columns in file order."""
    return [c["name"] for c in column_specs()]


def check_headers(headers: list[str], specs: list[dict[str, Any]]) -> None:
    """Raise ``ValueError`` if the raw headers do not match the column dictionary.

    Args:
        headers: Column headers as read from the raw file.
        specs: Column dictionary entries in file order.
    """
    if len(headers) != len(specs):
        raise ValueError(f"Expected {len(specs)} columns, found {len(headers)}")
    mismatched = [
        spec["name"]
        for header, spec in zip(headers, specs, strict=True)
        if not str(header).strip().startswith(spec["header_start"])
    ]
    if mismatched:
        raise ValueError(f"Header text does not match the column dictionary for: {mismatched}")


def load_raw(key: str) -> pd.DataFrame:
    """Read a raw survey file and return it with short column names and a respondent ID.

    Args:
        key: ``"survey"`` (main data) or ``"pilot"``, as named in ``configs/data.yaml``.

    Returns:
        A new DataFrame. The first column is ``respondent_id`` (e.g. ``M0001``), assigned
        from the row order of the raw file; it carries no personal information.
    """
    spec = load_config("data")["raw_files"][key]
    path = resolve_path(spec["path"])
    frame = pd.read_excel(
        path, sheet_name=spec["sheet"] or 0, keep_default_na=False, na_values=[""]
    )
    specs = column_specs()
    check_headers(list(frame.columns), specs)
    frame.columns = [c["name"] for c in specs]
    width = len(str(len(frame)))
    ids = [f"{_ID_PREFIX[key]}{i:0{width}d}" for i in range(1, len(frame) + 1)]
    frame.insert(0, ID_COLUMN, ids)
    logger.info("Loaded %s: %d rows x %d columns from %s", key, *frame.shape, spec["path"])
    return frame
