# KB Agent Phase 5.3 LLM Session Review Notes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Improve `kb learn --from-session` pending notes for LLM ask sessions while preserving the human review gate.

**Architecture:** Keep `run_learn_from_session()` deterministic. Add a session-specific pending note writer that uses `evidence_pack.json`, `question.md`, and `answer.md` to create a richer review note for LLM sessions only.

**Tech Stack:** Python 3.11+, pytest.

---

## File Structure

- Modify `src/kb_agent/learn.py`: add LLM session review note rendering and call it from `run_learn_from_session()`.
- Modify `tests/test_learn_from_session.py`: assert LLM session pending note quality.
- Modify `README.md`: document LLM session review-note behavior.

## Task 1: LLM Session Pending Note

**Files:**
- Modify: `src/kb_agent/learn.py`
- Modify: `tests/test_learn_from_session.py`

- [ ] **Step 1: Write failing test**

Add a test that creates a fake LLM ask session, runs `kb learn --from-session`,
and asserts the generated pending note contains:

- `## Unverified LLM Answer Excerpt`
- the LLM answer text;
- `Confidence: llm_session_unverified`;
- a prompt evidence ref;
- a prompt evidence score;
- `Required Human Checks`.

- [ ] **Step 2: Verify RED**

Run:

```bash
uv run --extra dev pytest tests/test_learn_from_session.py -q
```

Expected: failure because LLM pending notes are still generic.

- [ ] **Step 3: Implement review note rendering**

Add helper functions:

```python
def markdown_excerpt(text: str, limit: int = 2000) -> str:
    ...

def write_llm_session_pending_note(...):
    ...
```

For LLM sessions, write one note under `reviews/pending_notes/<run_id>/` using
the session topic id. Include original question, answer excerpt,
`prompt_evidence`, required checks, and citations.

- [ ] **Step 4: Verify GREEN**

Run:

```bash
uv run --extra dev pytest tests/test_learn_from_session.py -q
```

Expected: pass.

## Task 2: Docs and Verification

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update README**

Document that `kb learn --from-session` creates richer review notes for LLM ask
sessions and labels them unverified until accepted.

- [ ] **Step 2: Run full verification**

Run:

```bash
uv run --extra dev pytest -q
```

Expected: all tests pass without live LLM calls.

- [ ] **Step 3: Commit**

Run:

```bash
git add README.md src/kb_agent/learn.py tests/test_learn_from_session.py docs/superpowers/specs/2026-05-28-kb-agent-phase-5-3-llm-session-review-design.md docs/superpowers/plans/2026-05-28-kb-agent-phase-5-3-llm-session-review.md
git commit -m "feat: improve LLM session review notes"
```

