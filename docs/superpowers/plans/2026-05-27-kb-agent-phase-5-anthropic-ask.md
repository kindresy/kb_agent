# KB Agent Phase 5 Anthropic Ask Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add optional Anthropic Claude answer generation to `kb ask --llm` while preserving the deterministic offline default.

**Architecture:** Keep `run_ask()` as the session workflow owner and introduce a small `kb_agent.llm` provider boundary. The LLM path consumes the same deterministic evidence pack and writes the same session artifacts with extra answer-mode metadata.

**Tech Stack:** Python 3.11+, Typer, pytest, Anthropic Python SDK.

---

## File Structure

- Create `src/kb_agent/llm/__init__.py`: public exports for LLM helpers.
- Create `src/kb_agent/llm/base.py`: `LLMProvider` protocol and `LLMResponse`.
- Create `src/kb_agent/llm/prompts.py`: evidence-constrained ask prompt renderer.
- Create `src/kb_agent/llm/anthropic_provider.py`: Anthropic Messages API adapter.
- Modify `src/kb_agent/ask.py`: add `use_llm`, `model`, and injectable provider support.
- Modify `src/kb_agent/cli.py`: add `kb ask --llm` and `--model`.
- Modify `src/kb_agent/learn.py`: preserve LLM ask-session provenance in
  `learn --from-session`.
- Modify `pyproject.toml`: add the Anthropic SDK dependency.
- Modify `README.md`: document setup and smoke-test commands.
- Test `tests/test_ask.py`: keep deterministic regression coverage and add LLM-mode session tests.
- Test `tests/test_llm.py`: prompt and Anthropic provider configuration tests.

## Task 1: Provider Boundary and Prompt Tests

**Files:**
- Create: `src/kb_agent/llm/__init__.py`
- Create: `src/kb_agent/llm/base.py`
- Create: `src/kb_agent/llm/prompts.py`
- Test: `tests/test_llm.py`

- [ ] **Step 1: Write failing prompt/provider contract tests**

Add tests proving:

```python
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
```

- [ ] **Step 2: Run tests to verify RED**

Run:

```bash
uv run --extra dev pytest tests/test_llm.py -q
```

Expected: import failure for missing `kb_agent.llm`.

- [ ] **Step 3: Add minimal provider boundary and prompt builder**

Implement:

```python
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
    ) -> LLMResponse: ...
```

`build_ask_prompt()` should render question, intent, evidence JSON, attachment
metadata JSON, and strict citation instructions.

- [ ] **Step 4: Run tests to verify GREEN**

Run:

```bash
uv run --extra dev pytest tests/test_llm.py -q
```

Expected: pass.

## Task 2: Ask Workflow LLM Mode

**Files:**
- Modify: `src/kb_agent/ask.py`
- Test: `tests/test_ask.py`

- [ ] **Step 1: Write failing `run_ask` fake-provider test**

Add a fake provider:

```python
class FakeProvider:
    def answer(self, *, question, intent, evidence, attachments):
        from kb_agent.llm.base import LLMResponse

        assert question == "Explain BAR Assignment"
        assert intent == "concept"
        assert evidence
        return LLMResponse(
            text="# Answer\n\nLLM cited answer using kb://source/manual",
            provider="anthropic",
            model="claude-sonnet-4-20250514",
        )
```

Test expectations:

- `run_ask(root, question, use_llm=True, llm_provider=FakeProvider())` returns
  the LLM answer;
- `answer.md` contains the LLM answer;
- `evidence_pack.json` contains `answer_mode: llm`,
  `llm_provider: anthropic`, and the model;
- deterministic `kb ask` still records `answer_mode: deterministic`.

- [ ] **Step 2: Run targeted tests to verify RED**

Run:

```bash
uv run --extra dev pytest tests/test_ask.py -q
```

Expected: failure because `run_ask()` does not accept `use_llm`.

- [ ] **Step 3: Implement minimal LLM branch in `run_ask()`**

Extend `run_ask()` signature:

```python
def run_ask(
    root: Path,
    question: str,
    attachment_paths: list[Path] | None = None,
    *,
    use_llm: bool = False,
    model: str | None = None,
    llm_provider: LLMProvider | None = None,
) -> AskResult:
```

