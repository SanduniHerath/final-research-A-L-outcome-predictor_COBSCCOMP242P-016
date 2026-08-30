"""System part 2 - recommendation engine (Phase 9).

Two transparent sources, combined into a short weekly study plan:

1. **Rules** (``configs/recommend.yaml``): each fires on the student's own answers or gap result
   and carries a reason and evidence labels.
2. **Similar successful profiles**: the ``k`` training respondents closest to the student (in the
   34 standardised model inputs) among those who reached the student's target degree area (or, with
   no target, who reached the top Z-score band). Only aggregates are shown, never one respondent.

The mode comes from the gap analysis: ``close_the_gap`` or ``strengthen``. A "what-if" estimate
re-runs the model with one-step-better changeable answers. All of this describes patterns in the
survey data and the model; the wording never promises a result.
"""

from __future__ import annotations

import string
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from src.data.split import load_split_rows
from src.models.cv import band_edges
from src.models.service import Predictor
from src.utils.config import get_seed, load_config, resolve_path

STUDY_ORDER = load_config("features")["ordinal"]["g11_self_study_hours"]["order"]
GRADE_ORDER = load_config("features")["ordinal"]["grades"]["order"]  # W..A -> 0..4
SUBJECT_NAMES = {"ol_maths": "Maths", "ol_science": "Science"}
MODE_TEXT = {
    "close_the_gap": "Close the gap: your plan focuses on the steps most linked to a higher Z-score.",
    "strengthen": "Strengthen: you are on track, so your plan helps you stay there with a safety margin.",
}
RULE_FEATURES = {
    "study_time": ["g11_self_study_hours"],
    "schedule": ["er4", "effort_regulation_index"],
    "weekly_review": ["er3", "effort_regulation_index"],
    "session_goal": ["er1", "effort_regulation_index"],
    "confidence": ["self_efficacy_index", "motivation_index"],
    "interest": ["interest_index", "motivation_index"],
    "career_goal": ["career_goal_clear", "goal_clarity_index"],
    "foundation": ["ol_sci_maths_mean", "ol_maths", "ol_science"],
}


class _Defaults(dict):
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def fill(template: str, facts: dict[str, Any]) -> str:
    """Fill ``{name}`` placeholders from the facts (unknown names stay visible for tests)."""
    return string.Formatter().vformat(" ".join(template.split()), (), _Defaults(facts))


STRUCTURED = ["similar_group", "similar_hours", "soft_hours", "backup_categories"]


def placeholders(rule: dict[str, Any]) -> list[str]:
    """Names used as ``{name}`` in a rule's title, text and reason."""
    names = []
    for part in ("title", "text", "reason"):
        names += [f for _, f, _, _ in string.Formatter().parse(rule[part]) if f]
    return sorted(set(names))


def condition_holds(cond: dict[str, Any], facts: dict[str, Any]) -> bool:
    """Evaluate one rule condition."""
    value, target = facts.get(cond["field"]), cond["value"]
    ops = {
        "eq": lambda: value == target,
        "ne": lambda: value != target,
        "lt": lambda: value is not None and value < target,
        "le": lambda: value is not None and value <= target,
        "gt": lambda: value is not None and value > target,
        "ge": lambda: value is not None and value >= target,
    }
    return bool(ops[cond["op"]]())


def mode_of(values: pd.Series, order: list[str]) -> str | None:
    """Most common answer (ties -> the higher option in the answer order)."""
    counts = values.dropna().astype(str).value_counts()
    if counts.empty:
        return None
    top = counts[counts == counts.max()].index
    return max(top, key=lambda v: order.index(v) if v in order else -1)


