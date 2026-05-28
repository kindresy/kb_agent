# KB Agent Phase 5.2 Evidence Rerank Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add deterministic evidence reranking and bounded `prompt_evidence` for `kb ask --llm`.

**Architecture:** Introduce a focused evidence selection module used by `run_ask()` before answer generation. Store both full retrieved evidence and selected prompt evidence in ask sessions; call LLM providers with only selected prompt evidence.

**Tech Stack:** Python 3.11+, Typer, pytest.

---

## File Structure

- Create `src/kb_agent/evidence.py`: deterministic scoring and top-N evidence selection.
- Modify `src/kb_agent/ask.py`: call evidence selector, persist `prompt_evidence` and `evidence_selection`, pass selected evidence to LLM provider.
- Modify `tests/test_ask.py`: cover ask session metadata and provider input.
- Create `tests/test_evidence.py`: cover deterministic scoring, ordering, and metadata.
- Modify `README.md`: document prompt evidence behavior.

## Task 1: Evidence Selection Module

**Files:**
- Create: `src/kb_agent/evidence.py`
- Create: `tests/test_evidence.py`

- [ ] **Step 1: Write failing tests**

Add tests proving:

```python
from kb_agent.evidence import select_prompt_evidence


def test_select_prompt_evidence_prioritizes_phrase_and_excerpt_matches():
    evidence = [
        {"type": "source", "ref": "kb://source/generic", "why_relevant": "fallback source evidence", "excerpt": "Generic PCIe overview"},
        {"type": "source_chunk", "ref": "kb://source/pci#chunk=bar", "why_relevant": "chunk text matched question terms", "excerpt": "PCIe BAR assignment programs Base Address Registers for memory windows."},
    ]

    selected, metadata = select_prompt_evidence("Explain PCIe BAR assignment", evidence, budget=1)

    assert selected[0]["ref"] == "kb://source/pci#chunk=bar"
    assert selected[0]["score"] > 0
    assert metadata == {
        "method": "deterministic_token_phrase_v1",
        "budget": 1,
        "candidate_count": 2,
        "selected_count": 1,
        "omitted_count": 1,
    }
```

Also test stable ordering when two items have equal score.

- [ ] **Step 2: Verify RED**

Run:

```bash
uv run --extra dev pytest tests/test_evidence.py -q
```

Expected: import failure for missing `kb_agent.evidence`.

- [ ] **Step 3: Implement selector**

Implement:

```python
DEFAULT_PROMPT_EVIDENCE_BUDGET = 32
EVIDENCE_SELECTION_METHOD = "deterministic_token_phrase_v1"

def select_prompt_evidence(question: str, evidence: list[dict[str, str]], budget: int = DEFAULT_PROMPT_EVIDENCE_BUDGET) -> tuple[list[dict[str, object]], dict[str, object]]:
    ...
```

Rules:

- score token overlap across `ref`, `citation`, `why_relevant`, `excerpt`;
- add phrase bonus for adjacent question token pairs;
- add excerpt bonus when overlap appears in `excerpt`;
- add type bonus: accepted_claim 5, accepted_note 4, source_chunk 3,
  attachment 2, source 1;
- sort by `(-score, original_index)`;
- copy selected items and add integer `score`;
- return metadata with method, budget, candidate_count, selected_count,
  omitted_count.

- [ ] **Step 4: Verify GREEN**

Run:

```bash
uv run --extra dev pytest tests/test_evidence.py -q
```

Expected: pass.

## Task 2: Ask Workflow Integration

**Files:**
- Modify: `src/kb_agent/ask.py`
- Modify: `tests/test_ask.py`

- [ ] **Step 1: Write failing ask integration tests**

Add tests proving:

- fake LLM provider receives selected BAR evidence, not full evidence;
- `evidence_pack.json` contains `prompt_evidence` and `evidence_selection`;
- deterministic ask still writes the new metadata for audit.

- [ ] **Step 2: Verify RED**

Run:

```bash
uv run --extra dev pytest tests/test_ask.py -q
```

Expected: failure because `prompt_evidence` is not written and provider still
receives the full evidence list.

- [ ] **Step 3: Wire selector into `run_ask()`**

After `retrieve_evidence()`:

```python
prompt_evidence, evidence_selection = select_prompt_evidence(question, evidence)
```

For LLM mode, pass `prompt_evidence` to the provider. For deterministic mode,
render with the full `evidence` to preserve existing behavior. Persist both
`prompt_evidence` and `evidence_selection`.

- [ ] **Step 4: Verify GREEN**

Run:

```bash
uv run --extra dev pytest tests/test_ask.py tests/test_evidence.py -q
```

Expected: pass.

## Task 3: Docs and Verification

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update README**

Document that `kb ask --llm` uses a bounded `prompt_evidence` slice while the
complete retrieved `evidence` list remains in the session for audit.

- [ ] **Step 2: Run full verification**

Run:

```bash
uv run --extra dev pytest -q
```

Expected: all tests pass without a live LLM call.

- [ ] **Step 3: Commit**

Run:

```bash
git add README.md src/kb_agent/evidence.py src/kb_agent/ask.py tests/test_evidence.py tests/test_ask.py docs/superpowers/specs/2026-05-28-kb-agent-phase-5-2-evidence-rerank-design.md docs/superpowers/plans/2026-05-28-kb-agent-phase-5-2-evidence-rerank.md
git commit -m "feat: rerank ask evidence for LLM prompts"
```

