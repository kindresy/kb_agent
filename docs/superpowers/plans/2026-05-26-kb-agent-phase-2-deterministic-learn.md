# KB Agent Phase 2 Deterministic Learn Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a local deterministic `kb learn` and `kb accept` pipeline that stages cited learning notes before promotion.

**Architecture:** Add focused modules for learn runs, deterministic profiling/topic/chunk/claim generation, pending note/report writing, and accept promotion. Extend `compile_fast` to validate persisted claim citations. Keep all Phase 2 generation deterministic and file-based so tests can assert exact behavior.

**Tech Stack:** Python 3.11+, Typer, pytest, dataclasses, pathlib, json/jsonl.

---

## File Structure

- Create `src/kb_agent/jsonl.py`: shared JSONL read/write/append helpers.
- Create `src/kb_agent/learn.py`: learn run models, source selection, profiling, topic extraction, chunk and claim drafting, pending note/report writing.
- Create `src/kb_agent/accept.py`: accept gate and promotion logic.
- Modify `src/kb_agent/cli.py`: add `learn` and `accept` commands.
- Modify `src/kb_agent/compile.py`: validate `.kb/claims/*.jsonl`.
- Create `tests/test_learn.py`: learn command and deterministic artifact tests.
- Create `tests/test_accept.py`: accept success/failure tests.
- Modify `tests/test_compile.py`: claim validation tests.
- Modify `README.md`: Phase 2 usage.

## Task 1: JSONL Helpers and Learn Run Snapshot

**Files:**
- Create: `src/kb_agent/jsonl.py`
- Create: `src/kb_agent/learn.py`
- Create: `tests/test_learn.py`
- Modify: `src/kb_agent/cli.py`

- [ ] **Step 1: Write failing tests for `kb learn` snapshot**

Create `tests/test_learn.py`:

```python
import json
from pathlib import Path

from tests.conftest import run_cli


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def test_learn_creates_run_snapshot_for_all_sources(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert run_cli("init", "pcie").exit_code == 0
    source = tmp_path / "manual.md"
    source.write_text("# Configuration Space\nBAR notes\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path / "pcie")
    assert run_cli("ingest", str(source)).exit_code == 0

    result = run_cli("learn", "--goal", "Build config notes")

    assert result.exit_code == 0
    assert "Learn run:" in result.output
    run_id = result.output.split("Learn run:", 1)[1].splitlines()[0].strip()
    run_root = tmp_path / "pcie" / ".kb" / "learn_runs" / run_id
    snapshot = json.loads((run_root / "snapshot.json").read_text())
    assert snapshot["run_id"] == run_id
    assert snapshot["goal"] == "Build config notes"
    assert snapshot["selected_source_ids"] == ["manual"]
    assert snapshot["skipped_sources"] == []
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
uv run --extra dev pytest tests/test_learn.py::test_learn_creates_run_snapshot_for_all_sources -v
```

Expected: FAIL because `learn` command is not defined.

- [ ] **Step 3: Implement JSONL helpers**

Create `src/kb_agent/jsonl.py`:

```python
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def append_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as file:
        for row in rows:
            file.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
```

- [ ] **Step 4: Implement minimal learn run snapshot**

Create `src/kb_agent/learn.py` with:

```python
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

from kb_agent.sources import SourceRecord, load_source_index


@dataclass(frozen=True)
class LearnRun:
    run_id: str
    goal: str | None
    selected_sources: list[SourceRecord]
    skipped_sources: list[dict[str, str]]


def new_run_id(now: datetime | None = None) -> str:
    timestamp = now or datetime.now()
    return timestamp.strftime("learn_%Y%m%d_%H%M%S")


def select_sources(root: Path, source_ids: list[str] | None) -> tuple[list[SourceRecord], list[dict[str, str]]]:
    records = load_source_index(root)
    if source_ids is None:
        return records, []

    by_id = {record.source_id: record for record in records}
    unknown = [source_id for source_id in source_ids if source_id not in by_id]
    if unknown:
        raise ValueError(f"unknown source id(s): {', '.join(unknown)}")
    selected = [by_id[source_id] for source_id in source_ids]
    selected_ids = set(source_ids)
    skipped = [
        {"source_id": record.source_id, "reason": "not selected"}
        for record in records
        if record.source_id not in selected_ids
    ]
    return selected, skipped


def write_snapshot(root: Path, run: LearnRun) -> None:
    run_root = root / ".kb" / "learn_runs" / run.run_id
    run_root.mkdir(parents=True, exist_ok=True)
    snapshot = {
        "run_id": run.run_id,
        "goal": run.goal,
        "selected_source_ids": [record.source_id for record in run.selected_sources],
        "selected_sources": [asdict(record) for record in run.selected_sources],
        "skipped_sources": run.skipped_sources,
    }
    (run_root / "snapshot.json").write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def run_learn(root: Path, goal: str | None = None, source_ids: list[str] | None = None) -> LearnRun:
    selected, skipped = select_sources(root, source_ids)
    run = LearnRun(new_run_id(), goal, selected, skipped)
    write_snapshot(root, run)
    return run
```

