# KB Agent Phase 1.1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `kb ingest` preserve Markdown files and their adjacent assets directories as one source package.

**Architecture:** Extend `SourceRecord` with package metadata while keeping old file records compatible. Detect Markdown packages during ingest, copy the main Markdown file plus its `<stem>.assets/` directory into `sources/manuals/<source_id>/`, and teach `kb compile --fast` to validate package files, listed assets, and package-local Markdown links.

**Tech Stack:** Python 3.11+, Typer, pytest, pathlib, shutil, dataclasses.

---

## Tasks

### Task 1: Package-Aware Ingest

**Files:**
- Modify: `src/kb_agent/sources.py`
- Modify: `tests/test_ingest.py`

- [ ] Write tests for ingesting `pcie_book.md` with `pcie_book.assets/`.
- [ ] Verify tests fail because current ingest splits assets into separate image records.
- [ ] Extend `SourceRecord` with `kind`, `package_path`, and `assets`.
- [ ] Detect Markdown packages and copy them under `sources/manuals/<source_id>/`.
- [ ] Skip package asset files as standalone records during directory ingest.
- [ ] Verify targeted ingest tests pass.

### Task 2: Package Compile Checks

**Files:**
- Modify: `src/kb_agent/compile.py`
- Modify: `tests/test_compile.py`

- [ ] Write tests for missing package asset and package Markdown link escaping the package.
- [ ] Verify tests fail.
- [ ] Add package validation to `compile_fast`.
- [ ] Verify package tests and full suite pass.

### Task 3: Demo and Docs

**Files:**
- Modify: `examples/phase1_demo.sh`
- Modify: `README.md`

- [ ] Update demo to include a Markdown package with an assets directory.
- [ ] Run demo with the local `kb` binary.
- [ ] Commit and push.

## Self-Review

Coverage:
- Markdown + adjacent assets directory package ingest is covered.
- Directory ingest skipping packaged asset files is covered.
- Compile checks for package assets and package-local links are covered.

Intentional exclusions:
- No AI content analysis.
- No OCR.
- No automatic Markdown rewrite.
- No PDF package handling.
