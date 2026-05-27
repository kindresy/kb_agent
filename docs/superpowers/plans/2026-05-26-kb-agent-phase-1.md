# KB Agent Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Phase 1 local CLI skeleton for a file-based AI knowledge base: initialize a domain repo, ingest source files, maintain source metadata, run fast compile checks, and print a health report.

**Architecture:** Implement a Python package named `kb_agent` with a Typer CLI exposed as `kb`. Keep accepted knowledge as files and write rebuildable machine state under `.kb/`. Phase 1 intentionally avoids AI calls, embeddings, and semantic conflict detection; it establishes the file discipline and static checks needed by later phases.

**Tech Stack:** Python 3.11+, Typer, PyYAML, pytest, pathlib, hashlib, json, dataclasses.

---

## Scope

This plan implements Phase 1 from `specs/2026-05-26-file-ai-knowledge-base-design.md`:

- `kb init <domain>`
- `kb ingest [path]`
- `kb compile --fast`
- `kb health`
- source manifest
- basic `kb://source/...` citation checker
- basic Markdown link checker
- health report

It does not implement `kb learn`, `kb ask`, AI source profiling, embeddings, staged review, or semantic conflict detection. Those are Phase 2 and later.

## File Structure

Create these files:

```text
pyproject.toml
README.md
src/kb_agent/__init__.py
src/kb_agent/cli.py
src/kb_agent/config.py
src/kb_agent/layout.py
src/kb_agent/sources.py
src/kb_agent/compile.py
src/kb_agent/health.py
src/kb_agent/markdown.py
tests/conftest.py
tests/test_init.py
tests/test_ingest.py
tests/test_compile.py
tests/test_health.py
```

Responsibilities:

- `cli.py`: Typer command surface and console output.
- `config.py`: `kb.yaml` load/write and config defaults.
- `layout.py`: canonical domain directory creation and repository discovery.
- `sources.py`: source metadata, hashing, material type detection, ingest operations, JSONL index I/O.
- `markdown.py`: Markdown link and `kb://source/...` extraction.
- `compile.py`: fast compile checks and machine-readable findings.
- `health.py`: health summary and exit severity.
- `tests/`: CLI and library behavior tests using temporary directories.

## Task 1: Project Skeleton and CLI Entrypoint

**Files:**
- Create: `pyproject.toml`
- Create: `README.md`
- Create: `src/kb_agent/__init__.py`
- Create: `src/kb_agent/cli.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Write the failing CLI smoke test**

Create `tests/conftest.py`:

```python
from typer.testing import CliRunner

from kb_agent.cli import app


def run_cli(*args: str):
    runner = CliRunner()
    return runner.invoke(app, list(args))
```

Create the first test in `tests/test_init.py`:

```python
from tests.conftest import run_cli


def test_cli_version_command():
    result = run_cli("--version")

    assert result.exit_code == 0
    assert "kb-agent" in result.stdout
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/test_init.py::test_cli_version_command -v
```

Expected: FAIL because `kb_agent` package or `app` is not defined.

- [ ] **Step 3: Add package metadata and dependencies**

Create `pyproject.toml`:

```toml
[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "kb-agent"
version = "0.1.0"
description = "Local file-based AI knowledge base CLI"
readme = "README.md"
requires-python = ">=3.11"
dependencies = [
    "typer>=0.12.0",
    "PyYAML>=6.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
]

[project.scripts]
kb = "kb_agent.cli:app"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]
```

Create `README.md`:

```markdown
# kb-agent

`kb-agent` is a local CLI-first, file-based knowledge base manager.

Phase 1 provides:

- `kb init <domain>`
- `kb ingest [path]`
- `kb compile --fast`
- `kb health`
```

Create `src/kb_agent/__init__.py`:

```python
__version__ = "0.1.0"
```

Create `src/kb_agent/cli.py`:

```python
import typer

from kb_agent import __version__

app = typer.Typer(
    name="kb",
    help="Local file-based knowledge base manager.",
    no_args_is_help=True,
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"kb-agent {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False,
        "--version",
        help="Show version and exit.",
        callback=_version_callback,
        is_eager=True,
    )
) -> None:
    return None
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
pytest tests/test_init.py::test_cli_version_command -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml README.md src/kb_agent/__init__.py src/kb_agent/cli.py tests/conftest.py tests/test_init.py
git commit -m "feat: add kb-agent CLI skeleton"
```

## Task 2: Knowledge Base Initialization

**Files:**
- Create: `src/kb_agent/config.py`
- Create: `src/kb_agent/layout.py`
- Modify: `src/kb_agent/cli.py`
- Modify: `tests/test_init.py`

- [ ] **Step 1: Write failing tests for `kb init`**

Append to `tests/test_init.py`:

```python
from pathlib import Path