Modify `src/kb_agent/cli.py`:

```python
from kb_agent.learn import run_learn


@app.command()
def learn(
    goal: str | None = typer.Option(None, "--goal", help="Learning goal for this run."),
    sources: str | None = typer.Option(None, "--sources", help="Comma-separated source ids."),
) -> None:
    """Run deterministic staged learning."""
    try:
        root = find_kb_root(Path.cwd())
        source_ids = [item.strip() for item in sources.split(",") if item.strip()] if sources else None
        run = run_learn(root, goal=goal, source_ids=source_ids)
    except (FileNotFoundError, ValueError) as exc:
        typer.echo(str(exc))
        raise typer.Exit(code=1)

    typer.echo(f"Learn run: {run.run_id}")
    typer.echo(f"Selected sources: {len(run.selected_sources)}")
```

- [ ] **Step 5: Verify snapshot test passes**

Run:

```bash
uv run --extra dev pytest tests/test_learn.py::test_learn_creates_run_snapshot_for_all_sources -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/kb_agent/jsonl.py src/kb_agent/learn.py src/kb_agent/cli.py tests/test_learn.py
git commit -m "feat: add deterministic learn snapshot"
```

## Task 2: Source Profiles and Topic Extraction

**Files:**
- Modify: `src/kb_agent/learn.py`
- Modify: `tests/test_learn.py`

- [ ] **Step 1: Add failing tests for profiles and topics**

Append to `tests/test_learn.py`:

```python
def test_learn_profiles_markdown_headings_and_topics(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert run_cli("init", "pcie").exit_code == 0
    source = tmp_path / "manual.md"
    source.write_text("# Configuration Space\n\n## BAR Assignment\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path / "pcie")
    assert run_cli("ingest", str(source)).exit_code == 0

    result = run_cli("learn")

    assert result.exit_code == 0
    run_id = result.output.split("Learn run:", 1)[1].splitlines()[0].strip()
    run_root = tmp_path / "pcie" / ".kb" / "learn_runs" / run_id
    profiles = read_jsonl(run_root / "profiles.jsonl")
    topics = read_jsonl(run_root / "topics.jsonl")
    assert profiles[0]["headings"] == ["Configuration Space", "BAR Assignment"]
    assert [topic["topic_id"] for topic in topics] == [
        "topic.configuration_space",
        "topic.bar_assignment",
    ]
    assert all(topic["citations"] == ["kb://source/manual"] for topic in topics)


def test_learn_rejects_unknown_source_filter(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert run_cli("init", "pcie").exit_code == 0
    monkeypatch.chdir(tmp_path / "pcie")

    result = run_cli("learn", "--sources", "missing")

    assert result.exit_code == 1
    assert "unknown source id(s): missing" in result.output
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
uv run --extra dev pytest tests/test_learn.py::test_learn_profiles_markdown_headings_and_topics tests/test_learn.py::test_learn_rejects_unknown_source_filter -v
```

Expected: heading/topic test FAILS because profile/topic files are missing.

- [ ] **Step 3: Implement profiling and topic extraction**

Add to `src/kb_agent/learn.py`:

