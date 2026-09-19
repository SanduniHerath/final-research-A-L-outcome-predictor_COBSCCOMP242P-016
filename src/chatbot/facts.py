"""The chatbot's fact sheet: the ONLY knowledge it may use (system part 4).

Built from the student's own results in the app (prediction, gap, explanation, study plan) and a
few fixed facts about the project. Probabilities are written as whole percentages so that any
number the chatbot says can be checked against this sheet.
"""

from __future__ import annotations

import json
from typing import Any

from src.utils.config import load_config, resolve_path


def pct(p: float) -> str:
    """0.6234 -> '62%'."""
    return f"{round(p * 100)}%"


def project_facts() -> list[str]:
    """Fixed facts about the data and the model (from the Phase 7 test results)."""
    reports = resolve_path(load_config("project")["paths"]["reports"])
    phase08 = json.loads((reports / "phase08" / "summary.json").read_text("utf-8"))
    within = phase08["zscore_residuals_test"]["share_within_0_4"]
    rows = json.loads((reports / "phase07" / "summary.json").read_text("utf-8"))["rows"]
    years = ", ".join(sorted(load_config("app")["gap"]["cutoff_exam_years"].values()))
    return [
        "The app learned from a survey of university students who did A/L in the Science stream.",
        "Everyone in the survey entered a state university, so the app knows less about lower results.",
        f"When tested on {rows} students it had not seen, the predicted Z-score was within 0.4 of "
        f"the real Z-score for {pct(within)} of them.",
        f"Cut-offs come only from the UGC minimum Z-score documents for {years}.",
        "The predictions are estimates from patterns in the survey, not promises.",
    ]


GLOSSARY = [
    "Z-score: the standard score used by the UGC to rank A/L students for university entry.",
    "Cut-off: the lowest Z-score that got a student into a course from a district in a given year.",
    "NQC: the UGC table shows NQC when no qualified student was selected from that district.",
    "Band: the app splits Z-scores of students in the survey into three equal groups: Band 1, Band 2, Band 3.",
]


def _gap_words(gap: float) -> str:
    """Per-university gap, worked out here so the chatbot never has to subtract."""
    if gap > 0:
        return f"the predicted Z-score is {gap:.2f} below this cut-off"
    return f"the predicted Z-score is {abs(gap):.2f} above this cut-off"


