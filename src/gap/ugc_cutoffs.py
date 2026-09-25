"""Extract the official UGC minimum Z-score tables (course x district) from the researcher's PDFs.

Source documents (University Grants Commission, "Minimum Z scores for selection to various
courses of study ... in respect of each district"), stored read-only in ``data/raw/ugc``.

Each table page has one row per district and one column per course. Course headings are printed
rotated 90 degrees, so they are rebuilt from the individual characters: characters are grouped
into text lines by their x position, each line is read bottom-to-top, and each line is assigned to
the value column it sits above. "NQC" (no qualified candidate selected from that district) is kept
as missing. Nothing is typed in by hand; the output keeps the page number for checking.

Run: ``python -m src.gap.ugc_cutoffs``  ->  ``data/processed/ugc_cutoffs.csv``
"""

from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

import pandas as pd
import pdfplumber

from src.utils.config import load_config, resolve_path
from src.utils.logging_setup import get_logger

LOG = get_logger(__name__)

VALUE = re.compile(r"^(-?\d\.\d{4}|NQC)$")
UNICODE = re.compile(r"^\d{3}[A-Z]$")
YEAR = re.compile(r"ACADEMIC\s+YEAR\s+(\d{4}/\d{4})")
DISTRICTS = [
    "COLOMBO", "GAMPAHA", "KALUTARA", "MATALE", "KANDY", "NUWARA ELIYA", "GALLE", "MATARA",
    "HAMBANTOTA", "JAFFNA", "KILINOCHCHI", "MANNAR", "MULLAITIVU", "VAVUNIYA", "TRINCOMALEE",
    "BATTICALOA", "AMPARA", "PUTTALAM", "KURUNEGALA", "ANURADHAPURA", "POLONNARUWA", "BADULLA",
    "MONARAGALA", "KEGALLE", "RATNAPURA",
]  # fmt: skip
ROTATED = (0.0, 1.0, -1.0, 0.0)


def _is_rotated(char: dict) -> bool:
    """True for characters printed bottom-to-top (the course headings)."""
    a, b, c, d = char["matrix"][:4]
    scale = (a * a + b * b) ** 0.5 or 1.0
    return all(abs(m / scale - r) < 0.05 for m, r in zip((a, b, c, d), ROTATED, strict=True))


def _clean(text: str) -> str:
    """Collapse whitespace and tidy spacing around brackets."""
    text = re.sub(r"\s+", " ", text).strip()
    return re.sub(r"\(\s+", "(", re.sub(r"\s+\)", ")", text))


def _district_rows(words: list[dict]) -> list[tuple[str, float]]:
    """District names on the page with the vertical centre of their row."""
    rows: dict[int, list[dict]] = defaultdict(list)
    for w in words:
        rows[round(w["top"])].append(w)
    found = []
    for top, ws in sorted(rows.items()):
        label = " ".join(
            w["text"] for w in sorted(ws, key=lambda w: w["x0"]) if w["text"].isalpha()
        )
        for district in DISTRICTS:
            if label.startswith(district) and all(d != district for d, _ in found):
                found.append((district, top))
                break
    return found


def parse_page(page: pdfplumber.page.Page) -> pd.DataFrame:
    """Return the long table (course heading, unicode, district, value) for one table page."""
    page = page.dedupe_chars()
    words = page.extract_words()
    districts = _district_rows(words)
    if len(districts) < 20:
        return pd.DataFrame()
    first_top = min(t for _, t in districts)

    # Value columns: x positions of the values in the district rows.
    cells: dict[str, list[dict]] = {}
    for district, top in districts:
        cells[district] = sorted(
            (w for w in words if abs(w["top"] - top) < 3 and VALUE.match(w["text"])),
            key=lambda w: w["x0"],
        )
    n_cols = max(len(v) for v in cells.values())
    reference = max(cells.values(), key=len)
    centres = [(w["x0"] + w["x1"]) / 2 for w in reference]

    def column_of(x: float) -> int:
        return min(range(n_cols), key=lambda i: abs(centres[i] - x))

    # Course headings: rotated characters above the first district row.
    lines: dict[int, list[dict]] = defaultdict(list)
    for c in page.chars:
        if _is_rotated(c) and c["bottom"] <= first_top:
            lines[round(c["x0"] * 2)].append(c)
    headings: dict[int, list[str]] = defaultdict(list)
    for key in sorted(lines):
        chars = sorted(lines[key], key=lambda c: -c["top"])
        x_mid = (chars[0]["x0"] + chars[0]["x1"]) / 2
        col = column_of(x_mid)
        if abs(centres[col] - x_mid) < 20:
            headings[col].append("".join(c["text"] for c in chars))

    codes = sorted(
        (w for w in words if UNICODE.match(w["text"]) and w["bottom"] <= first_top),
        key=lambda w: w["x0"],
    )
    code_of = {column_of((w["x0"] + w["x1"]) / 2): w["text"] for w in codes}

    rows = []
    for district, values in cells.items():
        for w in values:
            col = column_of((w["x0"] + w["x1"]) / 2)
            rows.append(
                {
                    "column": col,
                    "heading": _clean(" ".join(headings.get(col, []))),
                    "unicode": code_of.get(col, ""),
                    "district": district.title(),
                    "min_z": None if w["text"] == "NQC" else float(w["text"]),
                }
            )
    return pd.DataFrame(rows)


def split_heading(heading: str) -> tuple[str, str]:
    """Split 'MEDICINE (University of Colombo)' into course and university."""
    match = re.match(r"^(.*)\(([^()]*(?:University|Campus|Institute)[^()]*)\)\s*$", heading)
    if not match:
        return heading, ""
    return match.group(1).strip(), match.group(2).strip()


def extract_pdf(path: Path) -> pd.DataFrame:
    """All table pages of one PDF."""
    frames = []
    with pdfplumber.open(path) as pdf:
        year = None
        for number, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            found = YEAR.search(text)
            year = found.group(1) if found else year
            table = parse_page(page)
            if table.empty:
                continue
            table["page"] = number
            table["academic_year"] = year
            frames.append(table)
    out = pd.concat(frames, ignore_index=True)
    out[["course", "university"]] = out["heading"].apply(lambda h: pd.Series(split_heading(h)))
    out["source_file"] = path.name
    return out


def extract_all() -> pd.DataFrame:
    """Extract every UGC PDF listed in configs/data.yaml."""
    frames = [extract_pdf(resolve_path(p)) for p in load_config("data")["raw_files"]["ugc_cutoffs"]]
    cols = ["academic_year", "course", "university", "unicode", "district", "min_z", "page",
            "column", "heading", "source_file"]  # fmt: skip
    return pd.concat(frames, ignore_index=True)[cols]


def main() -> int:
    """Write data/processed/ugc_cutoffs.csv and a per-file summary to the log."""
    table = extract_all()
    out = resolve_path(load_config("project")["paths"]["processed"]) / "ugc_cutoffs.csv"
    table.to_csv(out, index=False)
    for (year, src), part in table.groupby(["academic_year", "source_file"]):
        courses = part.groupby(["page", "column"]).ngroups
        LOG.info("%s (%s): %d course columns, %d cells", year, src, courses, len(part))
    LOG.info("Wrote %s (%d rows)", out, len(table))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