```python
import re
from kb_agent.jsonl import write_jsonl


def slug(value: str) -> str:
    result = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return result or "topic"


def source_content_path(root: Path, record: SourceRecord) -> Path:
    return root / record.path


def extract_markdown_headings(path: Path) -> list[str]:
    if not path.is_file() or path.suffix.lower() not in {".md", ".markdown"}:
        return []
    headings: list[str] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        match = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
        if match:
            headings.append(match.group(2).strip())
    return headings


def extract_code_symbols(path: Path) -> list[str]:
    if not path.is_file() or path.suffix.lower() not in {".c", ".h", ".py", ".rs", ".go"}:
        return []
    symbols: list[str] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        stripped = line.strip()
        match = re.match(r"#\s*define\s+([A-Za-z_][A-Za-z0-9_]*)", stripped)
        if match:
            symbols.append(match.group(1))
            continue
        match = re.match(r"(?:struct|class)\s+([A-Za-z_][A-Za-z0-9_]*)", stripped)
        if match:
            symbols.append(match.group(1))
            continue
        match = re.match(r"(?:[A-Za-z_][A-Za-z0-9_*\s]+)\s+([A-Za-z_][A-Za-z0-9_]*)\s*\([^;]*\)\s*\{?", stripped)
        if match:
            symbols.append(match.group(1))
    return symbols


def authority_for(record: SourceRecord) -> str:
    if record.type == "spec":
        return "primary"
    if record.type == "code":
        return "implementation"
    if record.type == "log":
        return "debug"
    if record.type in {"manual", "webpage"}:
        return "explanatory"
    return "secondary"


def build_profiles(root: Path, sources: list[SourceRecord]) -> list[dict[str, object]]:
    profiles = []
    for record in sources:
        path = source_content_path(root, record)
        headings = extract_markdown_headings(path)
        symbols = extract_code_symbols(path)
        candidates = headings or symbols or [record.title]
        profiles.append(
            {
                "source_id": record.source_id,
                "type": record.type,
                "title": record.title,
                "path": record.path,
                "kind": record.kind,
                "authority": authority_for(record),
                "headings": headings,
                "symbols": symbols,
                "candidate_topics": candidates,
            }
        )
    return profiles


def build_topics(profiles: list[dict[str, object]]) -> list[dict[str, object]]:
    topics: list[dict[str, object]] = []
    used: set[str] = set()
    for profile in profiles:
        for candidate in profile["candidate_topics"]:
            base_id = f"topic.{slug(str(candidate))}"
            topic_id = base_id
            counter = 2
            while topic_id in used:
                topic_id = f"{base_id}_{counter}"
                counter += 1
            used.add(topic_id)
            topics.append(
                {
                    "topic_id": topic_id,
                    "name": str(candidate),
                    "source_id": profile["source_id"],
                    "source_path": profile["path"],
                    "basis": "profile",
                    "priority": "normal",
                    "citations": [f"kb://source/{profile['source_id']}"],
                }
            )
    return topics
```

Update `run_learn` to write `profiles.jsonl` and `topics.jsonl`.

- [ ] **Step 4: Verify profile/topic tests pass**

Run:

```bash
uv run --extra dev pytest tests/test_learn.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/kb_agent/learn.py tests/test_learn.py
git commit -m "feat: extract deterministic learn topics"
```

## Task 3: Evidence Chunks, Claims, Pending Notes, and Reports

**Files:**
- Modify: `src/kb_agent/learn.py`
- Modify: `tests/test_learn.py`

- [ ] **Step 1: Add failing test for staged artifacts**

Append to `tests/test_learn.py`:

```python
def test_learn_writes_chunks_claims_pending_notes_and_report(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert run_cli("init", "pcie").exit_code == 0
    source = tmp_path / "manual.md"
    source.write_text("# Configuration Space\nBAR notes\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path / "pcie")
    assert run_cli("ingest", str(source)).exit_code == 0

    result = run_cli("learn", "--goal", "Build config notes")

    assert result.exit_code == 0
    run_id = result.output.split("Learn run:", 1)[1].splitlines()[0].strip()
    root = tmp_path / "pcie"
    run_root = root / ".kb" / "learn_runs" / run_id
    chunks = read_jsonl(run_root / "chunks.jsonl")
    claims = read_jsonl(run_root / "claims.jsonl")
    assert chunks[0]["citation"].startswith("kb://source/manual#chunk=")
    assert claims[0]["citations"] == [chunks[0]["citation"]]
    pending_note = root / "reviews" / "pending_notes" / run_id / "topic.configuration_space.md"
    assert "kb://source/manual#chunk=" in pending_note.read_text()
    report = root / "reports" / "learn" / run_id / "learn_report.md"
    report_text = report.read_text()
    assert "# Learn Report" in report_text
    assert "Build config notes" in report_text
```

