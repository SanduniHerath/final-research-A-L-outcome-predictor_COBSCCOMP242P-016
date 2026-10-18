"""Phase 10: the web interface is served, its data endpoints work, and the design rules hold."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app import create_app
from src.chatbot.bot import Chatbot
from src.evaluation.stats_api import MIN_COUNT, parse_ci, project_statistics
from src.system import DecisionSupportSystem

FRONTEND = Path(__file__).resolve().parents[1] / "frontend"
NODE = shutil.which("node")


class FakeModel:
    name = "fake"

    def chat(self, messages: list[dict[str, str]]) -> str:
        return "ok"


@pytest.fixture(scope="module")
def client() -> TestClient:
    system = DecisionSupportSystem.load(chatbot=Chatbot(model=FakeModel(), fallback=None))
    with TestClient(create_app(lambda: system)) as c:
        yield c


def test_interface_is_served(client: TestClient) -> None:
    page = client.get("/")
    assert page.status_code == 200
    assert "<title>Alora" in page.text and 'lang="en"' in page.text
    for path in (
        "/css/tokens.css",
        "/css/app.css",
        "/js/main.js",
        "/i18n/si.js",
        "/i18n/ta.js",
        "/img/logo.svg",
    ):
        assert client.get(path).status_code == 200, path


def test_examples_endpoint(client: TestClient) -> None:
    assert set(client.get("/api/examples").json()) == {"strong", "average", "weak"}


def test_statistics_page_is_removed(client: TestClient) -> None:
    assert client.get("/api/stats").status_code == 404
    assert client.get("/js/pages/stats.js").status_code == 404


def test_chatbot_answers_before_a_profile_exists(client: TestClient) -> None:
    """The floating chatbot (Lumi) works without a profile: general questions, same checks."""
    ask = lambda m: client.post("/api/chat/general", json={"message": m}).json()  # noqa: E731
    reply = ask("What is a cut-off?")
    assert reply["reply"] == "ok" and reply["source"] == "model"
    assert "support tool" in reply["notice"]
    crisis = ask("I want to end my life")
    assert crisis["source"] == "guard" and "1926" in crisis["reply"]
    assert client.post("/api/chat/general", json={"message": ""}).status_code == 422


def test_cutoff_questions_get_exact_answers_from_the_ugc_table(client: TestClient) -> None:
    """A named course and university is answered from the official table, never by the model."""
    ask = lambda m: client.post("/api/chat/general", json={"message": m}).json()  # noqa: E731
    one = ask("Medicine at Peradeniya from Kandy district?")
    assert one["source"] == "university_lookup" and "2.1565" in one["reply"]
    spread = ask("How much Z-score do I need for medicine in Peradeniya university?")
    assert spread["source"] == "university_lookup" and "depended on the district" in spread["reply"]
    assert ask("What is a cut-off?")["source"] == "model"
    follow = client.post("/api/chat/general", json={
        "message": "I am from Kandy district",
        "history": [{"role": "user", "content": "Z-score for medicine in Peradeniya?"}],
    }).json()  # fmt: skip
    assert follow["source"] == "university_lookup" and "2.1565" in follow["reply"]


def test_general_fact_sheet_has_no_student_results() -> None:
    from src.chatbot.facts import general_fact_sheet

    sheet = general_fact_sheet()
    assert "NO STUDENT RESULTS YET" in sheet and "Cut-off:" in sheet
    assert "Predicted A/L Z-score" not in sheet and "STUDY PLAN" not in sheet


def test_statistics_never_show_small_groups() -> None:
    data = project_statistics()["dataset"]
    for key in ("degree_category", "university_group", "subject_combination", "exam_year"):
        for row in data[key]:
            assert row["count"] is None or row["count"] >= MIN_COUNT
    assert all(b["count"] >= MIN_COUNT for b in data["zscore"]["bins"])


def test_parse_ci() -> None:
    assert parse_ci("0.205 [0.180, 0.232]") == {"value": 0.205, "low": 0.18, "high": 0.232}


# ---- design rules -------------------------------------------------------------------------
def _tokens(theme: str = "light") -> dict[str, str]:
    """Colour tokens of one theme: the light set, with the dark block's values on top for dark."""
    css = (FRONTEND / "css" / "tokens.css").read_text("utf-8")
    light, dark = css.split(':root[data-theme="dark"]', 1)
    pick = lambda part: dict(re.findall(r"--(c-[\w-]+):\s*(#[0-9A-Fa-f]{6})", part))  # noqa: E731
    return pick(light) | (pick(dark.split("}", 1)[0]) if theme == "dark" else {})


