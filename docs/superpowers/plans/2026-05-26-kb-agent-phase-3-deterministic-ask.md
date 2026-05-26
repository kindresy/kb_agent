# KB Agent Phase 3 Deterministic Ask Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement deterministic `kb ask` session capture and `kb learn --from-session`.

**Architecture:** Add `ask.py` for question/session/evidence/answer generation, extend `learn.py` for session-origin staged runs, and expose both through Typer. Keep retrieval deterministic using token overlap across claims, notes, sources, chunks, and attachments.

**Tech Stack:** Python 3.11+, Typer, pytest, dataclasses, pathlib, json/jsonl.

---

## Tasks

### Task 1: Ask Session Core

**Files:**
- Create: `src/kb_agent/ask.py`
- Create: `tests/test_ask.py`
- Modify: `src/kb_agent/cli.py`

- [ ] Write failing test that `kb ask "What is Configuration Space?"` prints `# Answer`, includes `kb://source/manual`, and writes `question.md`, `evidence_pack.json`, `answer.md`, and `feedback_plan.md` under `sessions/questions/<session_id>/`.
- [ ] Run the test and confirm it fails because `ask` is not defined.
- [ ] Implement session id creation, intent classification, source fallback evidence, answer rendering, session file writing, and CLI command.
- [ ] Run `uv run --extra dev pytest tests/test_ask.py -v`.
- [ ] Commit `feat: add deterministic ask sessions`.

### Task 2: Attachments and Debug Sessions

**Files:**
- Modify: `src/kb_agent/ask.py`
- Modify: `tests/test_ask.py`

- [ ] Write failing test that `kb ask --with boot.log "Why was BAR0 not assigned?"` copies the attachment, records metadata, and saves under `sessions/debug_cases/<session_id>/`.
- [ ] Write failing test that missing attachment paths fail before any new session directory is written.
- [ ] Run the tests and confirm they fail for missing attachment behavior.
- [ ] Implement attachment validation, copy, metadata, and debug path selection.
- [ ] Run `uv run --extra dev pytest tests/test_ask.py -v`.
- [ ] Commit `feat: capture ask attachments`.

### Task 3: Evidence Retrieval From Notes, Claims, and Chunks

**Files:**
- Modify: `src/kb_agent/ask.py`
- Modify: `tests/test_ask.py`

- [ ] Write failing test that accepted claims and notes appear in `evidence_pack.json` when their tokens match the question.
- [ ] Run the test and confirm it fails because only source fallback is retrieved.
- [ ] Implement token overlap retrieval for `.kb/claims/*.jsonl`, `.kb/chunks/*.jsonl`, `notes/**/*.md`, and source records.
- [ ] Run `uv run --extra dev pytest tests/test_ask.py -v`.
- [ ] Commit `feat: retrieve deterministic ask evidence`.

### Task 4: Learn From Session

**Files:**
- Modify: `src/kb_agent/learn.py`
- Modify: `src/kb_agent/cli.py`
- Create: `tests/test_learn_from_session.py`

- [ ] Write failing test that `kb learn --from-session sessions/questions/<id>` creates a staged run whose snapshot contains `from_session` and whose pending note cites session evidence.
- [ ] Run the test and confirm it fails because `--from-session` is not defined.
- [ ] Extend `run_learn` with `from_session`, generate session profile/topic/chunk/claim/note/report, and update CLI option.
- [ ] Run `uv run --extra dev pytest tests/test_learn_from_session.py tests/test_learn.py -v`.
- [ ] Commit `feat: learn from ask sessions`.

### Task 5: Docs, Demo, Verification, Push

**Files:**
- Modify: `README.md`
- Create: `examples/phase3_demo.sh`

- [ ] Add README usage for `kb ask`, `kb ask --with`, and `kb learn --from-session`.
- [ ] Add demo that initializes a KB, learns/accepts a note, asks a cited question with an attachment, learns from the saved session, accepts it, compiles, and runs health.
- [ ] Run `uv run --extra dev pytest -v`.
- [ ] Run `KB_BIN="$PWD/.venv/bin/kb" bash examples/phase3_demo.sh`.
- [ ] Commit `docs: add phase 3 ask demo`.
- [ ] Push `phase-3`.

## Self-Review

This plan covers deterministic ask, evidence packs, attachments, session capture, feedback plan, and learn-from-session. It intentionally excludes LLM inference, OCR, vector search, and direct accepted-note modification.
