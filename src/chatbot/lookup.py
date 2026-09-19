"""Exact answers for questions about one university (Phase 10 addition to system part 4).

When a student names a university, the answer is a lookup in the student's own gap results
(official UGC cut-offs for their district), written by Python. The language model is not used:
in testing it attached the right numbers to the wrong university.
"""

from __future__ import annotations

import re
from typing import Any

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


__all__ = ["mentioned_universities", "university_answer"]
