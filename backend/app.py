"""Phase 9 backend: one FastAPI endpoint per system part.

    uvicorn backend.app:app --port 8000

| Part | Endpoint |
|---|---|
| 1 Prediction | POST /api/predict |
| 2 Recommendation | POST /api/recommend |
| 3 Target gap | POST /api/gap |
| 4 Chatbot | POST /api/chat (and POST /api/chat/general before a profile exists) |
| 5 XAI | POST /api/explain |

The Phase 10 web interface (``frontend/``) is served at ``/`` by the same server.

Storage: every answer set and every result (including chatbot questions and replies) is saved in
the app database (``backend/storage.py``, SQLite file set in ``configs/app.yaml`` -> ``storage``),
under the random visit code the browser sends in ``X-Alora-Session``. No name, e-mail or IP address
is stored, and request bodies are never written to the log. ``DELETE /api/my-data`` removes
everything stored for a visit code. For chat speed, a student's results are also kept in memory for
at most 15 minutes (``DecisionSupportSystem.cached_report``).
"""

from __future__ import annotations

import contextlib
import threading
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.schemas import ChatRequest, ExplainRequest, GeneralChatRequest, Profile, ProfileRequest
from backend.storage import AppStore, clean_session
from src.chatbot.llm import OllamaModel
from src.evaluation.stats_api import project_statistics
from src.models import student
from src.system import DecisionSupportSystem
from src.utils.config import load_config, resolve_path

FRONTEND = resolve_path("frontend")


def _safe_warm_up(model: OllamaModel) -> None:
    # If this fails, the chatbot answers "not available" later; the other parts still work.
    with contextlib.suppress(Exception):
        model.warm_up()


def _profile(profile: Profile, gap_fields: bool = False) -> dict[str, Any]:
    """Validated answers as a plain dict (422 with every problem listed if invalid)."""
    data = profile.model_dump()
    try:
        student.validate(data, require_gap_fields=gap_fields)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return data


_UNSET: Any = object()


def create_app(
    loader: Callable[[], DecisionSupportSystem] = DecisionSupportSystem.load,
    store: AppStore | None = _UNSET,
) -> FastAPI:
    """Build the app; tests pass a loader with a fake chatbot and their own (or no) store."""
    state: dict[str, DecisionSupportSystem] = {}
    if store is _UNSET:
        store = AppStore.from_config()

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        state["system"] = loader()
        model = state["system"].chatbot.model
        if hasattr(model, "warm_up"):  # load the language model now, not at the first question
            threading.Thread(target=_safe_warm_up, args=(model,), daemon=True).start()
        yield
        state.clear()

    app = FastAPI(title="A/L Outcome Decision-Support System", version="0.9.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:\d+)?",
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["Content-Type", "X-Alora-Session", "X-Alora-Lang"],
    )

    def system() -> DecisionSupportSystem:
        return state["system"]

    def saved(
        part: str,
        answers: dict[str, Any],
        result: dict[str, Any],
        session: str | None,
        lang: str | None,
        options: dict[str, Any] | None = None,
        question: str | None = None,
    ) -> dict[str, Any]:
        """Store the result in the app database (if switched on) and return it unchanged."""
        if store is not None:
            store.record(
                part, answers, result, session=clean_session(session), lang=lang,
                options=options, question=question,
            )
        return result

    @app.get("/api/health")
    def health() -> dict[str, Any]:
        """Is the system loaded, and can the chatbot model be reached?"""
        model = system().chatbot.model
        available = getattr(model, "available", lambda: True)()
        return {"status": "ok", "chatbot_model": model.name, "chatbot_available": available}

    @app.get("/api/questions")
    def questions() -> list[dict[str, Any]]:
        """The questions and allowed answers for the profile form."""
        return student.questions()

    @app.get("/api/notice")
    def notice() -> dict[str, str]:
        """The support-tool notice the interface must always show next to the chatbot."""
        return {"notice": " ".join(load_config("app")["chatbot"]["notice"].split())}

    @app.get("/api/stats")
    def stats() -> dict[str, Any]:
        """Project, dataset and evaluation statistics (aggregates only) for the Statistics page."""
        return project_statistics()

    @app.get("/api/examples")
    def examples() -> dict[str, Any]:
        """The three made-up example students (for 'Try an example' and for user testing)."""
        return load_config("example_profiles")

    session_header = Header(default=None, alias="X-Alora-Session")
    lang_header = Header(default=None, alias="X-Alora-Lang")

    @app.post("/api/predict")
    def predict(
        body: ProfileRequest, session: str | None = session_header, lang: str | None = lang_header
    ) -> dict[str, Any]:
        """Part 1: Z-score range, band, degree area and university region with confidence."""
        answers = _profile(body.profile)
        return saved("predict", answers, system().predict(answers), session, lang)

    @app.post("/api/gap")
    def gap(
        body: ProfileRequest, session: str | None = session_header, lang: str | None = lang_header
    ) -> dict[str, Any]:
        """Part 3: the student's target compared with the official cut-offs."""
        answers = _profile(body.profile, gap_fields=True)
        return saved("gap", answers, system().analyse_gap(answers), session, lang)

    @app.post("/api/recommend")
    def recommend(
        body: ProfileRequest, session: str | None = session_header, lang: str | None = lang_header
    ) -> dict[str, Any]:
        """Part 2: study plan in 'close the gap' or 'strengthen' mode."""
        answers = _profile(body.profile, gap_fields=True)
        return saved("recommend", answers, system().recommend(answers), session, lang)

    @app.post("/api/explain")
    def explain(
        body: ExplainRequest, session: str | None = session_header, lang: str | None = lang_header
    ) -> dict[str, Any]:
        """Part 5: why this result (SHAP, grouped and per answer)."""
        answers = _profile(body.profile)
        result = system().explain(answers, include_degree=body.include_degree)
        options = {"include_degree": body.include_degree}
        return saved("explain", answers, result, session, lang, options=options)

    @app.post("/api/chat")
    def chat(
        body: ChatRequest, session: str | None = session_header, lang: str | None = lang_header
    ) -> dict[str, Any]:
        """Part 4: grounded chatbot answer, always with the support-tool notice."""
        answers = _profile(body.profile, gap_fields=True)
        history = [turn.model_dump() for turn in body.history]
        result = system().chat(answers, body.message, history)
        return saved("chat", answers, result, session, lang, question=body.message)

    @app.post("/api/chat/general")
    def chat_general(
        body: GeneralChatRequest, session: str | None = session_header, lang: str | None = lang_header
    ) -> dict[str, Any]:
        """Part 4 before a profile exists: questions about the app and its words, same safety checks."""
        history = [turn.model_dump() for turn in body.history]
        result = system().chat(None, body.message, history)
        return saved("chat", {}, result, session, lang, question=body.message)

    @app.delete("/api/my-data")
    def delete_my_data(session: str | None = session_header) -> dict[str, Any]:
        """Delete everything the database holds for this browser's visit code."""
        code = clean_session(session)
        if code is None:
            raise HTTPException(status_code=400, detail="Missing or invalid X-Alora-Session header")
        removed = store.delete_session(code) if store is not None else 0
        return {"deleted_rows": removed}

    if (FRONTEND / "index.html").exists():  # Phase 10 interface, served from the same address
        app.mount("/", StaticFiles(directory=FRONTEND, html=True), name="frontend")
    return app


app = create_app()