When `use_llm` is true, call the provider and use its text as the answer. If no
provider is injected, construct the Anthropic provider. Write answer-mode
metadata into `evidence_pack.json`.

Evidence rows should include a bounded `excerpt` field when local text exists.
Provider failures after session allocation must remove the partial session
directory before re-raising the error.

- [ ] **Step 4: Run targeted tests to verify GREEN**

Run:

```bash
uv run --extra dev pytest tests/test_ask.py tests/test_llm.py -q
```

Expected: pass.

## Task 3: Anthropic Provider and CLI Wiring

**Files:**
- Create: `src/kb_agent/llm/anthropic_provider.py`
- Modify: `src/kb_agent/cli.py`
- Modify: `pyproject.toml`
- Test: `tests/test_llm.py`
- Test: `tests/test_ask.py`

- [ ] **Step 1: Write failing configuration and CLI tests**

Add tests proving:

- `AnthropicProvider.from_env()` raises `ValueError` mentioning
  `ANTHROPIC_API_KEY` when the key is absent;
- `kb ask --llm "QUESTION"` exits with code 1 and prints
  `ANTHROPIC_API_KEY` when the key is absent;
- `--model` is accepted by the CLI parser.

- [ ] **Step 2: Run targeted tests to verify RED**

Run:

```bash
uv run --extra dev pytest tests/test_llm.py tests/test_ask.py -q
```

Expected: import/signature failures for missing provider and CLI options.

- [ ] **Step 3: Implement Anthropic adapter and CLI options**

Implementation requirements:

- read `ANTHROPIC_API_KEY` only from env;
- default model: `claude-sonnet-4-20250514`;
- allow `KB_AGENT_LLM_MODEL` and `--model` override;
- default max tokens: `2048`;
- allow `KB_AGENT_LLM_MAX_TOKENS` override;
- call `client.messages.create(model=..., max_tokens=..., messages=[...])`;
- extract text blocks from the response;
- raise `ValueError` with actionable messages for missing key, missing SDK, and
  empty model output.

CLI options:

```python
llm: bool = typer.Option(False, "--llm", help="Use configured LLM provider for answer generation.")
model: str | None = typer.Option(None, "--model", help="Override LLM model for this answer.")
```

- [ ] **Step 4: Run targeted tests to verify GREEN**

Run:

```bash
uv run --extra dev pytest tests/test_llm.py tests/test_ask.py -q
```

Expected: pass.

## Task 4: Documentation and Full Verification

**Files:**
- Modify: `README.md`
- Modify: `docs/superpowers/specs/2026-05-27-kb-agent-phase-5-anthropic-ask-design.md`

- [ ] **Step 1: Document Anthropic setup**

Add README section:

```markdown
## Phase 5 optional LLM ask

`kb ask` remains deterministic by default. To use Claude for answer generation:

```bash
export ANTHROPIC_API_KEY="..."
kb ask --llm "Explain PCIe BAR assignment"
```

Optional:

```bash
export KB_AGENT_LLM_MODEL=claude-sonnet-4-20250514
kb ask --llm --model claude-sonnet-4-20250514 "Why was BAR0 not assigned?"
```

LLM answers are saved only into the ask session. Promote useful findings through
the existing review path, for example `kb learn --from-session <session>`.
```

Also document that LLM session learning keeps `answer_mode=llm` provenance and
does not treat the LLM answer as deterministic source truth.

- [ ] **Step 2: Run full verification**

Run:

```bash
uv run --extra dev pytest -q
```

Expected: all tests pass without `ANTHROPIC_API_KEY`.

- [ ] **Step 3: Inspect git diff**

Run:

```bash
git diff --stat
git diff -- src/kb_agent/ask.py src/kb_agent/cli.py src/kb_agent/llm tests README.md pyproject.toml
```

Expected: only Phase 5 LLM ask files changed.

- [ ] **Step 4: Commit**

Run:

```bash
git add README.md pyproject.toml src/kb_agent tests docs/superpowers/specs/2026-05-27-kb-agent-phase-5-anthropic-ask-design.md docs/superpowers/plans/2026-05-27-kb-agent-phase-5-anthropic-ask.md
git commit -m "feat: add optional Anthropic ask mode"
```
