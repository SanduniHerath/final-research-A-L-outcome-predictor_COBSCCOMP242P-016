"""The five system parts loaded once and used together (Phase 9 backend and checks)."""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Any

from src.chatbot.bot import Chatbot
from src.explain.student import StudentExplainer
from src.gap.analysis import GapAnalyzer
from src.models import student
from src.models.service import Predictor
from src.recommend.engine import Recommender


@dataclass
class DecisionSupportSystem:
    """Prediction, recommendation, gap analysis, chatbot and XAI."""

    predictor: Predictor
    gap: GapAnalyzer
    explainer: StudentExplainer
    recommender: Recommender
    chatbot: Chatbot
    # Chat speed: a student's report is kept IN MEMORY ONLY for a short time, keyed by a hash of
    # the answers, so follow-up questions do not rebuild it. Never written to disk.
    cache_seconds: float = 900.0
    cache_size: int = 32
    _cache: dict[str, tuple[float, dict[str, Any]]] = field(default_factory=dict, repr=False)

    @classmethod
    def load(cls, chatbot: Chatbot | None = None) -> DecisionSupportSystem:
        """Load models and data once."""
        predictor = Predictor.load()
        gap = GapAnalyzer.load()
        chatbot = chatbot or Chatbot()
        chatbot.cutoffs = gap.cutoffs  # exact cut-off answers from the official UGC table
        return cls(
            predictor=predictor,
            gap=gap,
            explainer=StudentExplainer.load(predictor),
            recommender=Recommender.load(predictor),
            chatbot=chatbot,
        )

    def predict(self, profile: dict[str, Any]) -> dict[str, Any]:
        """Part 1."""
        return self.predictor.predict(profile)

    def analyse_gap(
        self, profile: dict[str, Any], prediction: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Part 3 (needs district and target)."""
        student.validate(profile, require_gap_fields=True)
        return self.gap.analyse(profile, prediction or self.predict(profile))

    def explain(self, profile: dict[str, Any], include_degree: bool = True) -> dict[str, Any]:
        """Part 5: why the Z-score, and why the most likely degree area."""
        out = {"zscore": self.explainer.explain(profile, "zscore")}
        if include_degree:
            top = self.predict(profile)["degree_category"]["most_likely"]
            out["degree_category"] = self.explainer.explain(profile, "degree_category", top)
        return out

    def recommend(self, profile: dict[str, Any]) -> dict[str, Any]:
        """Part 2 (uses parts 1, 3 and 5)."""
        prediction = self.predict(profile)
        gap = self.analyse_gap(profile, prediction)
        explanation = self.explainer.explain(profile, "zscore")
        return self.recommender.recommend(profile, prediction, gap, explanation)

    def report(self, profile: dict[str, Any]) -> dict[str, Any]:
        """Everything for one student (what the chatbot is grounded on)."""
        prediction = self.predict(profile)
        gap = self.analyse_gap(profile, prediction)
        explanation = self.explain(profile)
        plan = self.recommender.recommend(profile, prediction, gap, explanation["zscore"])
        return {
            "prediction": prediction,
            "gap": gap,
            "explanation": explanation["zscore"],
            "explanation_degree": explanation.get("degree_category"),
            "recommendations": plan,
        }

    def chat(
        self,
        profile: dict[str, Any] | None,
        message: str,
        history: list[dict[str, str]] | None = None,
        results: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Part 4. Without a profile, the chatbot answers general questions about the app."""
        if results is None and profile:
            results = self.cached_report(profile)
        return self.chatbot.reply(message, results, history).as_dict()

    def cached_report(self, profile: dict[str, Any]) -> dict[str, Any]:
        """``report`` with a short in-memory cache (see ``cache_seconds``)."""
        key = hashlib.sha256(json.dumps(profile, sort_keys=True).encode()).hexdigest()
        now = time.monotonic()
        self._cache = {k: v for k, v in self._cache.items() if now - v[0] < self.cache_seconds}
        if key not in self._cache:
            if len(self._cache) >= self.cache_size:
                self._cache.pop(min(self._cache, key=lambda k: self._cache[k][0]))
            self._cache[key] = (now, self.report(profile))
        return self._cache[key][1]


__all__ = ["DecisionSupportSystem"]