def build_fact_sheet(results: dict[str, Any], max_courses: int = 6) -> str:
    """Plain-text facts from the app results of one student."""
    pred, gap = results["prediction"], results.get("gap")
    expl, plan = results.get("explanation"), results.get("recommendations")
    z = pred["zscore"]
    band, degree, uni = pred["zscore_band"], pred["degree_category"], pred["university_group"]
    lines = ["STUDENT RESULTS"]
    lines.append(
        f"- Predicted A/L Z-score: about {z['predicted']:.2f}. Likely range: {z['range_low']:.2f} to "
        f"{z['range_high']:.2f} (8 out of 10 similar students fell in a range like this)."
    )
    if z.get("warning"):
        lines.append(f"- Warning: {z['warning']}")
    edges = band["band_edges"]
    lines.append(
        f"- Z-score band: most likely {band['most_likely']} (the chance that the Z-score falls in "
        f"{band['most_likely']} is {pct(band['top_probability'])}). "
        f"Band 1 is below {edges[0]:.2f}, Band 2 is {edges[0]:.2f} to {edges[1]:.2f}, Band 3 is above "
        f"{edges[1]:.2f}. {band['confidence_message']}"
    )
    top_deg = list(degree["probabilities"].items())[:3]
    lines.append(
        "- Degree area the student is most likely to enter, with the model's chance for each: "
        + ", ".join(f"{k}: {pct(v)} chance" for k, v in top_deg)
        + f". {degree['confidence_message']}"
    )
    lines.append(
        f"- University region (very rough guide only): {' or '.join(uni['top_k'])}. {uni['confidence_message']}"
    )

    if gap:
        lines.append("TARGET AND GAP")
        lines.append(
            f"- Target: {gap['target_option']}. The student's district: {gap['district']}. Every "
            f"cut-off below is for students from {gap['district']} district only; cut-offs for "
            "other districts are NOT known here."
        )
        if gap.get("message"):
            lines.append(f"- {gap['message']}")
        if gap.get("status") == "gap":
            lines.append(f"- Gap: {gap['gap_points']:.2f} Z-score points below the lowest cut-off.")
        unis = gap.get("universities")
        if not unis:  # older results without university groups
            for c in gap.get("courses", [])[:max_courses]:
                cut = "NQC (no cut-off)" if c["cutoff"] is None else f"{c['cutoff']:.4f}"
                lines.append(
                    f"- {c['course']} at {c['university']}: cut-off {cut}. {c['status_text']}"
                )
        if unis:
            words = {"within_reach": "within reach (whole likely range at or above the cut-off)",
                     "close": "close (the cut-off is inside the likely range)",
                     "further": "further away (whole likely range below the cut-off)"}  # fmt: skip
            lines.append(
                f"- Universities for {gap['target_category']} for students from {gap['district']} district "
                f"(cut-offs for {gap['district']} district only), from the {gap['cutoff_year']} "
                "UGC cut-offs. This is a guide, not a prediction: the UGC also uses the order in which "
                "the student lists universities, and cut-offs change every year."
            )
            for key, text in words.items():
                names = [
                    f"{u['university']} ({u['course']}, cut-off {u['cutoff']:.4f})"
                    for u in unis[key]
                ]
                lines.append(f"  - {text}: " + ("; ".join(names) if names else "none"))
        entrants = gap.get("entrants") or {}
        if "median_z" in entrants:
            lines.append(
                f"- Students in the survey who entered {gap['target_category']}: the middle half had "
                f"Z-scores from {entrants['q1']:.2f} to {entrants['q3']:.2f}."
            )
        if gap.get("subject_check", {}).get("warning"):
            lines.append(f"- {gap['subject_check']['warning']}")
        for o in gap.get("other_options", []):
            names = list(dict.fromkeys(u["university"] for u in o.get("universities_reached", [])))
            if names and o["category"] != gap.get("target_category"):
                lines.append(
                    f"- Backup area {o['category']}: the predicted Z-score reaches last year's cut-off at "
                    + ", ".join(names[:6])
                    + "."
                )
        others = [o["category"] for o in gap.get("other_options", [])]
        if others:
            lines.append(
                "- Degree areas the predicted Z-score reaches in this district: "
                + ", ".join(others)
                + "."
            )
        lines.extend(f"- {n}" for n in gap.get("notes", []))

    if expl:
        lines.append("WHY THIS RESULT (how the model used the answers; patterns, not causes)")
        lines.extend(f"- {s}" for s in expl["sentences"])

    if plan:
        lines.append(f"STUDY PLAN (steps in order of importance). {plan['mode_text']}")
        if plan["weekly_plan"].get("self_study_advice"):
            lines.append(f"- {plan['weekly_plan']['self_study_advice']}")
        for r in plan["recommendations"]:
            lines.append(f"- Step {r['priority']}. {r['title']}: {r['text']} (Why: {r['reason']})")
        w = plan["what_if"]
        lines.append(
            f"- What-if (model estimate, not a promise): one step better study habits changed the predicted "
            f"Z-score by {w['habits']:+.2f}; all changeable answers one step better: {w['all']:+.2f}."
        )

    lines.append("ABOUT THE APP")
    lines.extend(f"- {f}" for f in project_facts())
    lines.append("WORDS")
    lines.extend(f"- {g}" for g in GLOSSARY)
    return "\n".join(lines)


__all__ = ["GLOSSARY", "build_fact_sheet", "pct", "project_facts"]