- [ ] **Step 2: Run test to verify failure**

Run:

```bash
uv run --extra dev pytest tests/test_learn.py::test_learn_writes_chunks_claims_pending_notes_and_report -v
```

Expected: FAIL because chunks, claims, notes, and report are missing.

- [ ] **Step 3: Implement chunks, claims, notes, and report**

Add deterministic builders to `src/kb_agent/learn.py`:

```python
import hashlib


def stable_hash(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def build_chunks(root: Path, topics: list[dict[str, object]]) -> list[dict[str, object]]:
    chunks = []
    for index, topic in enumerate(topics, start=1):
        source_path = root / str(topic["source_path"])
        text = ""
        if source_path.is_file() and source_path.suffix.lower() in {".md", ".markdown", ".txt", ".log", ".c", ".h", ".py", ".rs", ".go"}:
            text = source_path.read_text(encoding="utf-8", errors="replace")[:1000]
        if not text:
            text = f"File-level evidence for {topic['name']} from {topic['source_id']}."
        chunk_id = f"chunk.{topic['topic_id'].removeprefix('topic.')}.{index}"
        chunks.append(
            {
                "chunk_id": chunk_id,
                "source_id": topic["source_id"],
                "source_path": topic["source_path"],
                "topic_id": topic["topic_id"],
                "kind": "deterministic_excerpt",
                "text": text,
                "hash": stable_hash(text),
                "citation": f"kb://source/{topic['source_id']}#chunk={chunk_id}",
            }
        )
    return chunks


def build_claims(topics: list[dict[str, object]], chunks: list[dict[str, object]]) -> list[dict[str, object]]:
    chunk_by_topic = {chunk["topic_id"]: chunk for chunk in chunks}
    claims = []
    for index, topic in enumerate(topics, start=1):
        chunk = chunk_by_topic[topic["topic_id"]]
        claims.append(
            {
                "claim_id": f"claim.{topic['topic_id'].removeprefix('topic.')}.{index}",
                "topic_id": topic["topic_id"],
                "type": "source_observation",
                "claim": f"The source introduces {topic['name']}.",
                "citations": [chunk["citation"]],
                "confidence": "deterministic",
            }
        )
    return claims


def write_pending_notes(root: Path, run_id: str, topics: list[dict[str, object]], claims: list[dict[str, object]]) -> list[str]:
    pending_root = root / "reviews" / "pending_notes" / run_id
    pending_root.mkdir(parents=True, exist_ok=True)
    claims_by_topic = {claim["topic_id"]: claim for claim in claims}
    paths = []
    for topic in topics:
        claim = claims_by_topic[topic["topic_id"]]
        path = pending_root / f"{topic['topic_id']}.md"
        path.write_text(
            "\n".join(
                [
                    f"# {topic['name']}",
                    "",
                    "## One-Sentence Conclusion",
                    "",
                    str(claim["claim"]),
                    "",
                    "## What Was Found",
                    "",
                    f"`kb learn` identified this topic from `{topic['source_id']}`.",
                    "",
                    "## Evidence",
                    "",
                    f"- {claim['citations'][0]}",
                    "",
                    "## Open Questions",
                    "",
                    "- Needs human review before becoming authoritative.",
                    "",
                    "## Related Sources",
                    "",
                    f"- kb://source/{topic['source_id']}",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        paths.append(path.relative_to(root).as_posix())
    return paths


def write_learn_report(root: Path, run: LearnRun, profiles: list[dict[str, object]], topics: list[dict[str, object]], chunks: list[dict[str, object]], claims: list[dict[str, object]], pending_notes: list[str]) -> None:
    report_path = root / "reports" / "learn" / run.run_id / "learn_report.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        "\n".join(
            [
                "# Learn Report",
                "",
                f"Run: `{run.run_id}`",
                f"Goal: {run.goal or 'not specified'}",
                "",
                "## Selected Sources",
                *[f"- {record.source_id}: {record.path}" for record in run.selected_sources],
                "",
                "## Generated Artifacts",
                "",
                f"- Profiles: {len(profiles)}",
                f"- Topics: {len(topics)}",
                f"- Chunks: {len(chunks)}",
                f"- Claims: {len(claims)}",
                f"- Pending notes: {len(pending_notes)}",
                "",
                "## Pending Notes",
                *[f"- {path}" for path in pending_notes],
                "",
                "## Next Suggested Command",
                "",
                f"`kb accept {run.run_id}`",
                "",
            ]
        ),
        encoding="utf-8",
    )
```

