"""Exact answers for questions about one university (Phase 10 addition to system part 4).

When a student names a university, the answer is a lookup in the student's own gap results
(official UGC cut-offs for their district), written by Python. The language model is not used:
in testing it attached the right numbers to the wrong university.
"""

from __future__ import annotations

import re
from typing import Any

import pandas as pd

# Words that identify a university in a student's question -> text that must appear in the UGC name.
UNIVERSITY_WORDS = {
    r"peradeniya": "Peradeniya", r"moratuwa": "Moratuwa", r"kelaniya": "Kelaniya", r"ruhuna": "Ruhuna",
    r"jayewardenepura|japura|sri\s*j": "Jayewardenepura", r"colombo": "University of Colombo",
    r"jaffna": "University of Jaffna", r"rajarata": "Rajarata", r"sabaragamuwa": "Sabaragamuwa",
    r"wayamba": "Wayamba", r"uva\s*wellassa|\buva\b": "Uva Wellassa", r"south\s*eastern": "South Eastern",
    r"vavuniya": "Vavuniya", r"trincomalee": "Trincomalee", r"(?<!south )eastern": "Eastern University",
}  # fmt: skip
GROUP_WORDS = {
    "within_reach": "within reach: your whole likely range is at or above last year's cut-off",
    "close": "close: last year's cut-off is inside your likely range",
    "further": "further away for now: your whole likely range is below last year's cut-off",
}


def mentioned_universities(message: str) -> list[str]:
    """University name fragments the student mentioned (a district question is not a university one)."""
    text = message.lower()
    if re.search(r"\bdistrict\b", text):
        return []
    return [name for pattern, name in UNIVERSITY_WORDS.items() if re.search(pattern, text)]


def university_answer(message: str, results: dict[str, Any]) -> str | None:
    """A fixed, exact answer if the question names universities in the student's target list."""
    gap = results.get("gap") or {}
    groups = gap.get("universities")
    names = mentioned_universities(message)
    if not groups or not names:
        return None
    z = results["prediction"]["zscore"]["predicted"]
    lines = []
    for name in names:
        for key, rows in groups.items():
            for u in rows:
                if name.lower() not in u["university"].lower():
                    continue
                if u["cutoff"] is None:
                    lines.append(
                        f"{u['course']} at {u['university']}: no cut-off was published for {gap['district']} "
                        f"district in {gap['cutoff_year']} (NQC)."
                    )
                    continue
                diff = u["gap_from_best_guess"]
                where = f"{abs(diff):.2f} below" if diff > 0 else f"{abs(diff):.2f} above"
                lines.append(
                    f"{u['course']} at {u['university']}: the {gap['cutoff_year']} cut-off for {gap['district']} "
                    f"district was {u['cutoff']:.4f}. Your predicted Z-score ({z:.2f}) is {where} it, so it is "
                    f"{GROUP_WORDS[key]}."
                )
    if not lines:
        return None
    return " ".join(lines) + (
        " This is a guide from last year's cut-offs, not a promise: cut-offs change every year, and the "
        "UGC also uses the order in which you list universities."
    )


# Words for a course in a question -> course names as printed in the UGC documents.
COURSE_WORDS = {
    r"medicine|\bmbbs\b|\bdoctor": ["MEDICINE"],
    r"dental|dentist": ["DENTAL SURGERY"],
    r"veterinar|\bvet\b": ["VETERINARY SCIENCE"],
    r"engineer": ["ENGINEERING", "ENGINEERING (EM)", "ENGINEERING (TM)"],
    r"nursing|\bnurse": ["NURSING"],
    r"pharmac": ["PHARMACY"],
    r"physiotherap": ["PHYSIOTHERAPY"],
    r"\bmls\b|medical lab": ["MEDICAL LABORATORY SCIENCES"],
    r"radiograph": ["RADIOGRAPHY"],
    r"agricultur": ["AGRICULTURE", "AGRICULTURAL TECHNOLOGY & MANAGEMENT", "EXPORT AGRICULTURE"],
    r"food science": ["FOOD SCIENCE & NUTRITION", "FOOD SCIENCE & TECHNOLOGY"],
    r"bio(logical)?\s*science": ["BIOLOGICAL SCIENCE", "APPLIED SCIENCES (BIO.SC)"],
    r"physical\s*science": ["PHYSICAL SCIENCE", "APPLIED SCIENCES (PHY.SC)"],
    r"computer\s*science|computing": ["COMPUTER SCIENCE"],
    r"artificial intelligence|\bai\b": ["ARTIFICIAL INTELLIGENCE"],
    r"data\s*science": ["DATA SCIENCE"],
}  # fmt: skip
GUIDE = (
    " Cut-offs change every year and the UGC also uses the order in which you list universities, "
    "so this is a guide, not a promise."
)