@dataclass
class Recommender:
    """Rules + similar successful profiles + what-if estimates."""

    predictor: Predictor
    train_x: np.ndarray
    train_rows: pd.DataFrame
    rules: dict[str, Any]
    cfg: dict[str, Any]

    @classmethod
    def load(cls, predictor: Predictor) -> Recommender:
        """Training inputs (standardised) and answers, aligned by respondent."""
        processed = resolve_path(load_config("project")["paths"]["processed"])
        features = pd.read_csv(processed / "features_train.csv")
        rows = load_split_rows("train").set_index("respondent_id").loc[features["respondent_id"]]
        x = features[predictor.system.columns].to_numpy(np.float32)
        return cls(
            predictor,
            x,
            rows.reset_index(),
            load_config("recommend"),
            load_config("app")["recommend"],
        )

    # ---- similar successful profiles ---------------------------------------------------------
    def pool(self, category: str | None) -> np.ndarray:
        """Indices of 'successful' training respondents for this target."""
        rows = self.train_rows
        if category:
            mask = rows["degree_category"] == category
        else:  # top Z-score band (frozen training edges)
            mask = rows["zscore"] >= band_edges()[-1]
        return np.flatnonzero(mask.to_numpy())

    def group_for(self, category: str | None) -> str | None:
        """The success group used: the target area, or the top band if too few entered it."""
        if category and len(self.pool(category)) >= self.cfg["min_group"]:
            return category
        return None

    def similar(self, x: np.ndarray, category: str | None) -> np.ndarray:
        """Indices of the k nearest successful training respondents."""
        pool = self.pool(self.group_for(category))
        dist = np.linalg.norm(self.train_x[pool] - x, axis=1)
        return pool[np.argsort(dist)[: self.cfg["k_neighbours"]]]

    def distance_check(
        self, x: np.ndarray, category: str | None, rng: np.random.Generator
    ) -> tuple[float, float]:
        """Mean distance to the similar profiles and to as many random training profiles."""
        idx = self.similar(x, category)
        random_idx = rng.choice(len(self.train_x), size=max(len(idx), 1), replace=False)
        near = float(np.linalg.norm(self.train_x[idx] - x, axis=1).mean()) if len(idx) else np.nan
        return near, float(np.linalg.norm(self.train_x[random_idx] - x, axis=1).mean())

    def similar_summary(self, idx: np.ndarray, category: str | None) -> dict[str, Any]:
        """Aggregates of the similar successful respondents (no single respondent is shown)."""
        if len(idx) < self.cfg["min_group"]:
            return {"n": int(len(idx)), "available": False}
        group = self.train_rows.iloc[idx]
        form = {c["name"]: c for c in load_config("columns")["columns"]}

        def dist(column: str) -> dict[str, float]:
            shares = group[column].dropna().astype(str).value_counts(normalize=True)
            order = [str(o) for o in form[column]["options"]]
            return {o: round(float(shares.get(o, 0.0)), 2) for o in order}

        out: dict[str, Any] = {
            "n": int(len(idx)),
            "available": True,
            "group": category,
            "who": (
                f"students in our survey who entered {category}"
                if category
                else "students in our survey in the top Z-score band"
            ),
            "median_z": round(float(group["zscore"].median()), 2),
            "g11_self_study_hours": dist("g11_self_study_hours"),
        }
        for column in self.cfg["al_habits"]:
            out[column] = dist(column)
            out[f"{column}_mode"] = mode_of(
                group[column], [str(o) for o in form[column]["options"]]
            )
        levels = group["g11_self_study_hours"].dropna().map(STUDY_ORDER.index)
        out["g11_study_level_median"] = float(levels.median()) if len(levels) else None
        return out

    # ---- facts and rules ----------------------------------------------------------------------
    def facts(
        self, profile: dict[str, Any], gap: dict[str, Any], similar: dict[str, Any]
    ) -> dict[str, Any]:
        """Everything the rule conditions and texts may use."""
        category = gap.get("target_category")
        p = profile
        er4 = int(p["er4"])
        facts: dict[str, Any] = {
            "target": category or "your goal",
            "target_or_future": category or "the careers you are interested in",
            "has_target": category is not None,
            "mode": gap["mode"],
            "g11_self_study_hours": p["g11_self_study_hours"],
            "study_level": STUDY_ORDER.index(p["g11_self_study_hours"]),
            "er1": int(p["er1"]),
            "er3": int(p["er3"]),
            "er4": er4,
            "se_mean": float(np.mean([int(p[f"se{i}"]) for i in range(1, 5)])),
            "int_mean": float(np.mean([int(p[f"int{i}"]) for i in range(1, 5)])),
            "career_goal_clear": p["career_goal_clear"],
            "al_subject_combination": p["al_subject_combination"],
            "subject_warning": "warning" in gap.get("subject_check", {}),
            "gap_points": gap.get("gap_points"),
            "big_gap": (gap.get("gap_points") or 0) > self.cfg["big_gap"],
        }
        backups = [o for o in gap.get("other_options", []) if o["category"] != category]
        facts["has_backup"] = bool(backups)
        facts["backup_list"] = ", ".join(o["category"] for o in backups[:4]) or "none found"

        facts["weak_foundation_subject"], facts["weak_foundation_grade"] = "", ""
        limit = GRADE_ORDER.index(self.rules["foundation_max_grade"])
        for subject in self.rules["foundation_subjects"].get(category, []) if category else []:
            if GRADE_ORDER.index(p[subject]) <= limit:
                facts["weak_foundation_subject"] = SUBJECT_NAMES[subject]
                facts["weak_foundation_grade"] = p[subject]
                break

        group = similar.get("group")
        facts["similar_who"] = f"reached {group}" if group else "reached the top Z-score band"
        facts["similar_past_paper_known"] = bool(similar.get("al_past_paper_freq_mode"))
        facts["similar_revision_known"] = bool(similar.get("al_revision_freq_mode"))
        facts["similar_past_paper"] = similar.get("al_past_paper_freq_mode")
        facts["similar_revision"] = similar.get("al_revision_freq_mode")
        facts["similar_study_phrase"] = self.study_phrase(similar.get("al_study_hours_mode"))
        # Structured versions of the English phrases above, for translated interfaces.
        facts["similar_group"] = group
        facts["similar_hours"] = similar.get("al_study_hours_mode")
        facts["soft_hours"] = "studied regularly" in facts["similar_study_phrase"]
        facts["backup_categories"] = [o["category"] for o in backups[:4]]
        median_level = similar.get("g11_study_level_median")
        facts["study_below_similar"] = (
            median_level is not None and facts["study_level"] < median_level
        )

        ref = gap.get("reference") or {}
        facts["has_reference_range"] = False
        if ref.get("source") == "official":
            match = [
                c for c in gap.get("courses", [])
                if c["university"] == ref["university"] and c["cutoff"] == round(ref["value"], 4)
            ]  # fmt: skip
            if match and None not in match[0]["cutoff_range_over_years"]:
                low, high = match[0]["cutoff_range_over_years"]
                facts.update(
                    has_reference_range=True,
                    reference_course=match[0]["course"],
                    reference_university=ref["university"],
                    reference_min=f"{low:.2f}",
                    reference_max=f"{high:.2f}",
                )
        if facts["gap_points"] is not None:
            facts["gap_points"] = f"{facts['gap_points']:.2f}"
        return facts

    def study_phrase(self, hours: str | None) -> str:
        """How similar students' A/L study time is described (softer wording for high hours)."""
        if not hours:
            return "studied regularly during A/L"
        order = [
            str(o)
            for o in next(
                c for c in load_config("columns")["columns"] if c["name"] == "al_study_hours"
            )["options"]
        ]
        if order.index(hours) >= order.index(self.rules["study_hours_soft_from"]):
            return "studied regularly, on most days of the week, during A/L"
        return f"mostly studied {hours.lower()} hours a week during A/L"

    def apply_rules(
        self, facts: dict[str, Any], explanation: dict[str, Any] | None
    ) -> list[dict[str, Any]]:
        """Fired rules, ordered by how much the related answers lowered the prediction."""
        contribution = {}
        if explanation:
            contribution = {i["item"]: i["contribution"] for i in explanation["items"]}
        labels = self.rules["evidence_labels"]
        out = []
        for order, rule in enumerate(self.rules["rules"]):
            if not all(condition_holds(c, facts) for c in rule["when"]):
                continue
            related = RULE_FEATURES.get(rule["id"], [])
            push = sum(contribution.get(f, 0.0) for f in related)
            evidence = [
                labels[e] + (f": {rule['research']}" if e == "research" else "")
                for e in rule["evidence"]
            ]
            out.append(
                {
                    "id": rule["id"],
                    "area": rule["area"],
                    "title": fill(rule["title"], facts),
                    "text": fill(rule["text"], facts),
                    "reason": fill(rule["reason"], facts),
                    "evidence": evidence,
                    "evidence_types": list(rule["evidence"]),
                    # Values behind the placeholders, so the interface can show the text in
                    # Sinhala or Tamil from its own translated templates.
                    "params": {k: facts.get(k) for k in placeholders(rule) + STRUCTURED},
                    "linked_answers_effect": round(push, 3) if related else None,
                    "_order": (0 if related and push < 0 else 1, push if related else 0.0, order),
                }
            )
        out.sort(key=lambda r: r.pop("_order"))
        for rank, rec in enumerate(out, start=1):
            rec["priority"] = rank
        return out

    # ---- what-if ------------------------------------------------------------------------------
    def what_if(self, profile: dict[str, Any], base_z: float) -> dict[str, Any]:
        """Change in predicted Z-score if changeable answers were one step better."""
        out = {}
        combined = dict(profile)
        for area, changes in self.rules["what_if"].items():
            changed = dict(profile)
            for field, step in changes.items():
                changed[field] = combined[field] = self._step(profile, field, step)
            out[area] = round(
                float(self.predictor.predict(changed)["zscore"]["predicted"]) - base_z, 2
            )
        out["all"] = round(
            float(self.predictor.predict(combined)["zscore"]["predicted"]) - base_z, 2
        )
        out["note"] = (
            "This is the model's estimate for students whose answers were one step better. It shows "
            "a pattern in the survey data, not a promise of what will happen."
        )
        return out

    @staticmethod
    def _step(profile: dict[str, Any], field: str, step: Any) -> Any:
        if isinstance(step, str):
            return step
        if field == "g11_self_study_hours":
            level = min(max(STUDY_ORDER.index(profile[field]) + step, 0), len(STUDY_ORDER) - 1)
            return STUDY_ORDER[level]
        return int(min(max(int(profile[field]) + step, 1), 5))

    # ---- main entry ---------------------------------------------------------------------------
    def recommend(
        self,
        profile: dict[str, Any],
        prediction: dict[str, Any],
        gap: dict[str, Any],
        explanation: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """The study plan for the 'My recommendations' page."""
        x = self.predictor.features(profile)[0]
        category = gap.get("target_category")
        idx = self.similar(x, category)
        similar = self.similar_summary(idx, self.group_for(category))
        facts = self.facts(profile, gap, similar)
        recs = self.apply_rules(facts, explanation)
        return {
            "mode": gap["mode"],
            "mode_text": MODE_TEXT[gap["mode"]],
            "weekly_plan": {
                "self_study_advice": f"Similar successful students {self.study_phrase(similar.get('al_study_hours_mode'))}. Build up step by step and keep time for rest.",
                "actions": [r["title"] for r in recs if r["area"] not in ("Options", "Subjects")][
                    :5
                ],
            },
            "recommendations": recs,
            "similar_students": similar,
            "what_if": self.what_if(profile, prediction["zscore"]["predicted"]),
            "note": (
                "These suggestions come from patterns in our survey and from research on studying. "
                "They are not guarantees. Choose what fits you and talk to your teachers."
            ),
        }


def random_generator() -> np.random.Generator:
    """Seeded generator for the distance check."""
    return np.random.default_rng(get_seed())


__all__ = ["Recommender", "condition_holds", "fill", "mode_of", "random_generator"]