Update `run_learn` to write chunks, claims, pending notes, and report.

- [ ] **Step 4: Verify staged artifact tests pass**

Run:

```bash
uv run --extra dev pytest tests/test_learn.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/kb_agent/learn.py tests/test_learn.py
git commit -m "feat: write deterministic learn artifacts"
```

## Task 4: Claim Compile Checks

**Files:**
- Modify: `src/kb_agent/compile.py`
- Modify: `tests/test_compile.py`

- [ ] **Step 1: Add failing compile tests for claims**

Append to `tests/test_compile.py`:

```python
def test_compile_fast_fails_claim_without_citation(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert run_cli("init", "pcie").exit_code == 0
    root = tmp_path / "pcie"
    claim_path = root / ".kb" / "claims" / "claims.jsonl"
    claim_path.write_text(
        '{"claim_id":"claim.one","topic_id":"topic.one","claim":"uncited","citations":[]}\n',
        encoding="utf-8",
    )
    monkeypatch.chdir(root)

    result = run_cli("compile", "--fast")

    assert result.exit_code == 1
    assert "claim_missing_citation" in result.output


def test_compile_fast_fails_claim_with_unknown_source_citation(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert run_cli("init", "pcie").exit_code == 0
    root = tmp_path / "pcie"
    claim_path = root / ".kb" / "claims" / "claims.jsonl"
    claim_path.write_text(
        '{"claim_id":"claim.one","topic_id":"topic.one","claim":"bad","citations":["kb://source/missing"]}\n',
        encoding="utf-8",
    )
    monkeypatch.chdir(root)

    result = run_cli("compile", "--fast")

    assert result.exit_code == 1
    assert "claim_missing_source_reference" in result.output
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
uv run --extra dev pytest tests/test_compile.py::test_compile_fast_fails_claim_without_citation tests/test_compile.py::test_compile_fast_fails_claim_with_unknown_source_citation -v
```

Expected: FAIL because claim validation is not implemented.

- [ ] **Step 3: Implement claim checks**

Modify `src/kb_agent/compile.py`:

```python
from kb_agent.jsonl import read_jsonl


def check_claims(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    source_ids = {record.source_id for record in load_source_index(root)}
    claims_root = root / ".kb" / "claims"
    if not claims_root.is_dir():
        return findings

    for path in sorted(claims_root.rglob("*.jsonl")):
        relative_path = path.relative_to(root).as_posix()
        for claim in read_jsonl(path):
            claim_id = str(claim.get("claim_id", "<missing>"))
            citations = claim.get("citations") or []
            if not citations:
                findings.append(
                    Finding(
                        "error",
                        "claim_missing_citation",
                        relative_path,
                        f"claim has no citation: {claim_id}",
                    )
                )
                continue
            for citation in citations:
                for source_id in extract_kb_source_refs(str(citation)):
                    if source_id not in source_ids:
                        findings.append(
                            Finding(
                                "error",
                                "claim_missing_source_reference",
                                relative_path,
                                f"claim references missing source: {source_id}",
                            )
                        )
    return findings
```

Add `*check_claims(root)` to `compile_fast`.

- [ ] **Step 4: Verify claim compile tests pass**

Run:

```bash
uv run --extra dev pytest tests/test_compile.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/kb_agent/compile.py tests/test_compile.py
git commit -m "feat: validate claim citations"
```

## Task 5: Accept Promotion

**Files:**
- Create: `src/kb_agent/accept.py`
- Create: `tests/test_accept.py`
- Modify: `src/kb_agent/cli.py`

- [ ] **Step 1: Add failing accept tests**

Create `tests/test_accept.py`:

