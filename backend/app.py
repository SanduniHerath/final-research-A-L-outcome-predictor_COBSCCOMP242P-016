"""Phase 9 backend: one FastAPI endpoint per system part.

    uvicorn backend.app:app --port 8000

| Part | Endpoint |
|---|---|
| 1 Prediction | POST /api/predict |
| 2 Recommendation | POST /api/recommend |
| 3 Target gap | POST /api/gap |
| 4 Chatbot | POST /api/chat |
| 5 XAI | POST /api/explain |

The Phase 10 web interface (``frontend/``) is served at ``/`` by the same server.

Privacy: nothing about a student is written to disk and request bodies are never logged. Every
request carries the answers it needs. For chat speed, a student's results are kept in memory for at
most 15 minutes (``DecisionSupportSystem.cached_report``). The chat history is kept by the client.
"""

from __future__ import annotations

import contextlib
import threading
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.schemas import ChatRequest, ExplainRequest, Profile, ProfileRequest
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


def create_app(loader: Callable[[], DecisionSupportSystem] = DecisionSupportSystem.load) -> FastAPI:
    """Build the app; tests pass a loader with a fake chatbot."""
    state: dict[str, DecisionSupportSystem] = {}

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
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

    def system() -> DecisionSupportSystem:
        return state["system"]

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

    @app.post("/api/predict")
    def predict(body: ProfileRequest) -> dict[str, Any]:
        """Part 1: Z-score range, band, degree area and university region with confidence."""
        return system().predict(_profile(body.profile))

    @app.post("/api/gap")
    def gap(body: ProfileRequest) -> dict[str, Any]:
        """Part 3: the student's target compared with the official cut-offs."""
        return system().analyse_gap(_profile(body.profile, gap_fields=True))

    @app.post("/api/recommend")
    def recommend(body: ProfileRequest) -> dict[str, Any]:
        """Part 2: study plan in 'close the gap' or 'strengthen' mode."""
        return system().recommend(_profile(body.profile, gap_fields=True))

    @app.post("/api/explain")
    def explain(body: ExplainRequest) -> dict[str, Any]:
        """Part 5: why this result (SHAP, grouped and per answer)."""
        return system().explain(_profile(body.profile), include_degree=body.include_degree)

    @app.post("/api/chat")
    def chat(body: ChatRequest) -> dict[str, Any]:
        """Part 4: grounded chatbot answer, always with the support-tool notice."""
        history = [turn.model_dump() for turn in body.history]
        return system().chat(_profile(body.profile, gap_fields=True), body.message, history)

    if (FRONTEND / "index.html").exists():  # Phase 10 interface, served from the same address
        app.mount("/", StaticFiles(directory=FRONTEND, html=True), name="frontend")
    return app


app = create_app()
