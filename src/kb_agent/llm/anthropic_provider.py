from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Callable
from pathlib import Path

from kb_agent.llm.base import LLMResponse
from kb_agent.llm.prompts import build_ask_prompt


DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-4-20250514"
DEFAULT_MAX_TOKENS = 2048
CLAUDE_SETTINGS_PATH = Path.home() / ".claude" / "settings.json"


def load_claude_settings_env() -> dict[str, str]:
    if not CLAUDE_SETTINGS_PATH.is_file():
        return {}
    try:
        settings = json.loads(CLAUDE_SETTINGS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    env = settings.get("env", {})
    if not isinstance(env, dict):
        return {}
    return {str(key): str(value) for key, value in env.items()}


def config_value(name: str, settings_env: dict[str, str]) -> str | None:
    return os.environ.get(name) or settings_env.get(name)


def parse_custom_headers(text: str | None) -> dict[str, str]:
    headers: dict[str, str] = {}
    for line in (text or "").splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if key and value:
            headers[key] = value
    return headers


@dataclass(frozen=True)
class AnthropicProvider:
    api_key: str | None
    auth_token: str | None = None
    base_url: str | None = None
    default_headers: dict[str, str] | None = None
    model: str = DEFAULT_ANTHROPIC_MODEL
    max_tokens: int = DEFAULT_MAX_TOKENS

    @classmethod
    def from_env(cls, model: str | None = None) -> "AnthropicProvider":
        settings_env = load_claude_settings_env()
        api_key = config_value("ANTHROPIC_API_KEY", settings_env)
        auth_token = config_value("ANTHROPIC_AUTH_TOKEN", settings_env)
        if not api_key and not auth_token:
            raise ValueError(
                "ANTHROPIC_API_KEY or ANTHROPIC_AUTH_TOKEN is required when using kb ask --llm"
            )

        configured_model = (
            model
            or config_value("KB_AGENT_LLM_MODEL", settings_env)
            or config_value("ANTHROPIC_DEFAULT_SONNET_MODEL", settings_env)
        )
        max_tokens_text = config_value("KB_AGENT_LLM_MAX_TOKENS", settings_env)
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
            auth_token=auth_token,
            base_url=config_value("ANTHROPIC_BASE_URL", settings_env),
            default_headers=parse_custom_headers(
                config_value("ANTHROPIC_CUSTOM_HEADERS", settings_env)
            ),
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
        client_factory: Callable[..., Any] | None = None,
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
        create_client = client_factory or (lambda **kwargs: Anthropic(**kwargs))
        client = create_client(
            api_key=self.api_key,
            auth_token=self.auth_token,
            base_url=self.base_url,
            default_headers=self.default_headers or None,
        )
        try:
            message = client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                messages=[{"role": "user", "content": prompt}],
            )
        except Exception as exc:
            raise ValueError(
                "Anthropic API request failed. Check API key permissions, account "
                f"access, and model availability for {self.model}: {exc}"
            ) from exc
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
