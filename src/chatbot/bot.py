"""System part 4 - the grounded chatbot (Phase 9).

Order of work for each message:

1. The guard sorts the message. Crisis, medical, psychological and clearly unrelated messages get a
   fixed, safe reply; the language model never sees them.
2. Otherwise the model gets strict rules and the student's fact sheet (``facts.py``) and nothing
   else. All decisions (on track or not, which cut-off, how sure) were already made by the other
   four parts in Python; the model only explains them in simple words.
3. The reply is checked: ``OUT_OF_SCOPE`` becomes the fixed refusal, and any number that is not in
   the fact sheet or the student's message triggers one rewrite; if numbers are still invented, a
   safe "not sure" reply is sent instead.

Every response carries the support-tool notice.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from src.chatbot.facts import build_fact_sheet
from src.chatbot.guard import (
    OUT_OF_SCOPE_PATTERN,
    OUT_OF_SCOPE_TOKEN,
    PERSONAL_PATTERN,
    PERSONAL_TOKEN,
    REPLIES,
    in_domain,
    topic_of,
    unsupported_numbers,
)
from src.chatbot.llm import ChatModel, LLMUnavailableError, OllamaModel
from src.chatbot.lookup import university_answer
from src.utils.config import load_config

SYSTEM_PROMPT = """You are a friendly study-support assistant in an app for Sri Lankan students who \
have just finished their O/L exams and are starting the A/L Science stream.

Rules you must always follow:
1. Use ONLY the FACTS below. Do not use any other knowledge about cut-offs, universities, courses, exams, careers or statistics.
2. If the question is about studies, exams, A/L, degrees, careers or universities but the FACTS do not answer it, start your reply with "{unsure}" and suggest asking a teacher or checking the official UGC handbook. Do not guess.
3. The FACTS are about this one student only. You know nothing about other people (friends, classmates, family). For questions about them, use rule 2.
4. Never write a number that is not in the FACTS or in the student's question. Copy numbers exactly as they appear in the FACTS, and only with the thing they belong to.
5. Do not change any decision in the FACTS (for example "on track" or "below the cut-off").
6. Never give medical, health or psychological advice. If the student asks about health, sleep, food, feelings, worries or stress, reply with exactly: {personal}
7. Only if the question has nothing to do with studying, exams, A/L, O/L, degrees, careers, university entry or this app, reply with exactly: {token}
8. Use simple English for a 15-16 year old. Be kind and encouraging. Never promise a result. Keep the answer under 45 words.
9. When asked what to do, follow the STUDY PLAN steps in their order (Step 1 is the most important).
10. Cut-offs in the FACTS are only for the student's own district. A university's name is not a district.

FACTS:
{facts}"""

REWRITE = (
    "Your answer used these numbers that are not in the FACTS: {numbers}. Rewrite the answer using "
    "only numbers that appear in the FACTS, or leave the numbers out."
)


@dataclass
class ChatReply:
    """One chatbot answer and how it was produced."""

    reply: str
    source: str  # model, guard, out_of_scope, unsure_template, university_lookup, number_check_fallback, unavailable
    topic: str
    model: str | None
    seconds: float
    rewrites: int
    unsupported_numbers: list[str]
    notice: str

    def as_dict(self) -> dict[str, Any]:  # noqa: D102
        return self.__dict__.copy()


class Chatbot:
    """Grounded chatbot over one student's results."""

    def __init__(self, model: ChatModel | None = None, fallback: ChatModel | None = None) -> None:
        """Use the configured Ollama models unless models are passed in (tests use fakes)."""
        self.cfg = load_config("app")["chatbot"]
        if model is None:
            common = {"url": self.cfg["url"], "temperature": self.cfg["temperature"],
                      "max_tokens": self.cfg["max_tokens"], "timeout": self.cfg["timeout_seconds"]}  # fmt: skip
            model = OllamaModel(self.cfg["model"], **common)
            fallback = OllamaModel(self.cfg["fallback_model"], **common)
        self.model, self.fallback = model, fallback

    def _system(self, facts: str) -> str:
        return SYSTEM_PROMPT.format(
            unsure=self.cfg["unsure_phrase"],
            token=OUT_OF_SCOPE_TOKEN,
            personal=PERSONAL_TOKEN,
            facts=facts,
        )

    def _call(self, messages: list[dict[str, str]]) -> tuple[str, str]:
        """Ask the main model; if it is unreachable, the fallback model."""
        try:
            return self.model.chat(messages), self.model.name
        except LLMUnavailableError:
            if self.fallback is None:
                raise
            return self.fallback.chat(messages), self.fallback.name

    def reply(
        self, message: str, results: dict[str, Any], history: list[dict[str, str]] | None = None
    ) -> ChatReply:
        """Answer one message about the student's results."""
        start = time.perf_counter()
        notice = " ".join(self.cfg["notice"].split())

        def done(text: str, source: str, topic: str, model: str | None = None,
                 rewrites: int = 0, bad: list[str] | None = None) -> ChatReply:  # fmt: skip
            return ChatReply(text, source, topic, model, round(time.perf_counter() - start, 2),
                             rewrites, bad or [], notice)  # fmt: skip

        topic = topic_of(message)
        if topic != "in_scope":
            return done(REPLIES[topic], "guard", topic)
        exact = university_answer(message, results)
        if exact:  # questions about a named university are answered from the cut-off table
            return done(exact, "university_lookup", topic)

        facts = build_fact_sheet(results)
        turns = (history or [])[-2 * self.cfg["history_turns"] :]
        messages = [{"role": "system", "content": self._system(facts)}, *turns,
                    {"role": "user", "content": message}]  # fmt: skip
        try:
            text, used = self._call(messages)
        except LLMUnavailableError:
            return done(
                "Sorry, the chatbot is not available right now. Your results and study plan are "
                "still on the other pages.",
                "unavailable",
                topic,
            )
        special = self._special(text, message)
        if special:
            return done(*special, used)

        bad = unsupported_numbers(text, facts, message)
        rewrites = 0
        if bad:
            rewrites = 1
            retry = [*messages, {"role": "assistant", "content": text},
                     {"role": "user", "content": REWRITE.format(numbers=", ".join(bad))}]  # fmt: skip
            try:
                text, used = self._call(retry)
            except LLMUnavailableError:
                text = ""
            bad = unsupported_numbers(text, facts, message) if text else ["(no reply)"]
            if bad:
                return done(
                    f"{self.cfg['unsure_phrase']} about that. Please check the numbers on your "
                    "results pages, or ask a teacher.",
                    "number_check_fallback",
                    topic,
                    used,
                    rewrites,
                    bad,
                )
        special = self._special(text, message)
        if special:
            return done(*special, used, rewrites)
        return done(text, "model", topic, used, rewrites)

    @staticmethod
    def _special(text: str, message: str) -> tuple[str, str, str] | None:
        """Turn the model's control words into fixed replies: (reply, source, topic)."""
        if PERSONAL_PATTERN.search(text):
            return REPLIES["personal"], "out_of_scope", "personal"
        if OUT_OF_SCOPE_PATTERN.search(text):
            if in_domain(message):
                return REPLIES["unsure_domain"], "unsure_template", "in_scope"
            return REPLIES["unrelated"], "out_of_scope", "unrelated"
        return None


__all__ = ["ChatReply", "Chatbot", "SYSTEM_PROMPT"]
