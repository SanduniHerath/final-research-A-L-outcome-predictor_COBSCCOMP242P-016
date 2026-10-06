"""Phase 11: end-to-end tests of the whole system through the API, as the interface uses it.

Each test follows a student's journey (questions -> answers -> prediction -> target -> why ->
plan -> chat) and checks that the five parts agree with each other. The language model is replaced
by a fake one so the tests are fast and repeatable; the real model was tested in Phase 9.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from backend.app import create_app
from src.chatbot.bot import Chatbot
from src.chatbot.llm import LLMUnavailableError
from src.models.student import SUBJECT_COMBINATIONS
from src.system import DecisionSupportSystem
from src.utils.config import load_config

EXAMPLES = load_config("example_profiles")


class FakeModel:
    """Echoes the student's predicted Z-score from the fact sheet, like a well-behaved model."""

    name = "fake"

    def chat(self, messages: list[dict[str, str]]) -> str:
        facts = messages[0]["content"]
        start = facts.index("Predicted A/L Z-score: about ") + len("Predicted A/L Z-score: about ")
        return f"Your predicted Z-score is about {facts[start : start + 4]}."


class DownModel:
    name = "down"

    def chat(self, messages: list[dict[str, str]]) -> str:
        raise LLMUnavailableError("Ollama is not running")


@pytest.fixture(scope="module")
def system() -> DecisionSupportSystem:
    return DecisionSupportSystem.load(chatbot=Chatbot(model=FakeModel(), fallback=None))


@pytest.fixture(scope="module")
def client(system: DecisionSupportSystem) -> TestClient:
    with TestClient(create_app(lambda: system)) as c:
        yield c


def journey(client: TestClient, profile: dict[str, Any]) -> dict[str, Any]:
    body = {"profile": profile}
    out = {name: client.post(f"/api/{name}", json=body) for name in ("predict", "gap", "recommend")}
    out["explain"] = client.post("/api/explain", json={**body, "include_degree": True})
    out["chat"] = client.post(
        "/api/chat", json={**body, "message": "What is my predicted Z-score?"}
    )
    for name, response in out.items():
        assert response.status_code == 200, (name, response.text)
    return {name: response.json() for name, response in out.items()}


@pytest.mark.parametrize("name", ["strong", "average", "weak"])
def test_full_journey_parts_agree(client: TestClient, name: str) -> None:
    r = journey(client, EXAMPLES[name])
    z = r["predict"]["zscore"]["predicted"]
    # target uses the same prediction
    assert r["gap"]["predicted_z"] == z
    assert r["gap"]["range"] == [
        r["predict"]["zscore"]["range_low"],
        r["predict"]["zscore"]["range_high"],
    ]
    # the plan follows the gap status
    assert r["recommend"]["mode"] == (
        "close_the_gap" if r["gap"]["status"] == "gap" else "strengthen"
    )
    # the explanation adds up to the same prediction (before rounding)
    expl = r["explain"]["zscore"]
    assert abs(expl["prediction"] - z) < 0.006
    assert (
        abs(
            expl["typical_student_value"]
            + sum(i["contribution"] for i in expl["items"])
            - expl["prediction"]
        )
        < 1e-5
    )
    # the degree explanation is for the most likely degree area
    assert (
        r["explain"]["degree_category"]["class_name"]
        == r["predict"]["degree_category"]["most_likely"]
    )
    # the chatbot is grounded on the same results and always shows the notice
    assert f"{z:.2f}" in r["chat"]["reply"] and r["chat"]["notice"]
    # every university listed comes from the course list of the same target and district
    listed = {
        (u["university"], u["course"]) for rows in r["gap"]["universities"].values() for u in rows
    }
    assert listed == {(c["university"], c["course"]) for c in r["gap"]["courses"]}


def test_results_order_follows_the_profiles(client: TestClient) -> None:
    z = {
        n: client.post("/api/predict", json={"profile": EXAMPLES[n]}).json()["zscore"]["predicted"]
        for n in EXAMPLES
    }
    assert z["weak"] < z["average"] < z["strong"]


