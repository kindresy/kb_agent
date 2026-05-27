import pytest

from kb_agent.llm.anthropic_provider import AnthropicProvider
from kb_agent.llm.base import LLMResponse
from kb_agent.llm.prompts import build_ask_prompt


def test_build_ask_prompt_contains_evidence_and_citation_rules():
    prompt = build_ask_prompt(
        question="Why was BAR0 not assigned?",
        intent="debug",
        evidence=[
            {
                "type": "source",
                "ref": "kb://source/manual",
                "why_relevant": "source metadata matched question terms",
            }
        ],
        attachments=[],
    )

    assert "Why was BAR0 not assigned?" in prompt
    assert "Intent: debug" in prompt
    assert "kb://source/manual" in prompt
    assert "cite evidence refs exactly" in prompt
    assert "evidence is insufficient" in prompt


def test_llm_response_records_provider_metadata():
    response = LLMResponse(
        text="# Answer\n\nLLM answer",
        provider="anthropic",
        model="claude-sonnet-4-20250514",
    )

    assert response.provider == "anthropic"
    assert response.model == "claude-sonnet-4-20250514"


def test_anthropic_provider_from_env_requires_api_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
        AnthropicProvider.from_env()


def test_anthropic_provider_from_env_uses_model_and_max_tokens(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("KB_AGENT_LLM_MODEL", "env-model")
    monkeypatch.setenv("KB_AGENT_LLM_MAX_TOKENS", "1234")

    provider = AnthropicProvider.from_env()

    assert provider.model == "env-model"
    assert provider.max_tokens == 1234


def test_anthropic_provider_cli_model_overrides_env(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("KB_AGENT_LLM_MODEL", "env-model")

    provider = AnthropicProvider.from_env(model="cli-model")

    assert provider.model == "cli-model"


def test_anthropic_provider_rejects_invalid_max_tokens(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("KB_AGENT_LLM_MAX_TOKENS", "not-an-int")

    with pytest.raises(ValueError, match="KB_AGENT_LLM_MAX_TOKENS"):
        AnthropicProvider.from_env()
