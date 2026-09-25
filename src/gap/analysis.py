"""System part 3 - target gap analysis (Phase 9).

Compares the student's predicted Z-score (point and range) with the minimum Z-scores that the UGC
published for the student's target courses in the student's district. Only two kinds of figures
are used, as the Phase 2 criteria require:

* official: the three UGC documents supplied by the researcher (``src/gap/ugc_cutoffs.py``);
* data-derived: summaries of the TRAINING respondents (never single students).

Status of the target (``gap_status``), fixed before any check is run:

* reference cut-off = the LOWEST published cut-off among the target's courses for the district in
  the chosen year (entering the category anywhere counts as reaching it); NQC cells are skipped;
* ``on_track`` if the predicted Z-score >= reference, otherwise ``gap``;
* if no course of the category has a published cut-off for the district, the median Z-score of the
  training respondents who entered that category is used instead (labelled "data-derived").

The recommendation mode follows the status: ``gap`` -> close the gap, ``on_track`` -> strengthen.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from src.data.split import load_split_rows
from src.utils.config import load_config, resolve_path

NOT_APPLICABLE = "not_applicable"


def clean_course(name: str) -> tuple[str, bool, bool]:
    """Course name without the UGC footnote marks, and whether '#' / '*' was present."""
    aptitude, special = "#" in name, "*" in name
    return re.sub(r"\s*[#*]\s*", " ", name).strip(), aptitude, special


def load_cutoffs() -> pd.DataFrame:
    """The extracted UGC table with clean course names."""
    path = resolve_path(load_config("app")["gap"]["cutoff_file"])
    table = pd.read_csv(path)
    cleaned = table["course"].astype(str).map(clean_course)
    table["course_name"] = [c[0] for c in cleaned]
    table["aptitude_test_mark"] = [c[1] for c in cleaned]
    table["special_mark"] = [c[2] for c in cleaned]
    return table


def nearest_year(exam_year: Any, mapping: dict[int, str]) -> str:
    """Cut-off year for an A/L exam year: closest available, a tie goes to the later year."""
    text = str(exam_year)
    year = 2018 if text.startswith("2018") else int(text)
    best = min(mapping, key=lambda y: (abs(y - year), -y))
    return mapping[best]


def nice_course(name: str) -> str:
    """'ENGINEERING (TM)' -> 'Engineering (TM)': title case, short codes in brackets kept."""
    words = []
    for word in name.split():
        core = word.strip("()-")
        keep = word[0] in "(-" and (len(core) <= 3 or "." in core)
        words.append(word if keep else word.capitalize() if word.isalpha() else word.title())
    return " ".join(words)


def course_status(z: float, low: float, high: float, cutoff: float) -> str:
    """Where a cut-off lies relative to the predicted Z-score and its range."""
    if np.isnan(cutoff):
        return "no_cutoff"
    if low >= cutoff:
        return "likely"
    if z >= cutoff:
        return "borderline_above"
    if high >= cutoff:
        return "borderline_below"
    return "unlikely"


STATUS_WORDS = {
    "likely": "Your whole predicted range is at or above this cut-off.",
    "borderline_above": "Your best guess is above this cut-off, but the lower part of your range is below it.",
    "borderline_below": "Your best guess is below this cut-off, but the upper part of your range reaches it.",
    "unlikely": "Your whole predicted range is below this cut-off.",
    "no_cutoff": "No cut-off was published for your district (NQC in the UGC table).",
}


@dataclass
class GapAnalyzer:
    """Target gap analysis with official cut-offs and training-data summaries."""

    cutoffs: pd.DataFrame
    train: pd.DataFrame
    cfg: dict[str, Any]
    target_to_category: dict[str, str]

    @classmethod
    def load(cls) -> GapAnalyzer:
        """Load the cut-off table and the training respondents (labels and answers)."""
        labels = load_config("labels")["goal_status"]
        return cls(
            load_cutoffs(),
            load_split_rows("train"),
            load_config("app")["gap"],
            labels["target_to_category"],
        )

    # ---- lookups ---------------------------------------------------------------------------
    def category_of(self, target_option: str) -> str | None:
        """Degree category of a questionnaire target option (None = no target)."""
        return self.target_to_category.get(target_option)

    def courses(self, category: str, district: str, year: str) -> pd.DataFrame:
        """Courses of a category in one district and year, with the cut-off range over all years."""
        names = self.cfg["category_courses"][category]
        table = self.cutoffs[
            self.cutoffs["course_name"].isin(names) & (self.cutoffs["district"] == district)
        ]
        spread = table.groupby(["course_name", "university"])["min_z"].agg(["min", "max", "count"])
        latest = table[table["academic_year"] == year].set_index(["course_name", "university"])
        out = latest[["min_z", "unicode", "aptitude_test_mark", "page"]].join(spread, how="left")
        return out.reset_index().rename(
            columns={"min": "min_over_years", "max": "max_over_years", "count": "years_published"}
        )

    def reference(self, category: str, district: str, year: str) -> dict[str, Any]:
        """Reference cut-off for a category: lowest published course cut-off, else data-derived."""
        courses = self.courses(category, district, year)
        published = courses.dropna(subset=["min_z"])
        if not published.empty:
            row = published.loc[published["min_z"].idxmin()]
            return {
                "value": float(row["min_z"]),
                "source": "official",
                "document": f"UGC minimum Z-scores {year}, page {int(row['page'])}",
                "course": row["course_name"],
                "university": row["university"],
                "year": year,
            }
        entrants = self.entrants(category)
        if entrants["n"] >= self.cfg["min_students_for_profile"]:
            return {
                "value": entrants["median_z"],
                "source": "data-derived",
                "course": None,
                "university": None,
                "year": None,
            }
        return {"value": np.nan, "source": "none", "course": None, "university": None, "year": None}

    def entrants(self, category: str) -> dict[str, Any]:
        """Z-scores of training respondents who entered a category (aggregates only)."""
        z = self.train.loc[self.train["degree_category"] == category, "zscore"]
        if len(z) < self.cfg["min_students_for_profile"]:
            return {"n": int(len(z))}
        q1, med, q3 = np.percentile(z, [25, 50, 75])
        return {
            "n": int(len(z)),
            "median_z": round(float(med), 2),
            "q1": round(float(q1), 2),
            "q3": round(float(q3), 2),
        }

    def subject_check(self, category: str, combination: str) -> dict[str, Any]:
        """Share of training entrants of the category who took the same A/L subjects."""
        entrants = self.train[self.train["degree_category"] == category]
        if len(entrants) < self.cfg["min_students_for_profile"]:
            return {"checked": False}
        share = float((entrants["al_subject_combination"] == combination).mean())
        out = {
            "checked": True,
            "share_with_same_subjects": round(share, 3),
            "n": int(len(entrants)),
        }
        if share == 0:
            out["warning"] = (
                f"In our survey, none of the {len(entrants)} students who entered {category} took "
                f"{combination}. Please check the UGC subject requirements for this degree."
            )
        return out

    # ---- status ----------------------------------------------------------------------------
    @staticmethod
    def gap_status(z: float, reference: float) -> str | None:
        """'on_track' or 'gap' (None if there is nothing to compare with)."""
        if np.isnan(reference):
            return None
        return "on_track" if z >= reference else "gap"

    def retrospective_status(
        self, target_option: str, district: str, exam_year: Any, z: float
    ) -> str | None:
        """H8: status for a respondent, using the cut-off year nearest to their A/L exam year."""
        category = self.category_of(target_option)
        if category is None:
            return None
        year = nearest_year(exam_year, self.cfg["cutoff_exam_years"])
        return self.gap_status(z, self.reference(category, district, year)["value"])

    def university_groups(
        self, category: str, district: str, z: float, low: float, high: float
    ) -> dict[str, list[dict[str, Any]]]:
        """Universities offering the category's courses, grouped by last year's cut-off.

        A guide from the official cut-off tables, NOT a prediction of where a student will be
        placed (that also depends on the order in which the student lists universities):
        ``within_reach`` = whole predicted range at or above the cut-off; ``close`` = the cut-off
        lies inside the range; ``further`` = whole range below; ``no_cutoff`` = NQC this year.
        """
        groups: dict[str, list[dict[str, Any]]] = {
            "within_reach": [],
            "close": [],
            "further": [],
            "no_cutoff": [],
        }
        key = {"likely": "within_reach", "borderline_above": "close", "borderline_below": "close",
               "unlikely": "further", "no_cutoff": "no_cutoff"}  # fmt: skip
        courses = self.courses(category, district, self.cfg["latest_year"])
        for _, c in courses.sort_values("min_z", na_position="last").iterrows():
            cutoff = float(c["min_z"])
            state = course_status(z, low, high, cutoff)
            groups[key[state]].append(
                {
                    "university": c["university"],
                    "course": nice_course(c["course_name"]),
                    "cutoff": None if np.isnan(cutoff) else round(cutoff, 4),
                    "status": state,
                    # cut-off minus best guess: > 0 = still to go, <= 0 = best guess already above
                    "gap_from_best_guess": None if np.isnan(cutoff) else round(cutoff - z, 2),
                }
            )
        return groups

    def other_options(
        self, district: str, z: float, low: float, combination: str
    ) -> list[dict[str, Any]]:
        """Categories whose reference cut-off the predicted Z-score reaches (backup options).

        Only categories that training respondents with the same A/L subjects entered are listed.
        """
        out = []
        for category in self.cfg["category_courses"]:
            check = self.subject_check(category, combination)
            if not check["checked"] or check["share_with_same_subjects"] == 0:
                continue
            ref = self.reference(category, district, self.cfg["latest_year"])
            if ref["source"] == "official" and z >= ref["value"]:
                groups = self.university_groups(category, district, z, low, low)
                out.append(
                    {
                        "category": category,
                        "lowest_cutoff": round(ref["value"], 4),
                        "course": nice_course(ref["course"]),
                        "university": ref["university"],
                        "whole_range_above": low >= ref["value"],
                        # universities whose cut-off the predicted Z-score (best guess) reaches
                        "universities_reached": [
                            u
                            for u in self.university_groups(category, district, z, z, z)[
                                "within_reach"
                            ]
                        ],
                        "universities_whole_range": len(groups["within_reach"]),
                    }
                )
        return out

    def analyse(self, profile: dict[str, Any], prediction: dict[str, Any]) -> dict[str, Any]:
        """Gap between the student's prediction and their target, for the 'My target' page."""
        zinfo = prediction["zscore"]
        z, low, high = zinfo["predicted"], zinfo["range_low"], zinfo["range_high"]
        district, option = profile["al_district"], profile["al_target_degree"]
        year = self.cfg["latest_year"]
        category = self.category_of(option)
        result: dict[str, Any] = {
            "target_option": option,
            "target_category": category,
            "district": district,
            "cutoff_year": year,
            "predicted_z": z,
            "range": [low, high],
            "other_options": self.other_options(
                district, z, low, profile["al_subject_combination"]
            ),
            "university_note": (
                "These universities come from last year's official UGC cut-offs for your district. "
                "This is a guide, not a prediction: the UGC places students by Z-score AND by the "
                "order in which they list universities, and cut-offs change every year."
            ),
            "notes": [
                f"Cut-offs are the UGC minimum Z-scores for {year} for your district. They change "
                "every year, so they are a guide, not a promise.",
                "Your predicted Z-score is an estimate. Your own work in A/L can change your result.",
            ],
        }
        if category is None:
            result.update(
                status=NOT_APPLICABLE,
                mode="strengthen",
                message="You have not chosen a target degree yet. Here are the degree areas your "
                "predicted Z-score reaches in your district, to help you explore.",
            )
            return result

        ref = self.reference(category, district, year)
        status = self.gap_status(z, ref["value"])
        courses = self.courses(category, district, year)
        course_rows = []
        for _, c in courses.sort_values("min_z", na_position="last").iterrows():
            state = course_status(z, low, high, float(c["min_z"]))
            course_rows.append(
                {
                    "course": nice_course(c["course_name"]),
                    "university": c["university"],
                    "cutoff": None if np.isnan(c["min_z"]) else round(float(c["min_z"]), 4),
                    "cutoff_range_over_years": [
                        None
                        if np.isnan(c["min_over_years"])
                        else round(float(c["min_over_years"]), 4),
                        None
                        if np.isnan(c["max_over_years"])
                        else round(float(c["max_over_years"]), 4),
                    ],
                    "years_published": int(c["years_published"]),
                    "status": state,
                    "status_text": STATUS_WORDS[state],
                    "aptitude_test_mark": bool(c["aptitude_test_mark"]),
                    "document": f"UGC minimum Z-scores {year}, page {int(c['page'])}",
                }
            )
        gap_points = None if status is None else round(max(ref["value"] - z, 0.0), 2)
        degree_probs = prediction["degree_category"]["probabilities"]
        result.update(
            status=status or "no_reference",
            mode="close_the_gap" if status == "gap" else "strengthen",
            reference=ref,
            gap_points=gap_points,
            courses=course_rows,
            universities=self.university_groups(category, district, z, low, high),
            entrants=self.entrants(category),
            subject_check=self.subject_check(category, profile["al_subject_combination"]),
            model_chance_of_target=degree_probs.get(category),
            message=self.message(category, status, ref, gap_points, z),
        )
        return result

    @staticmethod
    def message(
        category: str, status: str | None, ref: dict[str, Any], gap: float | None, z: float
    ) -> str:
        """One plain sentence about the gap."""
        if status is None:
            return f"We could not find a cut-off for {category} in your district to compare with."
        where = (
            f"the lowest {ref['year']} cut-off for {category} in your district "
            f"({nice_course(ref['course'])}, {ref['university']}: {ref['value']:.2f})"
            if ref["source"] == "official"
            else f"the usual Z-score of students in our survey who entered {category} ({ref['value']:.2f})"
        )
        if status == "on_track":
            return f"Your predicted Z-score ({z:.2f}) reaches {where}. Keep going to make it safer."
        return f"Your predicted Z-score ({z:.2f}) is {gap:.2f} below {where}. A study plan can help close this gap."


__all__ = [
    "GapAnalyzer",
    "clean_course",
    "course_status",
    "load_cutoffs",
    "nearest_year",
    "nice_course",
]
