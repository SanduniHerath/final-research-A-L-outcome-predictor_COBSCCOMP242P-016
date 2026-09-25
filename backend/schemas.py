"""Request bodies of the Phase 9 API. Answer values are checked by ``src.models.student.validate``."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Profile(BaseModel):
    """A student's answers (the questions listed by GET /api/questions)."""

    model_config = ConfigDict(extra="forbid")

    ol_school_type: str
    g6_11_perf_rating: int = Field(ge=1, le=5)
    class_rank_freq: str
    ol_religion: str
    ol_first_language: str
    ol_english: str
    ol_maths: str
    ol_history: str
    ol_science: str
    ol_cat1: str
    ol_cat2: str
    ol_cat3: str
    g11_self_study_hours: str
    se1: int = Field(ge=1, le=5)
    se2: int = Field(ge=1, le=5)
    se3: int = Field(ge=1, le=5)
    se4: int = Field(ge=1, le=5)
    er1: int = Field(ge=1, le=5)
    er2: int = Field(ge=1, le=5)
    er3: int = Field(ge=1, le=5)
    er4: int = Field(ge=1, le=5)
    int1: int = Field(ge=1, le=5)
    int2: int = Field(ge=1, le=5)
    int3: int = Field(ge=1, le=5)
    int4: int = Field(ge=1, le=5)
    career_goal_clear: str
    stream_influences: list[str]
    al_subject_combination: str
    al_district: str | None = None
    al_target_degree: str | None = None


class ProfileRequest(BaseModel):
    """Body of the prediction, gap, recommendation and explanation endpoints."""

    profile: Profile


class ExplainRequest(ProfileRequest):
    """Explanation request; the degree-area explanation is optional."""

    include_degree: bool = True


class ChatTurn(BaseModel):
    """One earlier message of the conversation (kept by the client, not by the server)."""

    role: Literal["user", "assistant"]
    content: str = Field(max_length=2000)


class ChatRequest(ProfileRequest):
    """A chatbot question about the student's results."""

    message: str = Field(min_length=1, max_length=500)
    history: list[ChatTurn] = Field(default_factory=list, max_length=20)
