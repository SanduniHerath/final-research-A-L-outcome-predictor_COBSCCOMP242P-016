"""Phase 9: the five system parts, the API and the strong / average / weak example profiles."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from src.chatbot.bot import Chatbot
from src.chatbot.guard import REPLIES, in_domain, topic_of, unsupported_numbers
from src.chatbot.llm import LLMUnavailableError, trim_to_sentence
from src.explain.student import merge_onehots
from src.gap.analysis import GapAnalyzer, clean_course, course_status, nearest_year, nice_course
from src.models import student
from src.models.service import calibration_level
from src.recommend.engine import condition_holds, fill, mode_of
from src.system import DecisionSupportSystem
from src.utils.config import load_config, resolve_path

EXAMPLES = load_config("example_profiles")


class FakeModel:
    """Stands in for the language model: returns scripted replies in order."""

    def __init__(self, replies: list[str], name: str = "fake") -> None:
        self.replies, self.name, self.calls = list(replies), name, 0

    def chat(self, messages: list[dict[str, str]]) -> str:
        self.calls += 1
        reply = self.replies.pop(0)
        if reply == "RAISE":
            raise LLMUnavailableError("down")
        return reply


@pytest.fixture(scope="module")
def system() -> DecisionSupportSystem:
    return DecisionSupportSystem.load(chatbot=Chatbot(model=FakeModel(["ok"] * 50), fallback=None))


@pytest.fixture(scope="module")
def reports(system: DecisionSupportSystem) -> dict[str, dict]:
    return {name: system.report(profile) for name, profile in EXAMPLES.items()}


# ---- part 1: prediction ---------------------------------------------------------------------
def test_app_encoding_matches_training_features(system: DecisionSupportSystem) -> None:
    raw = pd.read_csv(
        resolve_path("data/interim/survey_labeled.csv"), keep_default_na=False, na_values=[""]
    )
    features = pd.read_csv(resolve_path("data/processed/features_train.csv"))
    columns = system.predictor.system.columns
    raw = raw.set_index("respondent_id")
    for rid in features["respondent_id"].iloc[:40]:
        x = student.to_features(
            student.profile_from_survey(raw.loc[rid]), system.predictor.system.pipeline, columns
        )
        expected = features.loc[features["respondent_id"] == rid, columns].to_numpy(np.float32)
        assert np.allclose(x, expected, atol=1e-6)


def test_invalid_answers_are_listed() -> None:
    bad = dict(EXAMPLES["average"], ol_maths="Z", se1=None)
    with pytest.raises(ValueError, match="ol_maths") as error:
        student.validate(bad)
    assert "se1: missing" in str(error.value)


def test_prediction_shape_and_messages(reports: dict[str, dict]) -> None:
    for report in reports.values():
        pred = report["prediction"]
        z = pred["zscore"]
        assert z["range_low"] < z["predicted"] < z["range_high"]
        for task in ("zscore_band", "degree_category", "university_group"):
            assert sum(pred[task]["probabilities"].values()) == pytest.approx(1, abs=1e-3)
            assert pred[task]["confidence_message"]
        assert len(pred["university_group"]["top_k"]) == 2
    order = [reports[n]["prediction"]["zscore"]["predicted"] for n in ("weak", "average", "strong")]
    assert order == sorted(order)


def test_calibration_levels_follow_phase7_rules() -> None:
    assert (
        calibration_level(pd.Series({"brier_skill_ci_lower_above_0": False, "ece_meets_max": True}))
        == "very_rough"
    )
    assert (
        calibration_level(pd.Series({"brier_skill_ci_lower_above_0": True, "ece_meets_max": False}))
        == "rough"
    )
    assert (
        calibration_level(pd.Series({"brier_skill_ci_lower_above_0": True, "ece_meets_max": True}))
        == "reliable"
    )


# ---- part 3: gap analysis -------------------------------------------------------------------
def test_ugc_values_match_the_documents() -> None:
    cut = pd.read_csv(resolve_path("data/processed/ugc_cutoffs.csv"))

    def value(year: str, university: str) -> float:
        row = cut[(cut["academic_year"] == year) & (cut["course"] == "MEDICINE")
                  & (cut["university"] == university) & (cut["district"] == "Colombo")]  # fmt: skip
        return float(row["min_z"].iloc[0])

    # Read by eye from the PDFs (first column, Colombo row).
    assert value("2019/2020", "University of Colombo") == pytest.approx(2.4546)
    assert value("2021/2022", "University of Colombo") == pytest.approx(2.3291)
    assert value("2023/2024", "University of Colombo") == pytest.approx(2.3700)
    assert cut.groupby(["source_file", "page", "column"]).size().eq(25).all()


def test_course_name_helpers() -> None:
    assert clean_course("ARCHITECTURE #") == ("ARCHITECTURE", True, False)
    assert nice_course("ENGINEERING (TM)") == "Engineering (TM)"
    assert nice_course("PHYSICAL SCIENCE -ICT") == "Physical Science -ICT"


@pytest.mark.parametrize(
    ("exam_year", "expected"),
    [
        ("2018 or earlier", "2019/2020"),
        (2019, "2019/2020"),
        (2020, "2021/2022"),
        (2022, "2023/2024"),
        (2025, "2023/2024"),
    ],
)
def test_cutoff_year_rule(exam_year: object, expected: str) -> None:
    assert nearest_year(exam_year, load_config("app")["gap"]["cutoff_exam_years"]) == expected


@pytest.mark.parametrize(
    ("z", "low", "high", "cutoff", "status"),
    [
        (2.0, 1.8, 2.2, 1.7, "likely"),
        (2.0, 1.8, 2.2, 1.9, "borderline_above"),
        (2.0, 1.8, 2.2, 2.1, "borderline_below"),
        (2.0, 1.8, 2.2, 2.3, "unlikely"),
        (2.0, 1.8, 2.2, float("nan"), "no_cutoff"),
    ],  # fmt: skip
)
def test_course_status_scenarios(
    z: float, low: float, high: float, cutoff: float, status: str
) -> None:
    assert course_status(z, low, high, cutoff) == status


def _scenario_gap(cutoffs: list[float | None]) -> GapAnalyzer:
    common = {"academic_year": "2023/2024", "course": "MEDICINE", "course_name": "MEDICINE",
              "unicode": "", "district": "Kandy", "page": 1, "aptitude_test_mark": False,
              "special_mark": False}  # fmt: skip
    rows = [
        {**common, "university": f"U{i}", "column": i, "min_z": np.nan if c is None else c}
        for i, c in enumerate(cutoffs)
    ]
    train = pd.DataFrame(
        {
            "degree_category": ["Medicine"] * 20,
            "zscore": np.linspace(1.9, 2.3, 20),
            "al_subject_combination": ["Biology + Chemistry + Physics"] * 20,
        }
    )
    cfg = load_config("app")["gap"]
    return GapAnalyzer(
        pd.DataFrame(rows), train, cfg, load_config("labels")["goal_status"]["target_to_category"]
    )


def _prediction(z: float) -> dict:
    return {"zscore": {"predicted": z, "range_low": z - 0.3, "range_high": z + 0.3},
            "degree_category": {"probabilities": {"Medicine": 0.5}}}  # fmt: skip


@pytest.mark.parametrize(
    ("cutoffs", "z", "status", "mode", "reference"),
    [([1.9, 2.1], 2.0, "on_track", "strengthen", 1.9),       # reaches the lowest cut-off
     ([1.9, 2.1], 1.8, "gap", "close_the_gap", 1.9),          # below every cut-off
     ([None, 2.1], 2.0, "gap", "close_the_gap", 2.1),         # NQC cells are skipped
     ([None, None], 2.0, "gap", "close_the_gap", 2.1),        # no cut-off: data-derived median
     ([None, None], 2.2, "on_track", "strengthen", 2.1)],
)  # fmt: skip
def test_gap_scenarios(cutoffs: list, z: float, status: str, mode: str, reference: float) -> None:
    profile = dict(EXAMPLES["strong"], al_district="Kandy", al_target_degree="Medicine")
    result = _scenario_gap(cutoffs).analyse(profile, _prediction(z))
    assert (result["status"], result["mode"]) == (status, mode)
    assert result["reference"]["value"] == pytest.approx(reference, abs=0.01)
    assert result["reference"]["source"] == ("official" if any(cutoffs) else "data-derived")


def test_no_target_means_strengthen() -> None:
    profile = dict(EXAMPLES["strong"], al_district="Kandy", al_target_degree="I had not decided")
    result = _scenario_gap([1.9]).analyse(profile, _prediction(2.0))
    assert (result["status"], result["mode"]) == ("not_applicable", "strengthen")


def test_only_supplied_cutoffs_are_used(reports: dict[str, dict]) -> None:
    cut = pd.read_csv(resolve_path("data/processed/ugc_cutoffs.csv"))
    known = set(cut["min_z"].dropna().round(4))
    for report in reports.values():
        for course in report["gap"]["courses"]:
            assert course["cutoff"] is None or course["cutoff"] in known
            assert course["document"].startswith("UGC minimum Z-scores")


# ---- part 2: recommendation -----------------------------------------------------------------
def test_rule_helpers() -> None:
    assert condition_holds({"field": "er4", "op": "ge", "value": 4}, {"er4": 4})
    assert not condition_holds({"field": "er4", "op": "ge", "value": 4}, {"er4": None})
    assert fill("Hi {name}, {missing}", {"name": "A"}) == "Hi A, {missing}"
    assert (
        mode_of(pd.Series(["Weekly", "Monthly", "Weekly", "Monthly"]), ["Monthly", "Weekly"])
        == "Weekly"
    )


def test_modes_follow_gap_for_examples(reports: dict[str, dict]) -> None:
    for report in reports.values():
        expected = "close_the_gap" if report["gap"]["status"] == "gap" else "strengthen"
        assert report["recommendations"]["mode"] == expected
    assert reports["strong"]["recommendations"]["mode"] == "strengthen"
    assert reports["weak"]["recommendations"]["mode"] == "close_the_gap"


def test_every_recommendation_has_reason_and_evidence(reports: dict[str, dict]) -> None:
    for report in reports.values():
        recs = report["recommendations"]["recommendations"]
        assert recs
        for rec in recs:
            assert rec["reason"] and rec["evidence"]
            assert "{" not in rec["title"] + rec["text"] + rec["reason"]


def test_rules_fire_on_the_right_answers(reports: dict[str, dict]) -> None:
    weak = {r["id"] for r in reports["weak"]["recommendations"]["recommendations"]}
    strong = {r["id"] for r in reports["strong"]["recommendations"]["recommendations"]}
    assert {
        "schedule",
        "career_goal",
        "foundation",
        "confidence",
    } <= weak  # er4=4, goal No, Science C
    assert not {"schedule", "career_goal", "foundation", "confidence"} & strong
    assert "safety_margin" in strong and "safety_margin" not in weak


def test_similar_students_are_aggregates_only(reports: dict[str, dict]) -> None:
    similar = reports["strong"]["recommendations"]["similar_students"]
    assert similar["n"] >= load_config("app")["recommend"]["min_group"]
    assert "respondent_id" not in str(similar)


# ---- part 5: XAI ----------------------------------------------------------------------------
def test_explanations_add_up_and_are_stable(reports: dict[str, dict]) -> None:
    for report in reports.values():
        for expl in (report["explanation"], report["explanation_degree"]):
            assert expl["additivity_error"] <= 1e-6
            assert expl["sentences"] and expl["detail_sentences"]
        assert report["explanation"]["stability_spearman_top5"] >= 0.8


def test_onehots_of_one_question_are_one_item() -> None:
    items = merge_onehots(["a", "ol_school_type_X", "ol_school_type_Y", "al_subject_combination_Z"])
    assert items == {"a": [0], "ol_school_type": [1, 2], "al_subject_combination": [3]}


# ---- part 4: chatbot ------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("message", "topic"),
    [
        ("Can I get into Medicine?", "in_scope"),
        ("Which tablet helps my headache?", "medical"),
        ("I feel nervous about exams", "psychological"),
        ("I want to die", "crisis"),
        ("Tell me a joke", "unrelated"),
    ],  # fmt: skip
)
def test_topics(message: str, topic: str) -> None:
    assert topic_of(message) == topic


def test_number_check() -> None:
    facts = "Predicted Z-score about 1.42. Range 1.11 to 1.75. Chance 62%. Cut-off 1.5299."
    assert unsupported_numbers("About 1.42 (1.11-1.75), 62% chance, cut-off 1.53.", facts) == []
    assert unsupported_numbers("You need 1.90 and 75%.", facts) == ["1.9", "75%"]
    assert unsupported_numbers("1. Study more", facts) == []  # list markers are not claims


def test_helpers() -> None:
    assert in_domain("What is the cut-off in Galle?") and not in_domain("Which phone should I buy?")
    assert trim_to_sentence("First. Second is cut") == "First."


def _bot(replies: list[str]) -> Chatbot:
    return Chatbot(model=FakeModel(replies), fallback=None)


def test_chatbot_guard_never_calls_the_model(reports: dict[str, dict]) -> None:
    bot = _bot([])
    reply = bot.reply("Which tablets should I take for a headache?", reports["average"])
    assert reply.source == "guard" and reply.reply == REPLIES["medical"] and bot.model.calls == 0
    assert "support tool" in reply.notice


def test_chatbot_control_words(reports: dict[str, dict]) -> None:
    assert (
        _bot(["OUT OF_SCOPE"]).reply("Which phone should I buy?", reports["average"]).reply
        == REPLIES["unrelated"]
    )
    assert (
        _bot(["OUT_OF_SCOPE"]).reply("Cut-off in Galle?", reports["average"]).source
        == "unsure_template"
    )
    assert (
        _bot(["PERSONAL_TOPIC"]).reply("Is skipping breakfast ok?", reports["average"]).reply
        == REPLIES["personal"]
    )


def test_chatbot_rewrites_then_refuses_invented_numbers(reports: dict[str, dict]) -> None:
    fixed = _bot(["You need 9.99.", "Your predicted Z-score is about 1.42."]).reply(
        "What do I need?", reports["average"]
    )
    assert fixed.source == "model" and fixed.rewrites == 1
    refused = _bot(["You need 9.99.", "Still 9.99."]).reply("What do I need?", reports["average"])
    assert refused.source == "number_check_fallback" and "9.99" not in refused.reply


def test_chatbot_unavailable(reports: dict[str, dict]) -> None:
    reply = _bot(["RAISE"]).reply("Am I on track?", reports["average"])
    assert reply.source == "unavailable" and reply.notice


# ---- backend --------------------------------------------------------------------------------
def test_api(system: DecisionSupportSystem) -> None:
    from backend.app import create_app

    system.chatbot = Chatbot(
        model=FakeModel(["Your predicted Z-score is about 1.42."] * 5), fallback=None
    )
    with TestClient(create_app(lambda: system)) as client:
        assert client.get("/api/health").json()["status"] == "ok"
        assert len(client.get("/api/questions").json()) == len(student.MODEL_FIELDS) + 2
        body = {"profile": EXAMPLES["average"]}
        assert client.post("/api/predict", json=body).status_code == 200
        assert client.post("/api/gap", json=body).json()["mode"] == "close_the_gap"
        assert client.post("/api/recommend", json=body).status_code == 200
        assert (
            "zscore" in client.post("/api/explain", json={**body, "include_degree": False}).json()
        )
        chat = client.post("/api/chat", json={**body, "message": "What is my Z-score?"}).json()
        assert chat["notice"] and chat["source"] == "model"
        bad = {"profile": dict(EXAMPLES["average"], ol_maths="Z")}
        assert client.post("/api/predict", json=bad).status_code == 422
        no_target = {"profile": dict(EXAMPLES["average"], al_target_degree=None)}
        assert client.post("/api/gap", json=no_target).status_code == 422


def test_university_groups_follow_the_range() -> None:
    gap = _scenario_gap([1.6, 1.9, 2.1, None])
    groups = gap.university_groups("Medicine", "Kandy", z=2.0, low=1.7, high=2.3)
    assert [u["cutoff"] for u in groups["within_reach"]] == [1.6]  # whole range above
    assert [u["cutoff"] for u in groups["close"]] == [1.9, 2.1]  # cut-off inside the range
    assert groups["further"] == []
    assert len(groups["no_cutoff"]) == 1
    further = gap.university_groups("Medicine", "Kandy", z=1.2, low=1.0, high=1.5)["further"]
    assert [u["cutoff"] for u in further] == [1.6, 1.9, 2.1]


def test_gap_result_lists_universities(reports: dict[str, dict]) -> None:
    for report in reports.values():
        groups = report["gap"]["universities"]
        assert set(groups) == {"within_reach", "close", "further", "no_cutoff"}
        listed = sum(len(v) for v in groups.values())
        assert listed == len(report["gap"]["courses"])
    assert reports["strong"]["gap"]["universities"]["within_reach"]
    assert not reports["weak"]["gap"]["universities"]["within_reach"]


def test_named_university_questions_use_the_cutoff_table(reports: dict[str, dict]) -> None:
    from src.chatbot.lookup import mentioned_universities, university_answer

    average = reports["average"]
    peradeniya = next(
        u
        for rows in average["gap"]["universities"].values()
        for u in rows
        if "Peradeniya" in u["university"]
    )
    answer = university_answer("Can I get into Peradeniya?", average)
    assert (
        f"{peradeniya['cutoff']:.4f}" in answer
        and f"{abs(peradeniya['gap_from_best_guess']):.2f}" in answer
    )
    assert "not a promise" in answer
    assert (
        mentioned_universities("What is the cut-off for Jaffna district?") == []
    )  # a district, not a university
    bot = _bot([])
    reply = bot.reply("Is Moratuwa possible?", average)
    assert reply.source == "university_lookup" and bot.model.calls == 0
