"""Phase 11: the user-test scoring is correct (with made-up answers, not real testers)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from src.evaluation.user_test import KEY, score, sus_score


def test_sus_scoring_matches_the_standard() -> None:
    best = pd.Series({f"a{i}": 5 if i % 2 else 1 for i in range(1, 11)})
    worst = pd.Series({f"a{i}": 1 if i % 2 else 5 for i in range(1, 11)})
    middle = pd.Series({f"a{i}": 3 for i in range(1, 11)})
    assert (sus_score(best), sus_score(worst), sus_score(middle)) == (100.0, 0.0, 50.0)


@pytest.fixture()
def made_up(tmp_path: Path) -> Path:
    testers = [f"T{i}" for i in range(1, 6)]
    pd.DataFrame(
        [{"tester": t, **{f"a{i}": 4 if i % 2 else 2 for i in range(1, 11)}} for t in testers]
    ).to_csv(tmp_path / "sus.csv", index=False)
    rows = []
    for n, t in enumerate(testers):
        answers = dict(KEY)
        if n == 0:
            answers["b2"] = "a"  # one wrong answer
        rows.append({"tester": t, **answers, "b3_correct": 1})
    pd.DataFrame(rows).to_csv(tmp_path / "comprehension.csv", index=False)
    pd.DataFrame([{"tester": t, "own_mode": "close_the_gap" if n % 2 else "strengthen", "own_c1": 4, "own_c2": 5,
                   "own_c3": 4, "own_c4": 4, "example_mode": "strengthen" if n % 2 else "close_the_gap",
                   "ex_c1": 4, "ex_c2": 4, "ex_c3": 3, "ex_c4": 5, "d1": 4, "d2": 4, "d3_noticed": "yes",
                   "language": "en"} for n, t in enumerate(testers)]).to_csv(tmp_path / "ratings.csv", index=False)  # fmt: skip
    pd.DataFrame([{"tester": t, "task": k, "result": "done", "seconds": 30, "errors": 0, "notes": ""}
                  for t in testers for k in range(1, 10)]).to_csv(tmp_path / "tasks.csv", index=False)  # fmt: skip
    pd.DataFrame([{"expert": "E1", "example": e, "relevance": 4, "actionability": 4, "age_appropriate": 5, "comment": ""}
                  for e in ("strong", "average", "weak")]).to_csv(tmp_path / "expert.csv", index=False)  # fmt: skip
    return tmp_path


def test_scoring_against_the_locked_targets(made_up: Path) -> None:
    r = score(made_up)
    assert r["testers"] == 5
    assert r["H12_usability"]["sus_mean"] == 75.0 and r["H12_usability"]["verdict"] == "met"
    assert r["H10_comprehension"]["share_correct"] == pytest.approx(39 / 40, abs=1e-3)
    assert r["H10_comprehension"]["verdict"] == "met"
    assert r["H9_recommendations_testers"]["close_the_gap"]["ratings"] == 5
    assert r["H9_recommendations_testers"]["verdict"] == "met"
    assert r["H9_recommendations_expert"]["verdict"] == "met"
    assert (
        r["chatbot_clarity"]["verdict"] == "met"
        and r["chatbot_clarity"]["noticed_support_tool_notice"] == 5
    )
    assert all(t["done"] == 5 for t in r["tasks"])


def test_low_scores_are_reported_as_not_met(made_up: Path) -> None:
    sus = pd.read_csv(made_up / "sus.csv")
    sus.loc[:, [f"a{i}" for i in range(1, 11)]] = 3  # SUS 50
    sus.to_csv(made_up / "sus.csv", index=False)
    assert score(made_up)["H12_usability"]["verdict"] == "not met"