import yaml

from tests.conftest import run_cli


def test_init_creates_domain_layout(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    result = run_cli("init", "pcie")

    assert result.exit_code == 0
    root = tmp_path / "pcie"
    assert (root / "kb.yaml").is_file()
    assert (root / "AGENTS.md").is_file()
    assert (root / "README.md").is_file()
    for directory in [
        "inbox",
        "sources/specs",
        "sources/books",
        "sources/datasheets",
        "sources/manuals",
        "sources/webpages",
        "sources/code",
        "sources/logs",
        "sources/images",
        "sources/unknown",
        "notes/concepts",
        "notes/mechanisms",
        "notes/workflows",
        "notes/registers",
        "notes/software",
        "notes/hardware",
        "notes/debug",
        "notes/experiments",
        "sessions/questions",
        "sessions/debug_cases",
        "sessions/design_reviews",
        "sessions/experiments",
        "reports/ingest",
        "reports/learn",
        "reports/compile",
        "reports/health",
        "reviews/routing",
        "reviews/conflicts",
        "reviews/pending_notes",
        "skills",
        "tools",
        ".kb/chunks",
        ".kb/topics",
        ".kb/claims",
        ".kb/citations",
        ".kb/graph",
        ".kb/cache",
    ]:
        assert (root / directory).is_dir()

    config = yaml.safe_load((root / "kb.yaml").read_text())
    assert config["domain"] == "pcie"
    assert config["source_policy"]["ai_can_modify_sources"] is False
    assert config["citation_policy"]["require_citation_for_claim"] is True
    assert config["conflict_policy"]["require_user_review"] is True


def test_init_refuses_existing_nonempty_directory(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    existing = tmp_path / "pcie"
    existing.mkdir()
    (existing / "file.txt").write_text("already here\n")

    result = run_cli("init", "pcie")

    assert result.exit_code != 0
    assert "already exists and is not empty" in result.stdout
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
pytest tests/test_init.py -v
```

Expected: FAIL because `init` command and layout code are not defined.

- [ ] **Step 3: Implement config defaults**

Create `src/kb_agent/config.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class KBConfig:
    domain: str
    title: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "domain": self.domain,
            "title": self.title,
            "source_policy": {"ai_can_modify_sources": False},
            "citation_policy": {"require_citation_for_claim": True},
            "conflict_policy": {"require_user_review": True},
        }


def default_config(domain: str) -> KBConfig:
    return KBConfig(domain=domain, title=f"{domain} Knowledge Base")


def write_config(root: Path, config: KBConfig) -> None:
    path = root / "kb.yaml"
    path.write_text(
        yaml.safe_dump(config.to_dict(), sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )


def load_config(root: Path) -> dict[str, Any]:
    path = root / "kb.yaml"
    if not path.is_file():
        raise FileNotFoundError(f"missing kb.yaml at {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"invalid kb.yaml at {path}")
    return data
```

- [ ] **Step 4: Implement layout creation and discovery**

Create `src/kb_agent/layout.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

from kb_agent.config import default_config, write_config

CANONICAL_DIRS = [
    "inbox",
    "sources/specs",
    "sources/books",
    "sources/datasheets",
    "sources/manuals",
    "sources/webpages",
    "sources/code",
    "sources/logs",
    "sources/images",
    "sources/unknown",
    "notes/concepts",
    "notes/mechanisms",
    "notes/workflows",
    "notes/registers",
    "notes/software",
    "notes/hardware",
    "notes/debug",
    "notes/experiments",
    "sessions/questions",
    "sessions/debug_cases",
    "sessions/design_reviews",
    "sessions/experiments",
    "reports/ingest",
    "reports/learn",
    "reports/compile",
    "reports/health",
    "reviews/routing",
    "reviews/conflicts",
    "reviews/pending_notes",
    "skills",
    "tools",
    ".kb/chunks",
    ".kb/topics",
    ".kb/claims",
    ".kb/citations",
    ".kb/graph",
    ".kb/cache",
]


def create_kb(root: Path, domain: str) -> None:
    if root.exists() and any(root.iterdir()):
        raise FileExistsError(f"{root} already exists and is not empty")
    root.mkdir(parents=True, exist_ok=True)
    for relative in CANONICAL_DIRS:
        (root / relative).mkdir(parents=True, exist_ok=True)

    write_config(root, default_config(domain))
    (root / "AGENTS.md").write_text(
        f"# AGENTS.md instructions for {root}\n\n"
        "You are a domain knowledge-base assistant. Preserve source evidence, "
        "cite original material, and do not rewrite archived sources.\n",
        encoding="utf-8",
    )
    (root / "README.md").write_text(
        f"# {domain} Knowledge Base\n\n"
        "This repository is managed by `kb-agent`.\n",
        encoding="utf-8",
    )
    (root / "notes" / "_index.md").write_text("# Notes Index\n", encoding="utf-8")
    (root / "notes" / "_glossary.md").write_text("# Glossary\n", encoding="utf-8")
    (root / "notes" / "_open_questions.md").write_text("# Open Questions\n", encoding="utf-8")
    (root / ".kb" / "manifest.json").write_text("{}\n", encoding="utf-8")
    (root / ".kb" / "source_index.jsonl").write_text("", encoding="utf-8")
    (root / ".kb" / "compile_state.json").write_text(
        json.dumps({"status": "never_run"}, indent=2) + "\n",
        encoding="utf-8",
    )


def find_kb_root(start: Path) -> Path:
    current = start.resolve()
    for candidate in [current, *current.parents]:
        if (candidate / "kb.yaml").is_file() and (candidate / ".kb").is_dir():
            return candidate
    raise FileNotFoundError("not inside a kb-agent knowledge base")
```

- [ ] **Step 5: Add `kb init` CLI command**

Modify `src/kb_agent/cli.py`:

```python
from pathlib import Path

import typer

from kb_agent import __version__
from kb_agent.layout import create_kb

app = typer.Typer(
    name="kb",
    help="Local file-based knowledge base manager.",
    no_args_is_help=True,
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"kb-agent {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False,
        "--version",
        help="Show version and exit.",
        callback=_version_callback,
        is_eager=True,
    )
) -> None:
    return None


@app.command()
def init(domain: str) -> None:
    """Create a new domain knowledge base."""
    root = Path(domain)
    try:
        create_kb(root, domain)
    except FileExistsError as exc:
        typer.echo(str(exc))
        raise typer.Exit(code=1)
    typer.echo(f"Initialized knowledge base at {root}")
```

- [ ] **Step 6: Run tests to verify they pass**

Run:

```bash
pytest tests/test_init.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/kb_agent/config.py src/kb_agent/layout.py src/kb_agent/cli.py tests/test_init.py
git commit -m "feat: initialize knowledge base layout"
```

## Task 3: Source Metadata and Ingest

**Files:**
- Create: `src/kb_agent/sources.py`
- Modify: `src/kb_agent/cli.py`
- Create: `tests/test_ingest.py`

- [ ] **Step 1: Write failing tests for ingest**

Create `tests/test_ingest.py`:

```python
import json
from pathlib import Path

from tests.conftest import run_cli


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def test_ingest_file_copies_to_sources_and_indexes(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert run_cli("init", "pcie").exit_code == 0
    source_file = tmp_path / "manual.md"
    source_file.write_text("# Controller Manual\nBAR config\n", encoding="utf-8")

    monkeypatch.chdir(tmp_path / "pcie")
    result = run_cli("ingest", str(source_file))

    assert result.exit_code == 0
    records = read_jsonl(tmp_path / "pcie" / ".kb" / "source_index.jsonl")
    assert len(records) == 1
    record = records[0]
    assert record["source_id"] == "manual"
    assert record["type"] == "manual"
    assert record["original_path"] == str(source_file)
    assert record["path"] == "sources/manuals/manual.md"
    assert record["hash"].startswith("sha256:")
    assert (tmp_path / "pcie" / "sources" / "manuals" / "manual.md").read_text() == "# Controller Manual\nBAR config\n"


def test_ingest_directory_indexes_each_file(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert run_cli("init", "pcie").exit_code == 0
    package = tmp_path / "package"
    package.mkdir()
    (package / "boot.log").write_text("link down\n", encoding="utf-8")
    (package / "diagram.png").write_bytes(b"png bytes")

    monkeypatch.chdir(tmp_path / "pcie")
    result = run_cli("ingest", str(package))

    assert result.exit_code == 0
    records = read_jsonl(tmp_path / "pcie" / ".kb" / "source_index.jsonl")
    assert {record["source_id"] for record in records} == {"boot", "diagram"}
    assert (tmp_path / "pcie" / "sources" / "logs" / "boot.log").is_file()
    assert (tmp_path / "pcie" / "sources" / "images" / "diagram.png").is_file()
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
pytest tests/test_ingest.py -v
```

Expected: FAIL because `ingest` and source indexing are not defined.

- [ ] **Step 3: Implement source metadata and ingest operations**

Create `src/kb_agent/sources.py`:

```python
from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class SourceRecord:
    source_id: str
    type: str
    title: str
    path: str
    original_path: str
    hash: str
    status: str = "accepted"


TYPE_BY_SUFFIX = {
    ".pdf": "spec",
    ".md": "manual",
    ".markdown": "manual",
    ".txt": "manual",
    ".html": "webpage",
    ".htm": "webpage",
    ".c": "code",
    ".h": "code",
    ".py": "code",
    ".rs": "code",
    ".go": "code",
    ".log": "log",
    ".png": "image",
    ".jpg": "image",
    ".jpeg": "image",
    ".webp": "image",
}

DESTINATION_BY_TYPE = {
    "spec": "sources/specs",
    "manual": "sources/manuals",
    "webpage": "sources/webpages",
    "code": "sources/code",
    "log": "sources/logs",
    "image": "sources/images",
    "unknown": "sources/unknown",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return f"sha256:{digest.hexdigest()}"


def detect_type(path: Path) -> str:
    return TYPE_BY_SUFFIX.get(path.suffix.lower(), "unknown")


def source_id_for(path: Path) -> str:
    value = path.stem.lower()
    clean = []
    for char in value:
        if char.isalnum():
            clean.append(char)
        elif clean and clean[-1] != "_":
            clean.append("_")
    source_id = "".join(clean).strip("_")
    return source_id or "source"


def iter_input_files(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    if path.is_dir():
        return sorted(item for item in path.rglob("*") if item.is_file())
    raise FileNotFoundError(f"input path does not exist: {path}")


def load_source_index(root: Path) -> list[SourceRecord]:
    index = root / ".kb" / "source_index.jsonl"
    records: list[SourceRecord] = []
    if not index.exists():
        return records
    for line in index.read_text(encoding="utf-8").splitlines():
        if line.strip():
            records.append(SourceRecord(**json.loads(line)))
    return records


def write_source_index(root: Path, records: list[SourceRecord]) -> None:
    index = root / ".kb" / "source_index.jsonl"
    with index.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(asdict(record), ensure_ascii=False, sort_keys=True) + "\n")


def unique_destination(destination: Path) -> Path:
    if not destination.exists():
        return destination
    stem = destination.stem
    suffix = destination.suffix
    parent = destination.parent
    counter = 2
    while True:
        candidate = parent / f"{stem}_{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def ingest_path(root: Path, input_path: Path) -> list[SourceRecord]:
    existing = load_source_index(root)
    records = list(existing)
    new_records: list[SourceRecord] = []
    for file_path in iter_input_files(input_path):
        material_type = detect_type(file_path)
        destination_dir = root / DESTINATION_BY_TYPE[material_type]
        destination_dir.mkdir(parents=True, exist_ok=True)
        destination = unique_destination(destination_dir / file_path.name)
        shutil.copy2(file_path, destination)
        relative_destination = destination.relative_to(root).as_posix()
        record = SourceRecord(
            source_id=source_id_for(destination),
            type=material_type,
            title=file_path.stem,
            path=relative_destination,
            original_path=str(file_path),
            hash=sha256_file(destination),
        )
        records.append(record)
        new_records.append(record)
    write_source_index(root, records)
    return new_records
```

- [ ] **Step 4: Add `kb ingest` CLI command**

Modify `src/kb_agent/cli.py`:

```python
from pathlib import Path

import typer

from kb_agent import __version__
from kb_agent.layout import create_kb, find_kb_root
from kb_agent.sources import ingest_path

app = typer.Typer(
    name="kb",
    help="Local file-based knowledge base manager.",
    no_args_is_help=True,
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"kb-agent {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False,
        "--version",
        help="Show version and exit.",
        callback=_version_callback,
        is_eager=True,
    )
) -> None:
    return None


@app.command()
def init(domain: str) -> None:
    """Create a new domain knowledge base."""
    root = Path(domain)
    try:
        create_kb(root, domain)
    except FileExistsError as exc:
        typer.echo(str(exc))
        raise typer.Exit(code=1)
    typer.echo(f"Initialized knowledge base at {root}")


@app.command()
def ingest(path: Path = typer.Argument(Path("inbox"))) -> None:
    """Copy files into sources/ and update .kb/source_index.jsonl."""
    try:
        root = find_kb_root(Path.cwd())
        records = ingest_path(root, path)
    except (FileNotFoundError, ValueError) as exc:
        typer.echo(str(exc))
        raise typer.Exit(code=1)

    typer.echo(f"Ingested {len(records)} source file(s)")
    for record in records:
        typer.echo(f"- {record.source_id}: {record.path}")
```

- [ ] **Step 5: Run tests to verify they pass**

Run:

```bash
pytest tests/test_ingest.py -v
```

Expected: PASS.

- [ ] **Step 6: Run all tests**

Run:

```bash
pytest -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/kb_agent/sources.py src/kb_agent/cli.py tests/test_ingest.py
git commit -m "feat: ingest sources into file index"
```

## Task 4: Markdown Link and Citation Extraction

**Files:**
- Create: `src/kb_agent/markdown.py`
- Create: `tests/test_compile.py`

- [ ] **Step 1: Write failing tests for Markdown extraction**

Create `tests/test_compile.py`:

```python
from kb_agent.markdown import extract_kb_source_refs, extract_markdown_links


def test_extract_kb_source_refs_from_markdown():
    text = """
Evidence:
- [Spec](kb://source/pcie_base_spec_5_0#section=7.5.1)
- [Linux](kb://source/linux_kernel#path=drivers/pci/probe.c&line=1800)
"""

    refs = extract_kb_source_refs(text)

    assert refs == ["pcie_base_spec_5_0", "linux_kernel"]


def test_extract_relative_markdown_links():
    text = """
[BAR](../mechanisms/bar.md)
[External](https://example.com)
[Source](kb://source/pcie_base_spec_5_0#section=7.5.1)
"""

    links = extract_markdown_links(text)

    assert links == ["../mechanisms/bar.md"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
pytest tests/test_compile.py -v
```

Expected: FAIL because `kb_agent.markdown` is missing.

- [ ] **Step 3: Implement Markdown extraction helpers**

Create `src/kb_agent/markdown.py`:

```python
from __future__ import annotations

import re

MARKDOWN_LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
KB_SOURCE_RE = re.compile(r"kb://source/([^#)\s]+)")


def extract_kb_source_refs(text: str) -> list[str]:
    refs: list[str] = []
    for match in KB_SOURCE_RE.finditer(text):
        refs.append(match.group(1))
    return refs


def extract_markdown_links(text: str) -> list[str]:
    links: list[str] = []
    for match in MARKDOWN_LINK_RE.finditer(text):
        target = match.group(1)
        if target.startswith(("http://", "https://", "kb://", "mailto:")):
            continue
        if target.startswith("#"):
            continue
        links.append(target)
    return links
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
pytest tests/test_compile.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/kb_agent/markdown.py tests/test_compile.py
git commit -m "feat: extract markdown links and kb citations"
```

## Task 5: Fast Compile Checks

**Files:**
- Create: `src/kb_agent/compile.py`
- Modify: `src/kb_agent/cli.py`
- Modify: `tests/test_compile.py`

- [ ] **Step 1: Write failing tests for fast compile**

Append to `tests/test_compile.py`:

```python
import json
from pathlib import Path

from tests.conftest import run_cli


def test_compile_fast_passes_clean_initialized_repo(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert run_cli("init", "pcie").exit_code == 0
    monkeypatch.chdir(tmp_path / "pcie")

    result = run_cli("compile", "--fast")

    assert result.exit_code == 0
    assert "Compile passed" in result.stdout
    state = json.loads((tmp_path / "pcie" / ".kb" / "compile_state.json").read_text())
    assert state["status"] == "passed"


def test_compile_fast_fails_missing_source_reference(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert run_cli("init", "pcie").exit_code == 0
    note = tmp_path / "pcie" / "notes" / "concepts" / "bar.md"
    note.write_text("[Missing](kb://source/missing_source#section=1)\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path / "pcie")

    result = run_cli("compile", "--fast")

    assert result.exit_code == 1
    assert "missing source reference" in result.stdout


def test_compile_fast_fails_broken_relative_markdown_link(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert run_cli("init", "pcie").exit_code == 0
    note = tmp_path / "pcie" / "notes" / "concepts" / "bar.md"
    note.write_text("[Broken](missing.md)\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path / "pcie")

    result = run_cli("compile", "--fast")

    assert result.exit_code == 1
    assert "broken markdown link" in result.stdout
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
pytest tests/test_compile.py -v
```

Expected: FAIL because compile checks are not defined.

- [ ] **Step 3: Implement compile findings and fast checks**

Create `src/kb_agent/compile.py`:

```python
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from kb_agent.layout import CANONICAL_DIRS
from kb_agent.markdown import extract_kb_source_refs, extract_markdown_links
from kb_agent.sources import load_source_index


@dataclass(frozen=True)
class Finding:
    severity: str
    code: str
    path: str
    message: str


@dataclass(frozen=True)
class CompileResult:
    status: str
    findings: list[Finding]

    @property
    def passed(self) -> bool:
        return self.status == "passed"


def markdown_files(root: Path) -> list[Path]:
    search_roots = [root / "notes", root / "sessions", root / "reviews"]
    files: list[Path] = []
    for search_root in search_roots:
        if search_root.exists():
            files.extend(sorted(search_root.rglob("*.md")))
    return files


def check_structure(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for relative in ["kb.yaml", "AGENTS.md", "README.md"]:
        if not (root / relative).is_file():
            findings.append(Finding("error", "missing_file", relative, f"missing required file: {relative}"))
    for relative in CANONICAL_DIRS:
        if not (root / relative).is_dir():
            findings.append(Finding("error", "missing_directory", relative, f"missing required directory: {relative}"))
    return findings


def check_source_files(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for record in load_source_index(root):
        if not (root / record.path).is_file():
            findings.append(
                Finding("error", "missing_source_file", record.path, f"indexed source file is missing: {record.path}")
            )
    return findings


def check_citations(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    source_ids = {record.source_id for record in load_source_index(root)}
    for path in markdown_files(root):
        text = path.read_text(encoding="utf-8")
        for source_id in extract_kb_source_refs(text):
            if source_id not in source_ids:
                relative = path.relative_to(root).as_posix()
                findings.append(
                    Finding(
                        "error",
                        "missing_source_reference",
                        relative,
                        f"missing source reference: {source_id}",
                    )
                )
    return findings


def check_markdown_links(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for path in markdown_files(root):
        text = path.read_text(encoding="utf-8")
        for target in extract_markdown_links(text):
            target_path = (path.parent / target.split("#", 1)[0]).resolve()
            if not target_path.exists():
                relative = path.relative_to(root).as_posix()
                findings.append(
                    Finding(
                        "error",
                        "broken_markdown_link",
                        relative,
                        f"broken markdown link: {target}",
                    )
                )
    return findings


def compile_fast(root: Path) -> CompileResult:
    findings = []
    findings.extend(check_structure(root))
    findings.extend(check_source_files(root))
    findings.extend(check_citations(root))
    findings.extend(check_markdown_links(root))
    status = "failed" if any(finding.severity == "error" for finding in findings) else "passed"
    result = CompileResult(status=status, findings=findings)
    write_compile_state(root, result)
    return result


def write_compile_state(root: Path, result: CompileResult) -> None:
    path = root / ".kb" / "compile_state.json"
    payload = {
        "status": result.status,
        "findings": [asdict(finding) for finding in result.findings],
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
```

- [ ] **Step 4: Add `kb compile --fast` CLI command**

Modify `src/kb_agent/cli.py`:

```python
from pathlib import Path

import typer

from kb_agent import __version__
from kb_agent.compile import compile_fast
from kb_agent.layout import create_kb, find_kb_root
from kb_agent.sources import ingest_path

app = typer.Typer(
    name="kb",
    help="Local file-based knowledge base manager.",
    no_args_is_help=True,
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"kb-agent {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False,
        "--version",
        help="Show version and exit.",
        callback=_version_callback,
        is_eager=True,
    )
) -> None:
    return None


@app.command()
def init(domain: str) -> None:
    """Create a new domain knowledge base."""
    root = Path(domain)
    try:
        create_kb(root, domain)
    except FileExistsError as exc:
        typer.echo(str(exc))
        raise typer.Exit(code=1)
    typer.echo(f"Initialized knowledge base at {root}")


@app.command()
def ingest(path: Path = typer.Argument(Path("inbox"))) -> None:
    """Copy files into sources/ and update .kb/source_index.jsonl."""
    try:
        root = find_kb_root(Path.cwd())
        records = ingest_path(root, path)
    except (FileNotFoundError, ValueError) as exc:
        typer.echo(str(exc))
        raise typer.Exit(code=1)

    typer.echo(f"Ingested {len(records)} source file(s)")
    for record in records:
        typer.echo(f"- {record.source_id}: {record.path}")


@app.command(name="compile")
def compile_command(
    fast: bool = typer.Option(False, "--fast", help="Run fast compile checks.")
) -> None:
    """Check knowledge-base structure, links, citations, and source index."""
    if not fast:
        typer.echo("Phase 1 supports only: kb compile --fast")
        raise typer.Exit(code=1)
    try:
        root = find_kb_root(Path.cwd())
        result = compile_fast(root)
    except FileNotFoundError as exc:
        typer.echo(str(exc))
        raise typer.Exit(code=1)

    for finding in result.findings:
        typer.echo(f"{finding.severity}: {finding.code}: {finding.path}: {finding.message}")
    if result.passed:
        typer.echo("Compile passed")
        raise typer.Exit(code=0)
    typer.echo("Compile failed")
    raise typer.Exit(code=1)
```

- [ ] **Step 5: Run tests to verify they pass**

Run:

```bash
pytest tests/test_compile.py -v
```

Expected: PASS.

- [ ] **Step 6: Run all tests**

Run:

```bash
pytest -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/kb_agent/compile.py src/kb_agent/cli.py tests/test_compile.py
git commit -m "feat: add fast compile checks"
```

## Task 6: Health Report

**Files:**
- Create: `src/kb_agent/health.py`
- Modify: `src/kb_agent/cli.py`
- Create: `tests/test_health.py`

- [ ] **Step 1: Write failing tests for health**

Create `tests/test_health.py`:

```python
from pathlib import Path

from tests.conftest import run_cli


def test_health_reports_clean_empty_kb(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert run_cli("init", "pcie").exit_code == 0
    monkeypatch.chdir(tmp_path / "pcie")

    result = run_cli("health")

    assert result.exit_code == 0
    assert "Health: ok" in result.stdout
    assert "Sources: 0" in result.stdout
    assert "Findings: 0" in result.stdout


def test_health_reports_warning_when_compile_fails(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert run_cli("init", "pcie").exit_code == 0
    note = tmp_path / "pcie" / "notes" / "concepts" / "broken.md"
    note.write_text("[Broken](missing.md)\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path / "pcie")

    result = run_cli("health")

    assert result.exit_code == 0
    assert "Health: warning" in result.stdout
    assert "Findings: 1" in result.stdout
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
pytest tests/test_health.py -v
```

Expected: FAIL because `health` command is not defined.

- [ ] **Step 3: Implement health summary**

Create `src/kb_agent/health.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from kb_agent.compile import compile_fast
from kb_agent.sources import load_source_index


@dataclass(frozen=True)
class HealthReport:
    status: str
    source_count: int
    finding_count: int


def build_health_report(root: Path) -> HealthReport:
    compile_result = compile_fast(root)
    source_count = len(load_source_index(root))
    finding_count = len(compile_result.findings)
    status = "ok" if compile_result.passed else "warning"
    return HealthReport(status=status, source_count=source_count, finding_count=finding_count)
```

- [ ] **Step 4: Add `kb health` CLI command**

Modify `src/kb_agent/cli.py`:

```python
from pathlib import Path

import typer

from kb_agent import __version__
from kb_agent.compile import compile_fast
from kb_agent.health import build_health_report
from kb_agent.layout import create_kb, find_kb_root
from kb_agent.sources import ingest_path

app = typer.Typer(
    name="kb",
    help="Local file-based knowledge base manager.",
    no_args_is_help=True,
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"kb-agent {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False,
        "--version",
        help="Show version and exit.",
        callback=_version_callback,
        is_eager=True,
    )
) -> None:
    return None


@app.command()
def init(domain: str) -> None:
    """Create a new domain knowledge base."""
    root = Path(domain)
    try:
        create_kb(root, domain)
    except FileExistsError as exc:
        typer.echo(str(exc))
        raise typer.Exit(code=1)
    typer.echo(f"Initialized knowledge base at {root}")


@app.command()
def ingest(path: Path = typer.Argument(Path("inbox"))) -> None:
    """Copy files into sources/ and update .kb/source_index.jsonl."""
    try:
        root = find_kb_root(Path.cwd())
        records = ingest_path(root, path)
    except (FileNotFoundError, ValueError) as exc:
        typer.echo(str(exc))
        raise typer.Exit(code=1)

    typer.echo(f"Ingested {len(records)} source file(s)")
    for record in records:
        typer.echo(f"- {record.source_id}: {record.path}")


@app.command(name="compile")
def compile_command(
    fast: bool = typer.Option(False, "--fast", help="Run fast compile checks.")
) -> None:
    """Check knowledge-base structure, links, citations, and source index."""
    if not fast:
        typer.echo("Phase 1 supports only: kb compile --fast")
        raise typer.Exit(code=1)
    try:
        root = find_kb_root(Path.cwd())
        result = compile_fast(root)
    except FileNotFoundError as exc:
        typer.echo(str(exc))
        raise typer.Exit(code=1)

    for finding in result.findings:
        typer.echo(f"{finding.severity}: {finding.code}: {finding.path}: {finding.message}")
    if result.passed:
        typer.echo("Compile passed")
        raise typer.Exit(code=0)
    typer.echo("Compile failed")
    raise typer.Exit(code=1)


@app.command()
def health() -> None:
    """Print a static health summary."""
    try:
        root = find_kb_root(Path.cwd())
        report = build_health_report(root)
    except FileNotFoundError as exc:
        typer.echo(str(exc))
        raise typer.Exit(code=1)
    typer.echo(f"Health: {report.status}")
    typer.echo(f"Sources: {report.source_count}")
    typer.echo(f"Findings: {report.finding_count}")
```

- [ ] **Step 5: Run health tests**

Run:

```bash
pytest tests/test_health.py -v
```

Expected: PASS.

- [ ] **Step 6: Run all tests**

Run:

```bash
pytest -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/kb_agent/health.py src/kb_agent/cli.py tests/test_health.py
git commit -m "feat: add knowledge base health report"
```

## Task 7: CLI Packaging and Manual Smoke Test

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update README usage**

Replace `README.md` with:

````markdown
# kb-agent

`kb-agent` is a local CLI-first, file-based knowledge base manager.

## Install for development

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
```

## Phase 1 commands

```bash
kb init pcie
cd pcie
kb ingest ../some-manual.md
kb compile --fast
kb health
```

## Design

See `specs/2026-05-26-file-ai-knowledge-base-design.md`.
````

- [ ] **Step 2: Run all tests**

Run:

```bash
pytest -v
```

Expected: PASS.

- [ ] **Step 3: Run editable install**

Run:

```bash
python -m pip install -e ".[dev]"
```

Expected: command completes successfully and installs `kb`.

- [ ] **Step 4: Run manual smoke test**

Run:

```bash
tmpdir="$(mktemp -d)"
cd "$tmpdir"
kb init pcie
printf '# Manual\n' > manual.md
cd pcie
kb ingest ../manual.md
kb compile --fast
kb health
```

Expected output includes:

```text
Initialized knowledge base at pcie
Ingested 1 source file(s)
Compile passed
Health: ok
Sources: 1
```

- [ ] **Step 5: Commit**

```bash
git add README.md
git commit -m "docs: add phase 1 usage"
```

## Task 8: Final Verification and Push

**Files:**
- No source file changes expected.

- [ ] **Step 1: Run complete test suite**

Run:

```bash
pytest -v
```

Expected: all tests PASS.

- [ ] **Step 2: Check repository state**

Run:

```bash
git status --short --branch
```

Expected: branch is ahead of `origin/main` by the Phase 1 commits and has no untracked files.

- [ ] **Step 3: Push**

Run:

```bash
git push
```

Expected: push succeeds to `origin/main`.

## Self-Review

Spec coverage:

- `kb init <domain>` is covered by Task 2.
- `kb ingest [path]` is covered by Task 3.
- source manifest and `.kb/source_index.jsonl` are covered by Task 3.
- basic `kb://source/...` citation extraction is covered by Task 4.
- basic Markdown link extraction is covered by Task 4.
- `kb compile --fast` is covered by Task 5.
- `kb health` is covered by Task 6.
- development usage and smoke testing are covered by Task 7.
- full verification and push are covered by Task 8.

Intentional Phase 1 exclusions:

- AI calls, `kb learn`, `kb ask`, staged reviews, semantic conflict detection, embeddings, and topic graphs are excluded because the approved design places them in later phases.

Red-flag scan:

- The plan contains no unresolved implementation blanks.

Type consistency:

- CLI commands call `create_kb`, `find_kb_root`, `ingest_path`, `compile_fast`, and `build_health_report`.
- `SourceRecord` fields match the JSONL tests.
- `CompileResult.passed` is used consistently by `compile` and `health`.