def test_student_without_a_target(client: TestClient) -> None:
    profile = dict(EXAMPLES["average"], al_target_degree="I had not decided")
    r = journey(client, profile)
    assert r["gap"]["status"] == "not_applicable" and r["recommend"]["mode"] == "strengthen"
    assert "choose_target" in {x["id"] for x in r["recommend"]["recommendations"]}


ALL_DISTRICTS = sorted(d for ds in load_config("geography")["provinces"].values() for d in ds)


@pytest.mark.parametrize("district", ALL_DISTRICTS)
def test_every_district_works(client: TestClient, district: str) -> None:
    profile = dict(EXAMPLES["average"], al_district=district)
    gap = client.post("/api/gap", json={"profile": profile}).json()
    assert gap["district"] == district and gap["status"] in {"gap", "on_track", "no_reference"}


@pytest.mark.parametrize(
    "target", [o for o in load_config("labels")["goal_status"]["target_to_category"]]
)
def test_every_target_works(client: TestClient, target: str) -> None:
    profile = dict(EXAMPLES["strong"], al_target_degree=target)
    r = client.post("/api/recommend", json={"profile": profile})
    assert r.status_code == 200
    assert all(x["reason"] and x["evidence"] for x in r.json()["recommendations"])


@pytest.mark.parametrize("combination", SUBJECT_COMBINATIONS)
def test_every_subject_combination_works(client: TestClient, combination: str) -> None:
    profile = dict(EXAMPLES["average"], al_subject_combination=combination)
    assert client.post("/api/predict", json={"profile": profile}).status_code == 200


def test_invalid_input_is_rejected_clearly(client: TestClient) -> None:
    bad = dict(EXAMPLES["average"], ol_maths="Z", se1=9)
    response = client.post("/api/predict", json={"profile": bad})
    assert response.status_code == 422
    missing = {k: v for k, v in EXAMPLES["average"].items() if k != "ol_science"}
    assert client.post("/api/predict", json={"profile": missing}).status_code == 422
    assert (
        client.post("/api/chat", json={"profile": EXAMPLES["average"], "message": ""}).status_code
        == 422
    )


def test_chat_still_answers_safely_when_the_model_is_down(system: DecisionSupportSystem) -> None:
    down = DecisionSupportSystem(system.predictor, system.gap, system.explainer, system.recommender,
                                 Chatbot(model=DownModel(), fallback=None))  # fmt: skip
    with TestClient(create_app(lambda: down)) as c:
        reply = c.post(
            "/api/chat", json={"profile": EXAMPLES["average"], "message": "Am I on track?"}
        ).json()
        assert reply["source"] == "unavailable" and reply["notice"]
        guard = c.post(
            "/api/chat", json={"profile": EXAMPLES["average"], "message": "Which tablet helps?"}
        ).json()
        assert guard["source"] == "guard"  # safety replies do not need the model
        exact = c.post(
            "/api/chat", json={"profile": EXAMPLES["average"], "message": "Is Peradeniya possible?"}
        ).json()
        assert exact["source"] == "university_lookup"  # nor do university lookups
        assert c.post("/api/predict", json={"profile": EXAMPLES["average"]}).status_code == 200


def test_server_keeps_no_student_data_on_disk(client: TestClient) -> None:
    from src.utils.config import resolve_path

    watched = [resolve_path(p) for p in ("data", "reports", "models", "logs")]
    before = {f: f.stat().st_mtime for d in watched for f in d.rglob("*") if f.is_file()}
    journey(client, EXAMPLES["weak"])
    after = {f: f.stat().st_mtime for d in watched for f in d.rglob("*") if f.is_file()}
    changed = [str(f) for f in after if f not in before or after[f] != before[f]]
    changed = [f for f in changed if not f.endswith("project.log")]  # the log never holds answers
    assert changed == []
