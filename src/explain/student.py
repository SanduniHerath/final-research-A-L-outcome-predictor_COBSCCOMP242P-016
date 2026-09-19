"""System part 5 - "Why this result?" for one student (Phase 9).

SHAP values (permutation algorithm, as in Phase 8) against 100 training students as the
"typical student" reference. The explanation is run several times with different permutation
seeds; the shown values are the average of the runs (still exactly additive), and the runs are
compared to check stability (H10: Spearman of the top-5 features >= 0.80).

The one-hot columns of one question (school type, A/L subjects) are summed into one line, which
keeps additivity. Contributions describe what the MODEL does with the answers: they are
associations in the survey data, not causes.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from src.explain.core import display_name, group_columns, shap_explain
from src.models.service import Predictor, apply_temperature
from src.utils.config import get_seed, load_config, resolve_path

ONEHOT_QUESTIONS = {
    "ol_school_type_": "ol_school_type",
    "al_subject_combination_": "al_subject_combination",
}
GRADE_NAMES = {
    "ol_religion": "Religion", "ol_first_language": "First language", "ol_english": "English",
    "ol_maths": "Maths", "ol_history": "History", "ol_science": "Science",
}  # fmt: skip
CHANGEABLE_FEATURES = {
    "g11_self_study_hours", "er1", "er2", "er3", "er4", "self_efficacy_index",
    "effort_regulation_index", "interest_index", "motivation_index", "career_goal_clear",
    "goal_clarity_index",
}  # fmt: skip


def merge_onehots(columns: list[str]) -> dict[str, list[int]]:
    """Explanation items -> model column indices (one-hots of one question share an item)."""
    items: dict[str, list[int]] = {}
    for i, col in enumerate(columns):
        key = next((q for p, q in ONEHOT_QUESTIONS.items() if col.startswith(p)), col)
        items.setdefault(key, []).append(i)
    return items


def answer_text(item: str, profile: dict[str, Any]) -> str:
    """The student's own answer(s) behind an explanation item, in words."""
    p = profile

    def scale(names: list[str]) -> str:
        return f"average {np.mean([int(p[n]) for n in names]):.1f} out of 5"

    se, er = ["se1", "se2", "se3", "se4"], ["er1", "er2", "er3", "er4"]
    texts = {
        "ol_core_mean": ", ".join(f"{GRADE_NAMES[g]} {p[g]}" for g in GRADE_NAMES),
        "ol_sci_maths_mean": f"Maths {p['ol_maths']}, Science {p['ol_science']}",
        "ol_n_A": f"{sum(p[g] == 'A' for g in [*GRADE_NAMES, 'ol_cat1', 'ol_cat2', 'ol_cat3'])} A grades",
        "self_efficacy_index": scale(se),
        "effort_regulation_index": f"{scale(er)} (the 'hard to keep a schedule' answer counted in reverse)",
        "interest_index": scale(["int1", "int2", "int3", "int4"]),
        "motivation_index": scale(se + ["int1", "int2", "int3", "int4"]),
        "goal_clarity_index": f"clear career goal: {p['career_goal_clear']}; chose Science for career goals: "
        + ("yes" if "Career Goals" in p["stream_influences"] else "no"),
        "school_performance_index": f"rating {p['g6_11_perf_rating']} out of 5, top of class: {p['class_rank_freq']}",
        "g6_11_perf_rating": f"{p['g6_11_perf_rating']} out of 5",
        "stream_influence_personal_interest": "yes"
        if "Personal Interest" in p["stream_influences"]
        else "no",
        "stream_influence_teachers": "yes" if "Teachers" in p["stream_influences"] else "no",
        "er4": f"{p['er4']} out of 5 (higher = harder to keep a schedule)",
    }
    if item in texts:
        return texts[item]
    if item in ("er1", "er2", "er3"):
        return f"{p[item]} out of 5"
    return str(p.get(item, ""))


def item_name(item: str) -> str:
    """Plain-language name of an explanation item."""
    names = {
        "ol_school_type": "School type",
        "al_subject_combination": "A/L subjects",
        "er4": "Finding it hard to keep a study schedule",
    }
    return names.get(item, display_name(item))


