# KB Agent Phase 1.2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `kb ingest` handle real Markdown export asset layouts and avoid duplicate re-ingest.

**Architecture:** Extend package detection beyond `<stem>.assets/` to include `<stem>-assets/`, `<stem>_assets/`, and relative directories referenced by Markdown links such as `parts/` and `images/`. Add hash-based duplicate skipping so repeated `kb ingest inbox` does not append duplicate `_2` records.

**Tech Stack:** Python 3.11+, Typer, pytest, pathlib, shutil.

---

## Tasks

### Task 1: Asset Layout Detection

**Files:**
- Modify: `src/kb_agent/sources.py`
- Modify: `tests/test_ingest.py`

- [x] Add failing tests for `<stem>-assets/` packages.
- [x] Add failing tests for Markdown files referencing `parts/.../images/...`.
- [x] Implement package detection for sibling asset directories and referenced relative directories.

### Task 2: Duplicate Skipping

**Files:**
- Modify: `src/kb_agent/sources.py`
- Modify: `tests/test_ingest.py`

- [x] Add failing test for running `kb ingest` twice on the same file.
- [x] Add failing test for running `kb ingest` twice on the same Markdown package.
- [x] Implement hash-based duplicate skip.

### Task 3: Verify Realistic Ingest Shape

**Files:**
- Modify: `examples/phase1_demo.sh`
- Modify: `README.md`

- [x] Update docs to mention `.assets`, `-assets`, and `parts/images` package layouts.
- [x] Run targeted and full tests.
- [x] Push to the existing PR branch.

## Self-Review

Coverage:
- Handles common Markdown export directories: `.assets`, `-assets`, `_assets`, `parts`, and `images`.
- Prevents repeated ingest from duplicating already-indexed content by hash.

Intentional exclusions:
- No semantic content analysis.
- No Markdown rewriting.
- No automatic repair of broken third-party export paths.
