"""Small client for a local Ollama server (free, offline; student data never leaves the computer)."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Protocol

import httpx


def trim_to_sentence(text: str) -> str:
    """Cut a reply that hit the length limit back to its last complete sentence."""
    if text.endswith((".", "!", "?")):
        return text
    end = max(text.rfind(mark) for mark in (". ", "! ", "? ", ".\n"))
    return text[: end + 1] if end > 0 else text


class ChatModel(Protocol):
    """Anything that turns chat messages into a reply (a fake one is used in unit tests)."""

    name: str

    def chat(self, messages: list[dict[str, str]]) -> str:
        """Return the assistant's reply."""
        ...


class LLMUnavailableError(RuntimeError):
    """The language model server could not be reached or failed."""


@dataclass
class OllamaModel:
    """Chat with one model on a local Ollama server."""

    name: str
    url: str = "http://localhost:11434"
    temperature: float = 0.2
    max_tokens: int = 220
    timeout: float = 60.0

    def chat(self, messages: list[dict[str, str]]) -> str:
        """Send the messages and return the reply text."""
        body: dict[str, Any] = {
            "model": self.name,
            "messages": messages,
            "stream": False,
            "keep_alive": "30m",
            "options": {
                "temperature": self.temperature,
                "num_predict": self.max_tokens,
                "seed": 42,
            },
        }
        try:
            response = httpx.post(f"{self.url}/api/chat", json=body, timeout=self.timeout)
            response.raise_for_status()
        except httpx.HTTPError as error:
            raise LLMUnavailableError(str(error)) from error
        data = response.json()
        text = data["message"]["content"].strip()
        if data.get("done_reason") == "length":
            text = trim_to_sentence(text)
        return text

    def available(self) -> bool:
        """True if the server runs and has this model."""
        try:
            tags = httpx.get(f"{self.url}/api/tags", timeout=3).json()
        except (httpx.HTTPError, ValueError):
            return False
        return any(m["name"] == self.name for m in tags.get("models", []))

    def warm_up(self) -> float:
        """Load the model into memory once (the first reply is otherwise slow); returns seconds."""
        start = time.perf_counter()
        self.chat([{"role": "user", "content": "Say OK."}])
        return time.perf_counter() - start


__all__ = ["ChatModel", "LLMUnavailableError", "OllamaModel", "trim_to_sentence"]
