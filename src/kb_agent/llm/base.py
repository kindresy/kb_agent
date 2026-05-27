from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class LLMResponse:
    text: str
    provider: str
    model: str


class LLMProvider(Protocol):
    def answer(
        self,
        *,
        question: str,
        intent: str,
        evidence: list[dict[str, str]],
        attachments: list[dict[str, object]],
    ) -> LLMResponse:
        """Generate an answer from a retrieved evidence pack."""