```python
import json
from pathlib import Path

from tests.conftest import run_cli


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def test_accept_promotes_pending_notes_and_indexes(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert run_cli("init", "pcie").exit_code == 0
    source = tmp_path / "manual.md"
    source.write_text("# Configuration Space\nBAR notes\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path / "pcie")
    assert run_cli("ingest", str(source)).exit_code == 0
    learn = run_cli("learn")
    run_id = learn.output.split("Learn run:", 1)[1].splitlines()[0].strip()

    result = run_cli("accept", run_id)

    assert result.exit_code == 0
    assert "Accepted learn run" in result.output
    accepted_note = tmp_path / "pcie" / "notes" / "concepts" / "generated" / "topic.configuration_space.md"
    assert accepted_note.is_file()
    assert read_jsonl(tmp_path / "pcie" / ".kb" / "topics" / "topics.jsonl")
    assert read_jsonl(tmp_path / "pcie" / ".kb" / "chunks" / "chunks.jsonl")
    assert read_jsonl(tmp_path / "pcie" / ".kb" / "claims" / "claims.jsonl")


def test_accept_refuses_uncited_claim_without_partial_promotion(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert run_cli("init", "pcie").exit_code == 0
    source = tmp_path / "manual.md"
    source.write_text("# Configuration Space\nBAR notes\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path / "pcie")
    assert run_cli("ingest", str(source)).exit_code == 0
    learn = run_cli("learn")
    run_id = learn.output.split("Learn run:", 1)[1].splitlines()[0].strip()
    claims_path = tmp_path / "pcie" / ".kb" / "learn_runs" / run_id / "claims.jsonl"
    claims = read_jsonl(claims_path)
    claims[0]["citations"] = []
    claims_path.write_text(
        "\n".join(json.dumps(claim, sort_keys=True) for claim in claims) + "\n",
        encoding="utf-8",
    )

    result = run_cli("accept", run_id)

    assert result.exit_code == 1
    assert "claim has no citation" in result.output
    accepted_note = tmp_path / "pcie" / "notes" / "concepts" / "generated" / "topic.configuration_space.md"
    assert not accepted_note.exists()
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
uv run --extra dev pytest tests/test_accept.py -v
```

Expected: FAIL because `accept` command is not defined.

- [ ] **Step 3: Implement accept promotion**

Create `src/kb_agent/accept.py`:

```python
from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from kb_agent.compile import compile_fast
from kb_agent.jsonl import append_jsonl, read_jsonl
from kb_agent.markdown import extract_kb_source_refs
from kb_agent.sources import load_source_index


@dataclass(frozen=True)
class AcceptResult:
    run_id: str
    promoted_notes: list[str]


def validate_run_claims(root: Path, run_id: str) -> list[str]:
    errors: list[str] = []
    source_ids = {record.source_id for record in load_source_index(root)}
    claims_path = root / ".kb" / "learn_runs" / run_id / "claims.jsonl"
    for claim in read_jsonl(claims_path):
        claim_id = str(claim.get("claim_id", "<missing>"))
        citations = claim.get("citations") or []
        if not citations:
            errors.append(f"claim has no citation: {claim_id}")
            continue
        for citation in citations:
            refs = extract_kb_source_refs(str(citation))
            if not refs:
                errors.append(f"claim citation is not a kb source ref: {claim_id}")
            for source_id in refs:
                if source_id not in source_ids:
                    errors.append(f"claim references missing source: {source_id}")
    return errors


def accept_learn_run(root: Path, run_id: str) -> AcceptResult:
    run_root = root / ".kb" / "learn_runs" / run_id
    pending_root = root / "reviews" / "pending_notes" / run_id
    if not run_root.is_dir():
        raise FileNotFoundError(f"learn run not found: {run_id}")
    if not pending_root.is_dir():
        raise FileNotFoundError(f"pending notes not found for learn run: {run_id}")

    errors = validate_run_claims(root, run_id)
    if errors:
        raise ValueError("\n".join(errors))

    compile_result = compile_fast(root)
    if not compile_result.passed:
        messages = [f"{finding.code}: {finding.path}: {finding.message}" for finding in compile_result.findings]
        raise ValueError("compile gate failed before accept:\n" + "\n".join(messages))

    accepted_root = root / "notes" / "concepts" / "generated"
    accepted_root.mkdir(parents=True, exist_ok=True)
    promoted: list[str] = []
    for note in sorted(pending_root.glob("*.md")):
        destination = accepted_root / note.name
        shutil.copy2(note, destination)
        promoted.append(destination.relative_to(root).as_posix())

    append_jsonl(root / ".kb" / "topics" / "topics.jsonl", read_jsonl(run_root / "topics.jsonl"))
    append_jsonl(root / ".kb" / "chunks" / "chunks.jsonl", read_jsonl(run_root / "chunks.jsonl"))
    append_jsonl(root / ".kb" / "claims" / "claims.jsonl", read_jsonl(run_root / "claims.jsonl"))
    return AcceptResult(run_id, promoted)
```