def _contrast(a: str, b: str) -> float:
    def lum(h: str) -> float:
        rgb = [int(h[i : i + 2], 16) / 255 for i in (1, 3, 5)]
        lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
        return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]

    hi, lo = sorted([lum(a), lum(b)], reverse=True)
    return (hi + 0.05) / (lo + 0.05)


@pytest.mark.parametrize(
    ("fg", "bg", "minimum"),
    [
        ("c-ink", "c-bg", 4.5),
        ("c-ink", "c-surface", 4.5),
        ("c-ink-2", "c-surface", 4.5),
        ("c-ink-2", "c-bg", 4.5),
        ("c-primary-700", "c-surface", 4.5),
        ("c-primary-700", "c-primary-50", 4.5),
        ("c-accent-ink", "c-accent-50", 4.5),
        ("c-down-ink", "c-down-50", 4.5),
        ("c-growth", "c-surface", 4.5),
        ("c-danger", "c-surface", 4.5),
        ("c-focus", "c-surface", 3.0),
        ("c-down", "c-surface", 3.0),
        ("c-primary", "c-surface", 3.0),
        ("c-on-primary", "c-primary", 4.5),
        ("c-on-primary", "c-primary-700", 4.5),
        ("c-on-growth", "c-growth", 4.5),
        ("c-on-accent", "c-accent", 4.5),
        ("c-growth-ink", "c-growth-50", 4.5),
        ("c-primary-700", "c-surface-2", 4.5),
        ("c-ink", "c-surface-2", 4.5),
        ("c-on-inverse", "c-inverse", 4.5),
        ("c-brand", "c-surface", 4.5),
        ("c-focus", "c-bg", 3.0),
        ("c-growth", "c-growth-50", 3.0),
        ("c-down", "c-down-50", 3.0),
        ("c-border", "c-surface", 1.3),
    ],  # fmt: skip
)
@pytest.mark.parametrize("theme", ["light", "dark"])
def test_wcag_contrast(fg: str, bg: str, minimum: float, theme: str) -> None:
    tokens = _tokens(theme)
    assert _contrast(tokens[fg], tokens[bg]) >= minimum, f"{theme}: {fg} on {bg}"


def test_hero_text_is_white_on_the_dark_sky_in_both_themes() -> None:
    for theme in ("light", "dark"):
        tokens = _tokens(theme)
        for stop in ("c-night", "c-hero-mid", "c-hero-end"):
            assert _contrast("#FFFFFF", tokens[stop]) >= 4.5, f"{theme}: white on {stop}"


def test_dark_theme_redefines_every_colour_that_carries_meaning() -> None:
    light, dark = _tokens("light"), _tokens("dark")
    same = {k for k in light if light[k] == dark[k]}
    assert same <= {"c-sunrise", "c-accent", "c-on-accent"}, same


def test_touch_targets_are_at_least_48px() -> None:
    assert "--tap: 48px" in (FRONTEND / "css" / "tokens.css").read_text("utf-8")


@pytest.mark.skipif(NODE is None, reason="Node.js not installed")
def test_translations_have_every_key() -> None:
    result = subprocess.run(
        [NODE, "tools/check_i18n.mjs"], cwd=FRONTEND, capture_output=True, text=True
    )
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.skipif(NODE is None, reason="Node.js not installed")
def test_all_scripts_parse() -> None:
    for path in [*FRONTEND.glob("js/**/*.js"), *FRONTEND.glob("i18n/*.js")]:
        result = subprocess.run(
            [NODE, "--check", str(path)], cwd=FRONTEND, capture_output=True, text=True
        )
        assert result.returncode == 0, f"{path}: {result.stderr}"