@dataclass
class StudentExplainer:
    """Per-student SHAP explanations of the chosen system."""

    predictor: Predictor
    background: np.ndarray
    max_evals: int
    runs: int
    min_stability: float

    @classmethod
    def load(cls, predictor: Predictor) -> StudentExplainer:
        """Use the same 100 training students as the Phase 8 reference."""
        cfg = load_config("explain")["shap"]
        app = load_config("app")["xai"]
        processed = resolve_path(load_config("project")["paths"]["processed"])
        train = pd.read_csv(processed / "features_train.csv")
        columns = predictor.system.columns
        background = (
            train[columns]
            .sample(cfg["background_rows"], random_state=get_seed())
            .to_numpy(np.float32)
        )
        criteria = load_config("success_criteria")["xai"]["automated"]
        return cls(
            predictor, background, app["max_evals"], app["runs"],
            criteria["top5_stability_min_spearman"],
        )  # fmt: skip

    def task_function(self, task: str, class_index: int | None) -> Any:
        """``f(X)``: predicted Z-score, or the shown (temperature-scaled) chance of one class."""
        f = self.predictor.system.task_function(task)
        if task == "zscore":
            return f
        t = self.predictor.temperatures[task]
        return lambda x: apply_temperature(f(x), t)[:, class_index]

    def shap_runs(self, x: np.ndarray, task: str, class_index: int | None) -> list[Any]:
        """Repeated SHAP runs with different permutation seeds."""
        f = self.task_function(task, class_index)
        return [
            shap_explain(f, x, self.background, self.max_evals, get_seed() + r)
            for r in range(self.runs)
        ]

    @staticmethod
    def stability(values: list[np.ndarray], top: int = 5) -> float:
        """Smallest pairwise Spearman correlation of |SHAP| over each pair's top-``top`` features."""
        rhos = []
        for a, b in combinations(values, 2):
            idx = sorted(set(np.argsort(-np.abs(a))[:top]) | set(np.argsort(-np.abs(b))[:top]))
            rhos.append(spearmanr(np.abs(a[idx]), np.abs(b[idx])).statistic)
        return float(np.min(rhos)) if rhos else 1.0

    def explain(
        self, profile: dict[str, Any], task: str = "zscore", class_name: str | None = None
    ) -> dict[str, Any]:
        """Explanation of one prediction ("zscore", or one class of a classification task)."""
        columns = self.predictor.system.columns
        x = self.predictor.features(profile)
        class_index = None if class_name is None else self.predictor.names[task].index(class_name)
        runs = self.shap_runs(x, task, class_index)
        per_run = [r.values[0] for r in runs]
        values = np.mean(per_run, axis=0)
        base = float(runs[0].base_values[0])
        prediction = float(self.task_function(task, class_index)(x)[0])
        groups = group_columns(columns, load_config("explain")["groups"])
        group_of = {c: g for g, cols in groups.items() for c in cols}

        items = []
        for item, idx in merge_onehots(columns).items():
            contribution = float(values[idx].sum())
            items.append(
                {
                    "item": item,
                    "name": item_name(item),
                    "answer": answer_text(item, profile),
                    "contribution": contribution,
                    "direction": "up" if contribution > 0 else "down",
                    "changeable": item in CHANGEABLE_FEATURES,
                    "group": group_of[columns[idx[0]]],
                }
            )
        items.sort(key=lambda d: -abs(d["contribution"]))
        group_totals = pd.DataFrame(items).groupby("group")["contribution"].sum()
        unit = "Z-score points" if task == "zscore" else "chance (0-1)"
        stability = self.stability(per_run)
        return {
            "task": task,
            "class_name": class_name,
            "unit": unit,
            "typical_student_value": base,
            "prediction": prediction,
            "items": items,
            "groups": {
                g: float(v) for g, v in group_totals.sort_values(key=abs, ascending=False).items()
            },
            "top_up": [d for d in items if d["contribution"] > 0][:3],
            "top_down": [d for d in items if d["contribution"] < 0][:3],
            "additivity_error": float(abs(base + values.sum() - prediction)),
            "stability_spearman_top5": stability,
            "stable": stability >= self.min_stability,
            "stability_note": None
            if stability >= self.min_stability
            else "The order of the smaller factors changed between repeated checks, so focus on "
            "the biggest ones.",
            "sentences": group_sentences(group_totals, task, class_name),
            "detail_sentences": sentences(items, task, class_name),
            "note": (
                "These show how the model used your answers compared with a typical student in our "
                "survey. They are patterns in the data, not proof that one thing causes another."
            ),
        }


GROUP_WORDS = {
    "O/L results": "Your O/L results",
    "Attitudes and study habits": "Your attitudes and study habits",
    "Goals and reasons for Science": "Your goals and reasons for choosing Science",
    "School background and standing": "Your school background and class standing",
    "A/L subject choice": "Your A/L subject choice",
}


def _effect(value: float, task: str, class_name: str | None) -> str:
    verb = "raised" if value > 0 else "lowered"
    if task == "zscore":
        return f"{verb} your predicted Z-score by about {abs(value):.2f}"
    return f"{verb} the chance of {class_name} by about {abs(value) * 100:.0f} percentage points"


def group_sentences(
    totals: pd.Series, task: str, class_name: str | None, min_size: float = 0.005
) -> list[str]:
    """One line per question group (the main, more robust view), biggest first.

    Groups are shown first because single answers that overlap (for example the O/L Science grade
    and the Maths-and-Science average) can share the credit in surprising ways.
    """
    out = []
    for group, value in totals.sort_values(key=abs, ascending=False).items():
        if abs(value) < min_size:
            continue
        out.append(
            f"{GROUP_WORDS.get(group, group)} {_effect(value, task, class_name)}, compared with a typical student in our survey."
        )
    return out


def sentences(
    items: list[dict[str, Any]], task: str, class_name: str | None, n: int = 3
) -> list[str]:
    """Short plain-language lines for the biggest helping and holding-back answers."""
    out = []
    for d in [i for i in items if i["contribution"] > 0][:n] + [
        i for i in items if i["contribution"] < 0
    ][:n]:
        out.append(f"{d['name']} ({d['answer']}) {_effect(d['contribution'], task, class_name)}.")
    return out


__all__ = ["StudentExplainer", "answer_text", "group_sentences", "merge_onehots", "sentences"]