def _nice(course: str) -> str:
    return course.title().replace("(Em)", "(EM)").replace("(Tm)", "(TM)")


def district_in(message: str, cutoffs: pd.DataFrame) -> str | None:
    """The district a message names ("Kandy district", or "Kandy" unless it is also a university's name)."""
    text = message.lower()
    districts = sorted(cutoffs["district"].dropna().unique(), key=len, reverse=True)
    asked = next((d for d in districts if re.search(rf"\b{d.lower()}\s+district\b", text)), None)
    if asked is None:
        asked = next((d for d in districts if re.search(rf"\b{d.lower()}\b", text)
                      and d.lower() not in ("colombo", "jaffna", "trincomalee")), None)  # fmt: skip
    return asked


def cutoff_answer(message: str, cutoffs: pd.DataFrame, home_district: str | None = None) -> str | None:
    """An exact answer from the official UGC table when a question names a course and a university.

    The district comes from the question ("... Kandy district"), else from the student's profile,
    else every district is summarised as a range. Written by Python, never by the language model.
    """
    text = message.lower()
    courses = [c for pattern, names in COURSE_WORDS.items() if re.search(pattern, text) for c in names]
    if not courses:
        return None
    asked = district_in(message, cutoffs)
    unis = [name for pattern, name in UNIVERSITY_WORDS.items()
            if re.search(rf"(?:{pattern})(?!\s+district)", text)]  # fmt: skip
    if not unis:
        return None
    year = sorted(cutoffs["academic_year"].unique())[-1]
    latest = cutoffs[(cutoffs["academic_year"] == year) & cutoffs["course_name"].isin(courses)]
    district = asked or home_district
    lines = []
    for name in unis:
        rows = latest[latest["university"].str.contains(name, case=False, regex=False)]
        for (course, university), group in rows.groupby(["course_name", "university"]):
            if district:
                row = group[group["district"] == district]
                if row.empty:
                    continue
                value = row["min_z"].iloc[0]
                lines.append(
                    f"{_nice(course)} at {university}: no cut-off was published for {district} district in "
                    f"{year} (NQC)." if value != value else  # NaN check
                    f"{_nice(course)} at {university}: the {year} cut-off for {district} district was {value:.4f}."
                )
            else:
                known = group.dropna(subset=["min_z"]).sort_values("min_z")
                if known.empty:
                    continue
                low, high = known.iloc[0], known.iloc[-1]
                lines.append(
                    f"{_nice(course)} at {university}: in the {year} UGC cut-offs the minimum Z-score depended "
                    f"on the district, from {low['min_z']:.4f} ({low['district']} district) to "
                    f"{high['min_z']:.4f} ({high['district']} district)."
                )
            if len(lines) >= 3:
                break
    if not lines:
        return None
    tail = "" if district else (
        " The cut-off that applies to you depends on the district where you sit the A/L. Tell me your "
        "district, or fill in My Profile so I can compare it with your own predicted Z-score."
    )
    return " ".join(lines) + tail + GUIDE


__all__ = ["COURSE_WORDS", "cutoff_answer", "district_in", "mentioned_universities", "university_answer"]
