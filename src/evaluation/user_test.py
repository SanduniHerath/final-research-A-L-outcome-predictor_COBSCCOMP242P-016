"""Phase 11: score the user test and the expert review against the targets locked in Phase 2.

    python -m src.evaluation.user_test            # reads data/user_test/*.csv
    python -m src.evaluation.user_test --folder X # another folder (tests use a temporary one)

Writes reports/phase11/user_test_results.json. With 5 testers and 1 expert the results are
descriptive (Phase 2, limitation 7): each value is compared with its threshold, no p-values.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.utils.config import load_config, resolve_path

# Answer key for questionnaire part B (docs/user_testing/04_questionnaire.md). B3 is checked by
# the researcher against the tester's own screen and entered as b3_correct = 1 / 0.
KEY = {"b1": "b", "b2": "c", "b4": "b", "b5": "b", "b6": "a", "b7": "b", "b8": "a"}
MODES = ("close_the_gap", "strengthen")


def sus_score(row: pd.Series) -> float:
    """Standard SUS scoring (Brooke, 1996): odd items score-1, even items 5-score, sum x 2.5."""
    total = 0.0
    for i in range(1, 11):
        value = float(row[f"a{i}"])
        total += value - 1 if i % 2 == 1 else 5 - value
    return total * 2.5


def comprehension(table: pd.DataFrame) -> dict[str, Any]:
    """Share of correct answers over all testers and questions (H10)."""
    correct = pd.DataFrame(
        {q: table[q].astype(str).str.strip().str.lower() == a for q, a in KEY.items()}
    )
    correct["b3"] = table["b3_correct"].astype(int) == 1
    per_question = correct.mean().round(3).to_dict()
    return {"share_correct": round(float(correct.to_numpy().mean()), 3), "per_question": per_question,
            "per_tester": dict(zip(table["tester"], correct.mean(axis=1).round(3), strict=True))}  # fmt: skip


def plan_ratings(table: pd.DataFrame) -> dict[str, Any]:
    """Usefulness of the study plan per mode (H9, testers), from own and example plans."""
    rows = []
    for prefix in ("own", "ex"):
        mode_col = "own_mode" if prefix == "own" else "example_mode"
        for _, r in table.iterrows():
            rows.append({"mode": r[mode_col], "useful": r[f"{prefix}_c1"], "clear": r[f"{prefix}_c2"],
                         "would_try": r[f"{prefix}_c3"], "age_ok": r[f"{prefix}_c4"]})  # fmt: skip
    long = pd.DataFrame(rows).dropna(subset=["mode"])
    out = {}
    for mode in MODES:
        part = long[long["mode"] == mode]
        out[mode] = {"ratings": int(len(part))} | {
            f"median_{c}": (float(part[c].median()) if len(part) else None)
            for c in ("useful", "clear", "would_try", "age_ok")
        }
    return out


def task_summary(table: pd.DataFrame) -> list[dict[str, Any]]:
    """Per task: share done without help, with a hint, not done; median time."""
    out = []
    for task, part in table.groupby("task"):
        result = part["result"].astype(str).str.strip().str.lower()
        out.append(
            {
                "task": int(task),
                "testers": int(len(part)),
                "done": int((result == "done").sum()),
                "hint": int((result == "hint").sum()),
                "not_done": int((result == "not_done").sum()),
                "median_seconds": float(pd.to_numeric(part["seconds"], errors="coerce").median()),
            }
        )
    return out


def verdict(value: float | None, threshold: float) -> str:
    """Descriptive verdict against a threshold."""
    if value is None or np.isnan(value):
        return "no data"
    return "met" if value >= threshold else "not met"


def score(folder: Path) -> dict[str, Any]:
    """All user-test results with their targets."""
    crit = load_config("success_criteria")
    sus = pd.read_csv(folder / "sus.csv").dropna(subset=["a1"])
    comp = pd.read_csv(folder / "comprehension.csv").dropna(subset=["b1"])
    ratings = pd.read_csv(folder / "ratings.csv").dropna(subset=["own_c1"])
    tasks = pd.read_csv(folder / "tasks.csv").dropna(subset=["result"])
    expert = pd.read_csv(folder / "expert.csv").dropna(subset=["relevance"])

    sus_scores = sus.apply(sus_score, axis=1)
    understanding = comprehension(comp)
    plans = plan_ratings(ratings)
    chat_clear = float(ratings["d1"].median()) if len(ratings) else None
    expert_medians = (
        {c: float(expert[c].median()) for c in ("relevance", "actionability", "age_appropriate")}
        if len(expert)
        else {}
    )
    rec_min = crit["recommendation"]["user_test"]["minimum_median_usefulness"]
    exp_min = crit["recommendation"]["expert_review"]["minimum_median"]

    results = {
        "testers": int(len(sus)),
        "H12_usability": {
            "sus_per_tester": dict(zip(sus["tester"], sus_scores.round(1), strict=True)),
            "sus_mean": round(float(sus_scores.mean()), 1) if len(sus) else None,
            "target": crit["usability"]["sus_min"],
            "verdict": verdict(
                float(sus_scores.mean()) if len(sus) else None, crit["usability"]["sus_min"]
            ),
        },
        "H10_comprehension": understanding
        | {
            "target": crit["xai"]["user_test"]["comprehension_questions_min_correct"],
            "verdict": verdict(
                understanding["share_correct"],
                crit["xai"]["user_test"]["comprehension_questions_min_correct"],
            ),
        },
        "H9_recommendations_testers": plans
        | {
            "target_median_usefulness": rec_min,
            "verdict": "met"
            if all((plans[m]["median_useful"] or 0) >= rec_min for m in MODES)
            else (
                "no data for a mode" if any(plans[m]["ratings"] == 0 for m in MODES) else "not met"
            ),
        },
        "H9_recommendations_expert": {
            "medians": expert_medians,
            "target": exp_min,
            "verdict": verdict(min(expert_medians.values()) if expert_medians else None, exp_min),
            "experts": int(expert["expert"].nunique()) if len(expert) else 0,
        },
        "chatbot_clarity": {
            "median": chat_clear,
            "target": crit["chatbot"]["user_test"]["minimum_median_clarity"],
            "verdict": verdict(chat_clear, crit["chatbot"]["user_test"]["minimum_median_clarity"]),
            "noticed_support_tool_notice": int(
                (ratings["d3_noticed"].astype(str).str.lower() == "yes").sum()
            ),
        },
        "tasks": task_summary(tasks),
        "note": "Descriptive results with few raters (Phase 2, limitation 7); not tested statistically.",
    }
    return results


def main() -> int:
    """Score data/user_test (or --folder) and write the results file."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--folder", default="data/user_test")
    parser.add_argument("--out", default=None)
    args = parser.parse_args()
    results = score(resolve_path(args.folder))
    out = (
        Path(args.out)
        if args.out
        else resolve_path(load_config("project")["paths"]["reports"])
        / "phase11"
        / "user_test_results.json"
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, indent=2, default=str), "utf-8")
    print(
        json.dumps(
            {
                k: v.get("verdict") if isinstance(v, dict) else v
                for k, v in results.items()
                if k != "tasks"
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
