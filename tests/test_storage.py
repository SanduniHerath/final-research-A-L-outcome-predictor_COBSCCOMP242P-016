"""App database: every use of the app is stored under a visit code and can be deleted."""

from __future__ import annotations

import csv
import json
import sqlite3
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app import create_app
from backend.storage import AppStore, clean_session
from src.chatbot.bot import Chatbot
from src.system import DecisionSupportSystem
from src.utils.config import load_config

EXAMPLES = load_config("example_profiles")


class FakeModel:
    name = "fake"

    def chat(self, messages: list[dict[str, str]]) -> str:
        return "I'm not sure. Please ask your teachers."


@pytest.fixture(scope="module")
def system() -> DecisionSupportSystem:
    return DecisionSupportSystem.load(chatbot=Chatbot(model=FakeModel(), fallback=None))


@pytest.fixture()
def store(tmp_path: Path) -> AppStore:
    return AppStore(tmp_path / "alora.db")


@pytest.fixture()
def client(system: DecisionSupportSystem, store: AppStore) -> TestClient:
    with TestClient(create_app(lambda: system, store=store)) as c:
        yield c


def own_profile() -> dict:
    """An example profile with one answer changed, so it counts as a real student's answers."""
    return {**EXAMPLES["average"], "se1": 1 if EXAMPLES["average"]["se1"] != 1 else 2}


def rows(store: AppStore, sql: str) -> list[tuple]:
    with sqlite3.connect(store.path) as db:
        return db.execute(sql).fetchall()


def test_every_part_and_chat_message_is_stored(client: TestClient, store: AppStore) -> None:
    code = str(uuid.uuid4())
    headers = {"X-Alora-Session": code, "X-Alora-Lang": "si"}
    body = {"profile": own_profile()}
    for part in ("predict", "gap", "recommend"):
        assert client.post(f"/api/{part}", json=body, headers=headers).status_code == 200
    assert (
        client.post(
            "/api/explain", json={**body, "include_degree": False}, headers=headers
        ).status_code
        == 200
    )
    reply = client.post(
        "/api/chat", json={**body, "message": "What should I study?"}, headers=headers
    )
    assert reply.status_code == 200

    assert rows(store, "SELECT session_id, language FROM sessions") == [(code, "si")]
    profiles = rows(store, "SELECT answers_json, is_example FROM profiles")
    assert len(profiles) == 1  # the same answers are stored once
    assert json.loads(profiles[0][0])["se1"] == body["profile"]["se1"] and profiles[0][1] == 0
    parts = [r[0] for r in rows(store, "SELECT part FROM results ORDER BY id")]
    assert parts == ["predict", "gap", "recommend", "explain", "chat"]
    stored = json.loads(rows(store, "SELECT result_json FROM results WHERE part = 'predict'")[0][0])
    assert stored == client.post("/api/predict", json=body).json()
    assert rows(store, "SELECT options_json FROM results WHERE part = 'explain'") == [
        ('{"include_degree": false}',)
    ]
    assert rows(store, "SELECT question, reply FROM chat_messages") == [
        ("What should I study?", reply.json()["reply"])
    ]


def test_example_profiles_are_marked(client: TestClient, store: AppStore) -> None:
    client.post(
        "/api/predict",
        json={"profile": EXAMPLES["strong"]},
        headers={"X-Alora-Session": str(uuid.uuid4())},
    )
    assert rows(store, "SELECT is_example FROM profiles") == [(1,)]


def test_delete_my_data_removes_only_that_browser(client: TestClient, store: AppStore) -> None:
    mine, other = str(uuid.uuid4()), str(uuid.uuid4())
    body = {"profile": own_profile()}
    for code in (mine, other):
        client.post("/api/predict", json=body, headers={"X-Alora-Session": code})
        client.post("/api/chat", json={**body, "message": "Hi"}, headers={"X-Alora-Session": code})

    response = client.delete("/api/my-data", headers={"X-Alora-Session": mine})
    # one browser: session + profile + 2 results (predict, chat) + 1 chat message
    assert response.status_code == 200 and response.json()["deleted_rows"] == 5
    for table in ("sessions", "profiles", "results", "chat_messages"):
        assert {r[0] for r in rows(store, f"SELECT session_id FROM {table}")} == {other}
    assert client.delete("/api/my-data").status_code == 400  # no visit code

    # a request that was still running when the student deleted must not store anything afterwards
    client.post("/api/predict", json=body, headers={"X-Alora-Session": mine})
    assert rows(store, f"SELECT COUNT(*) FROM results WHERE session_id = '{mine}'") == [(0,)]
    assert rows(store, "SELECT COUNT(*) FROM sessions") == [(1,)]


def test_bad_visit_codes_are_not_stored(client: TestClient, store: AppStore) -> None:
    assert clean_session("Robert'); DROP TABLE results;--") is None
    client.post(
        "/api/predict", json={"profile": own_profile()}, headers={"X-Alora-Session": "my name"}
    )
    assert rows(store, "SELECT COUNT(*) FROM sessions") == [(0,)]
    assert rows(store, "SELECT session_id FROM results") == [(None,)]


def test_invalid_answers_are_not_stored(client: TestClient, store: AppStore) -> None:
    bad = {**own_profile(), "se1": 9}
    assert client.post("/api/predict", json={"profile": bad}).status_code == 422
    assert rows(store, "SELECT COUNT(*) FROM results") == [(0,)]


def test_export_writes_every_table(client: TestClient, store: AppStore, tmp_path: Path) -> None:
    client.post(
        "/api/predict",
        json={"profile": own_profile()},
        headers={"X-Alora-Session": str(uuid.uuid4())},
    )
    paths = store.export_csv(tmp_path / "export")
    assert [p.stem for p in paths] == ["sessions", "profiles", "results", "chat_messages"]
    with (tmp_path / "export" / "results.csv").open(encoding="utf-8-sig") as handle:
        assert [r["part"] for r in csv.DictReader(handle)] == ["predict"]


def test_storage_can_be_switched_off(system: DecisionSupportSystem) -> None:
    with TestClient(create_app(lambda: system, store=None)) as c:
        assert c.post("/api/predict", json={"profile": own_profile()}).status_code == 200
        assert c.delete("/api/my-data", headers={"X-Alora-Session": str(uuid.uuid4())}).json() == {
            "deleted_rows": 0
        }
