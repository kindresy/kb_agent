import pytest

from kb_agent.llm.anthropic_provider import (
    AnthropicProvider,
    load_claude_settings_env,
    parse_custom_headers,
)
from kb_agent.llm.base import LLMResponse
from kb_agent.llm.prompts import MAX_PROMPT_EVIDENCE_ITEMS, build_ask_prompt


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
    assert "Do not include private reasoning" in prompt


def test_build_ask_prompt_caps_evidence_items_for_llm_context():
    evidence = [
        {
            "type": "source",
            "ref": f"kb://source/manual_{index}",
            "why_relevant": "matched",
            "excerpt": "BAR " * 500,
        }
        for index in range(MAX_PROMPT_EVIDENCE_ITEMS + 5)
    ]

    prompt = build_ask_prompt(
        question="Explain BAR assignment",
        intent="concept",
        evidence=evidence,
        attachments=[],
    )

    assert f"kb://source/manual_{MAX_PROMPT_EVIDENCE_ITEMS - 1}" in prompt
    assert f"kb://source/manual_{MAX_PROMPT_EVIDENCE_ITEMS}" not in prompt
    assert "Evidence items omitted from prompt due to context budget: 5" in prompt


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
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    monkeypatch.setattr("kb_agent.llm.anthropic_provider.load_claude_settings_env", lambda: {})

    with pytest.raises(ValueError, match="ANTHROPIC_API_KEY or ANTHROPIC_AUTH_TOKEN"):
        AnthropicProvider.from_env()


def test_anthropic_provider_from_env_uses_model_and_max_tokens(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("KB_AGENT_LLM_MODEL", "env-model")
    monkeypatch.setenv("KB_AGENT_LLM_MAX_TOKENS", "1234")

    provider = AnthropicProvider.from_env()

    assert provider.model == "env-model"
    assert provider.max_tokens == 1234
    assert provider.api_key == "test-key"


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


def test_parse_custom_headers_skips_invalid_lines():
    headers = parse_custom_headers("X-Device-IP: 1.2.3.4\ninvalid\nX-User: luyuan")

    assert headers == {"X-Device-IP": "1.2.3.4", "X-User": "luyuan"}


def test_load_claude_settings_env_reads_env_without_exposing_secrets(tmp_path, monkeypatch):
    settings = tmp_path / "settings.json"
    settings.write_text(
        '{"env":{"ANTHROPIC_AUTH_TOKEN":"token","ANTHROPIC_BASE_URL":"http://proxy"}}',
        encoding="utf-8",
    )
    monkeypatch.setattr("kb_agent.llm.anthropic_provider.CLAUDE_SETTINGS_PATH", settings)

    env = load_claude_settings_env()

    assert env["ANTHROPIC_AUTH_TOKEN"] == "token"
    assert env["ANTHROPIC_BASE_URL"] == "http://proxy"


def test_anthropic_provider_from_env_supports_claude_code_proxy_settings(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    monkeypatch.delenv("ANTHROPIC_BASE_URL", raising=False)
    monkeypatch.delenv("ANTHROPIC_DEFAULT_SONNET_MODEL", raising=False)
    monkeypatch.setattr(
        "kb_agent.llm.anthropic_provider.load_claude_settings_env",
        lambda: {
            "ANTHROPIC_AUTH_TOKEN": "token",
            "ANTHROPIC_BASE_URL": "http://proxy",
            "ANTHROPIC_CUSTOM_HEADERS": "X-Device-IP: 1.2.3.4\nX-User: luyuan",
            "ANTHROPIC_DEFAULT_SONNET_MODEL": "Kimi-K2.6",
        },
    )

    provider = AnthropicProvider.from_env()

    assert provider.api_key is None
    assert provider.auth_token == "token"
    assert provider.base_url == "http://proxy"
    assert provider.default_headers == {"X-Device-IP": "1.2.3.4", "X-User": "luyuan"}
    assert provider.model == "Kimi-K2.6"


def test_anthropic_provider_wraps_sdk_permission_errors(monkeypatch):
    class PermissionDeniedError(Exception):
        pass

    class Messages:
        def create(self, **kwargs):
            raise PermissionDeniedError("Error code: 403 - Request not allowed")

    class Client:
        messages = Messages()

    provider = AnthropicProvider(api_key="test-key")

    with pytest.raises(ValueError, match="Anthropic API request failed"):
        provider.answer(
            question="What is BAR assignment?",
            intent="concept",
            evidence=[],
            attachments=[],
            client_factory=lambda **kwargs: Client(),
        )


def test_anthropic_provider_passes_proxy_config_to_client_factory():
    captured = {}

    class TextBlock:
        type = "text"
        text = "# Answer\n\nok"

    class Message:
        content = [TextBlock()]

    class Messages:
        def create(self, **kwargs):
            captured["create"] = kwargs
            return Message()

    class Client:
        messages = Messages()

    provider = AnthropicProvider(
        api_key=None,
        auth_token="token",
        base_url="http://proxy",
        default_headers={"X-Device-IP": "1.2.3.4"},
        model="Kimi-K2.6",
    )

    def client_factory(**kwargs):
        captured["client"] = kwargs
        return Client()

    response = provider.answer(
        question="What is BAR assignment?",
        intent="concept",
        evidence=[],
        attachments=[],
        client_factory=client_factory,
    )

    assert response.model == "Kimi-K2.6"
    assert captured["client"]["auth_token"] == "token"
    assert captured["client"]["base_url"] == "http://proxy"
    assert captured["client"]["default_headers"] == {"X-Device-IP": "1.2.3.4"}
    assert captured["create"]["model"] == "Kimi-K2.6"
