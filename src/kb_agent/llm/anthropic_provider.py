from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from kb_agent.llm.base import LLMResponse
from kb_agent.llm.prompts import build_ask_prompt


DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-4-20250514"
DEFAULT_MAX_TOKENS = 2048


@dataclass(frozen=True)
class AnthropicProvider:
    api_key: str
    model: str = DEFAULT_ANTHROPIC_MODEL
    max_tokens: int = DEFAULT_MAX_TOKENS

    @classmethod
    def from_env(cls, model: str | None = None) -> "AnthropicProvider":
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY is required when using kb ask --llm")

        configured_model = model or os.environ.get("KB_AGENT_LLM_MODEL")
        max_tokens_text = os.environ.get("KB_AGENT_LLM_MAX_TOKENS")
        max_tokens = DEFAULT_MAX_TOKENS
        if max_tokens_text:
            try:
                max_tokens = int(max_tokens_text)
            except ValueError as exc:
                raise ValueError("KB_AGENT_LLM_MAX_TOKENS must be an integer") from exc
            if max_tokens <= 0:
                raise ValueError("KB_AGENT_LLM_MAX_TOKENS must be greater than zero")

        return cls(
            api_key=api_key,
            model=configured_model or DEFAULT_ANTHROPIC_MODEL,
            max_tokens=max_tokens,
        )

    def answer(
        self,
        *,
        question: str,
        intent: str,
        evidence: list[dict[str, str]],
        attachments: list[dict[str, object]],
    ) -> LLMResponse:
        try:
            from anthropic import Anthropic
        except ImportError as exc:
            raise ValueError(
                "Anthropic Python SDK is required for kb ask --llm; "
                "install the project dependencies first"
            ) from exc

        prompt = build_ask_prompt(
            question=question,
            intent=intent,
            evidence=evidence,
            attachments=attachments,
        )
        client = Anthropic(api_key=self.api_key)
        message = client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        text = _extract_text(message)
        if not text:
            raise ValueError("Anthropic returned an empty response")
        return LLMResponse(text=text, provider="anthropic", model=self.model)


def _extract_text(message: Any) -> str:
    parts: list[str] = []
    for block in getattr(message, "content", []):
        if getattr(block, "type", None) == "text":
            parts.append(str(getattr(block, "text", "")))
    return "\n".join(part for part in parts if part).strip()