Modify `src/kb_agent/cli.py`:

```python
from kb_agent.accept import accept_learn_run


@app.command()
def accept(run_id: str) -> None:
    """Accept a staged learn run."""
    try:
        root = find_kb_root(Path.cwd())
        result = accept_learn_run(root, run_id)
    except (FileNotFoundError, ValueError) as exc:
        typer.echo(str(exc))
        raise typer.Exit(code=1)

    typer.echo(f"Accepted learn run: {result.run_id}")
    typer.echo(f"Promoted notes: {len(result.promoted_notes)}")
    for note in result.promoted_notes:
        typer.echo(f"- {note}")
```

- [ ] **Step 4: Verify accept tests pass**

Run:

```bash
uv run --extra dev pytest tests/test_accept.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/kb_agent/accept.py src/kb_agent/cli.py tests/test_accept.py
git commit -m "feat: accept deterministic learn runs"
```

## Task 6: Docs, Demo, and Final Verification

**Files:**
- Modify: `README.md`
- Create: `examples/phase2_demo.sh`

- [ ] **Step 1: Update README**

Add a Phase 2 section:

```markdown
## Phase 2 deterministic learn

```bash
kb learn --goal "Build PCIe configuration notes"
kb accept <learn_run_id>
kb compile --fast
kb health
```

Phase 2 uses deterministic local rules. It stages generated notes under
`reviews/pending_notes/<run_id>/` and writes reports under
`reports/learn/<run_id>/`. Accepted notes are promoted only through
`kb accept <run_id>`.
```

- [ ] **Step 2: Add demo**

Create `examples/phase2_demo.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

KB_BIN="${KB_BIN:-kb}"
DEMO_ROOT="${DEMO_ROOT:-$(mktemp -d)}"

echo "Demo root: ${DEMO_ROOT}"
cd "${DEMO_ROOT}"

cat > pcie-config.md <<'MARKDOWN'
# Configuration Space

BAR assignment is part of PCIe enumeration.

## BAR Assignment

Firmware or the OS sizes and assigns BARs.
MARKDOWN

"${KB_BIN}" init pcie
cd pcie
"${KB_BIN}" ingest ../pcie-config.md
learn_output=$("${KB_BIN}" learn --goal "Build PCIe configuration notes")
echo "${learn_output}"
run_id=$(printf '%s\n' "${learn_output}" | awk -F': ' '/Learn run:/ {print $2}')
"${KB_BIN}" accept "${run_id}"
"${KB_BIN}" compile --fast
"${KB_BIN}" health
```

- [ ] **Step 3: Run full tests**

Run:

```bash
uv run --extra dev pytest -v
```

Expected: 0 failures.

- [ ] **Step 4: Run demo**

Run:

```bash
KB_BIN="$PWD/.venv/bin/kb" bash examples/phase2_demo.sh
```

Expected: learn, accept, compile, and health all succeed.

- [ ] **Step 5: Commit and push**

```bash
git add README.md examples/phase2_demo.sh
git commit -m "docs: add phase 2 deterministic learn demo"
git push origin phase-2
```

## Self-Review

Spec coverage:

- `kb learn` command is covered by Tasks 1-3.
- source profiling and topic extraction are covered by Task 2.
- evidence chunks, claim drafting, pending notes, and learn report are covered by Task 3.
- claim citation compile gate is covered by Task 4.
- manual accept/reject is covered by Task 5.
- docs and demo are covered by Task 6.

Intentional exclusions:

- No LLM or embedding calls.
- No PDF full-text extraction.
- No semantic conflict detector.
- No `kb ask`.
