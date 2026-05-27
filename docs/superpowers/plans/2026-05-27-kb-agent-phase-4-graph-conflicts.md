# KB Agent Phase 4 Graph and Conflict Detection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build deterministic graph export and conflict gates for accepted and candidate KB claims.

**Architecture:** Add focused modules for graph construction and conflict detection. Wire graph export into the CLI, conflict checks into `compile --fast` and `accept`, and graph/conflict metrics into `health`. Keep all outputs rebuildable files under `.kb/graph/`, `reports/graph/`, and `reviews/conflicts/`.

**Tech Stack:** Python 3.11+, Typer, pytest, dataclasses, pathlib, json/jsonl.

---

## File Structure

- Create `src/kb_agent/graph.py`: graph node/edge dataclasses, accepted artifact loading, graph construction, graph artifact/report writing.
- Create `src/kb_agent/conflicts.py`: claim normalization, deterministic conflict rules, accepted/candidate comparison, conflict artifact/report writing.
- Modify `src/kb_agent/cli.py`: add `kb graph export`; extend `health` output.
- Modify `src/kb_agent/compile.py`: call accepted-claim conflict detection in `compile_fast`.
- Modify `src/kb_agent/accept.py`: block candidate conflicts before promotion and write review artifacts.
- Modify `src/kb_agent/health.py`: include graph node/edge counts and accepted conflict count.
- Create `tests/test_graph.py`: graph construction and CLI export tests.
- Create `tests/test_conflicts.py`: conflict rule tests, compile gate tests, accept gate tests.
- Modify `tests/test_health.py`: health graph/conflict metric coverage.
- Modify `README.md`: Phase 4 usage.
- Create `examples/phase4_demo.sh`: end-to-end conflict review demo.

## Task 1: Graph Builder and Export Command

**Files:**
- Create: `src/kb_agent/graph.py`
- Modify: `src/kb_agent/cli.py`
- Create: `tests/test_graph.py`

- [ ] **Step 1: Write failing tests for empty and populated graph export**

Create `tests/test_graph.py`:

```python
import json
from pathlib import Path

from tests.conftest import run_cli


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def test_graph_export_writes_empty_graph_for_initialized_kb(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert run_cli("init", "pcie").exit_code == 0
    monkeypatch.chdir(tmp_path / "pcie")

    result = run_cli("graph", "export")

    assert result.exit_code == 0
    assert "Graph exported" in result.output
    graph_root = tmp_path / "pcie" / ".kb" / "graph"
    assert read_jsonl(graph_root / "nodes.jsonl") == []
    assert read_jsonl(graph_root / "edges.jsonl") == []
    summary = json.loads((graph_root / "summary.json").read_text())
    assert summary["node_count"] == 0
    assert summary["edge_count"] == 0
    assert (tmp_path / "pcie" / "reports" / "graph" / "graph_report.md").is_file()


def test_graph_export_indexes_accepted_sources_topics_claims_chunks_and_notes(
    tmp_path: Path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    assert run_cli("init", "pcie").exit_code == 0
    source = tmp_path / "manual.md"
    source.write_text("# BAR Assignment\nBAR notes\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path / "pcie")
    assert run_cli("ingest", str(source)).exit_code == 0
    learn = run_cli("learn")
    run_id = learn.output.split("Learn run:", 1)[1].splitlines()[0].strip()
    assert run_cli("accept", run_id).exit_code == 0

    result = run_cli("graph", "export")

    assert result.exit_code == 0
    nodes = read_jsonl(tmp_path / "pcie" / ".kb" / "graph" / "nodes.jsonl")
    edges = read_jsonl(tmp_path / "pcie" / ".kb" / "graph" / "edges.jsonl")
    node_types = {node["type"] for node in nodes}
    edge_types = {edge["type"] for edge in edges}
    assert {"source", "topic", "claim", "chunk", "note"} <= node_types
    assert {"topic_from_source", "claim_about_topic", "claim_cites_source"} <= edge_types
    summary = json.loads((tmp_path / "pcie" / ".kb" / "graph" / "summary.json").read_text())
    assert summary["node_count"] == len(nodes)
    assert summary["edge_count"] == len(edges)
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
uv run --extra dev pytest tests/test_graph.py -v
```

Expected: FAIL because the `graph` command/module does not exist.

- [ ] **Step 3: Implement graph module**

Create `src/kb_agent/graph.py`:

```python
from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path

from kb_agent.jsonl import read_jsonl, write_jsonl
from kb_agent.markdown import extract_kb_source_refs
from kb_agent.sources import load_source_index


@dataclass(frozen=True)
class GraphNode:
    node_id: str
    type: str
    label: str
    ref: str


@dataclass(frozen=True)
class GraphEdge:
    from_: str
    to: str
    type: str
    evidence: str

    def to_record(self) -> dict[str, str]:
        return {"from": self.from_, "to": self.to, "type": self.type, "evidence": self.evidence}


@dataclass(frozen=True)
class GraphExport:
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    report_path: str


def _claim_paths(root: Path) -> list[Path]:
    claims_root = root / ".kb" / "claims"
    return sorted(claims_root.rglob("*.jsonl")) if claims_root.is_dir() else []


def _topic_paths(root: Path) -> list[Path]:
    topics_root = root / ".kb" / "topics"
    return sorted(topics_root.rglob("*.jsonl")) if topics_root.is_dir() else []


def _chunk_paths(root: Path) -> list[Path]:
    chunks_root = root / ".kb" / "chunks"
    return sorted(chunks_root.rglob("*.jsonl")) if chunks_root.is_dir() else []


def _note_paths(root: Path) -> list[Path]:
    notes_root = root / "notes"
    return sorted(notes_root.rglob("*.md")) if notes_root.is_dir() else []


def build_graph(root: Path) -> tuple[list[GraphNode], list[GraphEdge]]:
    nodes: dict[str, GraphNode] = {}
    edges: list[GraphEdge] = []

    for source in load_source_index(root):
        nodes[f"source:{source.source_id}"] = GraphNode(
            f"source:{source.source_id}", "source", source.title, source.path
        )

    for path in _topic_paths(root):
        relative = path.relative_to(root).as_posix()
        for topic in read_jsonl(path):
            topic_id = str(topic.get("topic_id", ""))
            if not topic_id:
                continue
            nodes[f"topic:{topic_id}"] = GraphNode(
                f"topic:{topic_id}", "topic", str(topic.get("name", topic_id)), relative
            )
            source_id = str(topic.get("source_id", ""))
            if source_id:
                edges.append(GraphEdge(f"topic:{topic_id}", f"source:{source_id}", "topic_from_source", "source_id"))

    for path in _chunk_paths(root):
        relative = path.relative_to(root).as_posix()
        for chunk in read_jsonl(path):
            chunk_id = str(chunk.get("chunk_id", ""))
            if not chunk_id:
                continue
            nodes[f"chunk:{chunk_id}"] = GraphNode(
                f"chunk:{chunk_id}", "chunk", chunk_id, relative
            )
            topic_id = str(chunk.get("topic_id", ""))
            source_id = str(chunk.get("source_id", ""))
            if topic_id:
                edges.append(GraphEdge(f"chunk:{chunk_id}", f"topic:{topic_id}", "chunk_supports_topic", "topic_id"))
            if source_id:
                edges.append(GraphEdge(f"chunk:{chunk_id}", f"source:{source_id}", "chunk_from_source", "source_id"))

    for path in _claim_paths(root):
        relative = path.relative_to(root).as_posix()
        for claim in read_jsonl(path):
            claim_id = str(claim.get("claim_id", ""))
            if not claim_id:
                continue
            nodes[f"claim:{claim_id}"] = GraphNode(
                f"claim:{claim_id}", "claim", str(claim.get("claim", claim_id)), relative
            )
            topic_id = str(claim.get("topic_id", ""))
            if topic_id:
                edges.append(GraphEdge(f"claim:{claim_id}", f"topic:{topic_id}", "claim_about_topic", "topic_id"))
            for citation in claim.get("citations") or []:
                for source_id in extract_kb_source_refs(str(citation)):
                    edges.append(GraphEdge(f"claim:{claim_id}", f"source:{source_id}", "claim_cites_source", str(citation)))

    topic_node_ids = {node.node_id.removeprefix("topic:") for node in nodes.values() if node.type == "topic"}
    for note in _note_paths(root):
        relative = note.relative_to(root).as_posix()
        text = note.read_text(encoding="utf-8", errors="replace")
        node_id = f"note:{relative}"
        nodes[node_id] = GraphNode(node_id, "note", relative, relative)
        for source_id in extract_kb_source_refs(text):
            edges.append(GraphEdge(node_id, f"source:{source_id}", "note_mentions_source", source_id))
        for topic_id in topic_node_ids:
            if topic_id in text or topic_id.removeprefix("topic.").replace("_", " ") in text.lower():
                edges.append(GraphEdge(node_id, f"topic:{topic_id}", "note_mentions_topic", topic_id))

    return sorted(nodes.values(), key=lambda node: node.node_id), sorted(
        edges, key=lambda edge: (edge.from_, edge.to, edge.type, edge.evidence)
    )


def export_graph(root: Path) -> GraphExport:
    nodes, edges = build_graph(root)
    graph_root = root / ".kb" / "graph"
    write_jsonl(graph_root / "nodes.jsonl", [asdict(node) for node in nodes])
    write_jsonl(graph_root / "edges.jsonl", [edge.to_record() for edge in edges])

    node_counts = Counter(node.type for node in nodes)
    edge_counts = Counter(edge.type for edge in edges)
    summary = {
        "node_count": len(nodes),
        "edge_count": len(edges),
        "node_counts": dict(sorted(node_counts.items())),
        "edge_counts": dict(sorted(edge_counts.items())),
    }
    (graph_root / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    report_path = root / "reports" / "graph" / "graph_report.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        "\n".join(
            [
                "# Graph Report",
                "",
                f"Nodes: {len(nodes)}",
                f"Edges: {len(edges)}",
                "",
                "## Node Counts",
                *[f"- {key}: {value}" for key, value in sorted(node_counts.items())],
                "",
                "## Edge Counts",
                *[f"- {key}: {value}" for key, value in sorted(edge_counts.items())],
                "",
            ]
        ),
        encoding="utf-8",
    )
    return GraphExport(nodes, edges, report_path.relative_to(root).as_posix())
```

- [ ] **Step 4: Add CLI subcommand group**

Modify `src/kb_agent/cli.py`:

```python
from kb_agent.graph import export_graph

graph_app = typer.Typer(help="Graph commands.")
app.add_typer(graph_app, name="graph")


@graph_app.command(name="export")
def graph_export() -> None:
    """Export deterministic graph artifacts."""
    try:
        root = find_kb_root(Path.cwd())
        result = export_graph(root)
    except (FileNotFoundError, ValueError) as exc:
        typer.echo(str(exc))
        raise typer.Exit(code=1)

    typer.echo("Graph exported")
    typer.echo(f"Nodes: {len(result.nodes)}")
    typer.echo(f"Edges: {len(result.edges)}")
    typer.echo(f"Report: {result.report_path}")
```

Place `graph_app` setup after the main `app = typer.Typer(...)` declaration and before command definitions.

- [ ] **Step 5: Run graph tests and full suite**

Run:

```bash
uv run --extra dev pytest tests/test_graph.py -v
uv run --extra dev pytest -q
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/kb_agent/graph.py src/kb_agent/cli.py tests/test_graph.py
git commit -m "feat: add deterministic graph export"
```

## Task 2: Conflict Rule Engine

**Files:**
- Create: `src/kb_agent/conflicts.py`
- Create: `tests/test_conflicts.py`

- [ ] **Step 1: Write failing unit tests for deterministic rules**

Create `tests/test_conflicts.py`:

```python
from kb_agent.conflicts import detect_claim_conflicts


def claim(claim_id: str, topic_id: str, text: str) -> dict:
    return {
        "claim_id": claim_id,
        "topic_id": topic_id,
        "type": "source_observation",
        "claim": text,
        "citations": [f"kb://source/{claim_id}"],
        "confidence": "deterministic",
    }


def test_detects_negation_polarity_conflict():
    accepted = [claim("accepted", "topic.bar", "BAR0 is assigned by firmware.")]
    candidate = [claim("candidate", "topic.bar", "BAR0 is not assigned by firmware.")]

    conflicts = detect_claim_conflicts(accepted, candidate, "learn_test")

    assert len(conflicts) == 1
    assert conflicts[0].rule == "negation_polarity"
    assert conflicts[0].accepted_claim_id == "accepted"
    assert conflicts[0].candidate_claim_id == "candidate"


def test_detects_modal_conflict():
    accepted = [claim("accepted", "topic.ltssm", "PERST must be asserted before link training.")]
    candidate = [claim("candidate", "topic.ltssm", "PERST must not be asserted before link training.")]

    conflicts = detect_claim_conflicts(accepted, candidate, "learn_test")

    assert len(conflicts) == 1
    assert conflicts[0].rule == "modal_conflict"


def test_detects_single_valued_assignment_conflict():
    accepted = [claim("accepted", "topic.msi", "MSI vector count is 32.")]
    candidate = [claim("candidate", "topic.msi", "MSI vector count is 64.")]

    conflicts = detect_claim_conflicts(accepted, candidate, "learn_test")

    assert len(conflicts) == 1
    assert conflicts[0].rule == "single_valued_assignment"


def test_different_topics_do_not_conflict():
    accepted = [claim("accepted", "topic.a", "BAR0 is assigned by firmware.")]
    candidate = [claim("candidate", "topic.b", "BAR0 is not assigned by firmware.")]

    assert detect_claim_conflicts(accepted, candidate, "learn_test") == []
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
uv run --extra dev pytest tests/test_conflicts.py -v
```

Expected: FAIL because `kb_agent.conflicts` does not exist.

- [ ] **Step 3: Implement conflict module**

Create `src/kb_agent/conflicts.py`:

```python
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

from kb_agent.jsonl import read_jsonl, write_jsonl

NEGATION_WORDS = {"not", "no", "never", "without", "disabled", "unsupported", "cannot", "cant"}
AUXILIARY_WORDS = {"do", "does", "did"}
REQUIREMENT_MODALS = {"must", "required", "shall", "always"}
PROHIBITION_PATTERNS = {"must not", "shall not", "forbidden", "prohibited", "never"}


@dataclass(frozen=True)
class ClaimConflict:
    conflict_id: str
    rule: str
    severity: str
    topic_id: str
    accepted_claim_id: str
    candidate_claim_id: str
    accepted_claim: str
    candidate_claim: str
    accepted_citations: list[str]
    candidate_citations: list[str]
    message: str


def tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9_]+", text.lower().replace("can't", "cannot"))


def normalized_without_negation(text: str) -> str:
    return " ".join(
        token for token in tokens(text) if token not in NEGATION_WORDS | AUXILIARY_WORDS
    )


def has_negation(text: str) -> bool:
    lowered = text.lower().replace("can't", "cannot")
    return any(pattern in lowered for pattern in ["must not", "shall not"]) or any(
        token in NEGATION_WORDS for token in tokens(lowered)
    )


def has_requirement_modal(text: str) -> bool:
    return bool(set(tokens(text)) & REQUIREMENT_MODALS)


def has_prohibition_modal(text: str) -> bool:
    lowered = text.lower()
    return any(pattern in lowered for pattern in PROHIBITION_PATTERNS)


def has_requirement_without_prohibition(text: str) -> bool:
    return has_requirement_modal(text) and not has_prohibition_modal(text)


def token_overlap_ratio(left: str, right: str) -> float:
    left_tokens = set(tokens(left))
    right_tokens = set(tokens(right))
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / max(len(left_tokens), len(right_tokens))


def parse_assignment(text: str) -> tuple[str, str] | None:
    normalized = " ".join(tokens(text))
    match = re.match(r"(.+?)\s+(?:is|uses|=)\s+(.+)", normalized)
    if not match:
        return None
    return match.group(1).strip(), match.group(2).strip()


def conflict_rule(accepted: dict, candidate: dict) -> str | None:
    if str(accepted.get("topic_id", "")) != str(candidate.get("topic_id", "")):
        return None

    accepted_text = str(accepted.get("claim", ""))
    candidate_text = str(candidate.get("claim", ""))
    if (
        normalized_without_negation(accepted_text) == normalized_without_negation(candidate_text)
        and has_negation(accepted_text) != has_negation(candidate_text)
    ):
        return "negation_polarity"

    if token_overlap_ratio(accepted_text, candidate_text) >= 0.6 and (
        (
            has_requirement_without_prohibition(accepted_text)
            and has_prohibition_modal(candidate_text)
        )
        or (
            has_prohibition_modal(accepted_text)
            and has_requirement_without_prohibition(candidate_text)
        )
    ):
        return "modal_conflict"

    accepted_assignment = parse_assignment(accepted_text)
    candidate_assignment = parse_assignment(candidate_text)
    if accepted_assignment and candidate_assignment:
        if accepted_assignment[0] == candidate_assignment[0] and accepted_assignment[1] != candidate_assignment[1]:
            return "single_valued_assignment"

    return None


def detect_claim_conflicts(
    accepted_claims: list[dict], candidate_claims: list[dict], run_id: str
) -> list[ClaimConflict]:
    conflicts: list[ClaimConflict] = []
    for accepted in accepted_claims:
        for candidate in candidate_claims:
            rule = conflict_rule(accepted, candidate)
            if rule is None:
                continue
            conflicts.append(
                ClaimConflict(
                    conflict_id=f"conflict.{run_id}.{len(conflicts) + 1}",
                    rule=rule,
                    severity="error",
                    topic_id=str(candidate.get("topic_id", "")),
                    accepted_claim_id=str(accepted.get("claim_id", "<missing>")),
                    candidate_claim_id=str(candidate.get("claim_id", "<missing>")),
                    accepted_claim=str(accepted.get("claim", "")),
                    candidate_claim=str(candidate.get("claim", "")),
                    accepted_citations=[str(item) for item in accepted.get("citations") or []],
                    candidate_citations=[str(item) for item in candidate.get("citations") or []],
                    message="candidate claim conflicts with an accepted claim",
                )
            )
    return conflicts


def load_accepted_claims(root: Path) -> list[dict]:
    claims_root = root / ".kb" / "claims"
    claims: list[dict] = []
    if claims_root.is_dir():
        for path in sorted(claims_root.rglob("*.jsonl")):
            claims.extend(read_jsonl(path))
    return claims


def load_run_claims(root: Path, run_id: str) -> list[dict]:
    return read_jsonl(root / ".kb" / "learn_runs" / run_id / "claims.jsonl")


def detect_accepted_conflicts(root: Path) -> list[ClaimConflict]:
    claims = load_accepted_claims(root)
    conflicts: list[ClaimConflict] = []
    for index, left in enumerate(claims):
        for right in claims[index + 1 :]:
            rule = conflict_rule(left, right)
            if rule is None:
                continue
            conflicts.append(
                ClaimConflict(
                    conflict_id=f"conflict.accepted.{len(conflicts) + 1}",
                    rule=rule,
                    severity="error",
                    topic_id=str(left.get("topic_id", "")),
                    accepted_claim_id=str(left.get("claim_id", "<missing>")),
                    candidate_claim_id=str(right.get("claim_id", "<missing>")),
                    accepted_claim=str(left.get("claim", "")),
                    candidate_claim=str(right.get("claim", "")),
                    accepted_citations=[str(item) for item in left.get("citations") or []],
                    candidate_citations=[str(item) for item in right.get("citations") or []],
                    message="accepted claims conflict",
                )
            )
    return conflicts


def write_conflict_artifacts(root: Path, run_id: str, conflicts: list[ClaimConflict]) -> str:
    conflict_root = root / "reviews" / "conflicts" / run_id
    conflict_root.mkdir(parents=True, exist_ok=True)
    write_jsonl(conflict_root / "conflicts.jsonl", [asdict(conflict) for conflict in conflicts])
    report_path = conflict_root / "conflict_report.md"
    report_path.write_text(
        "\n".join(
            [
                "# Conflict Report",
                "",
                f"Run: `{run_id}`",
                f"Conflicts: {len(conflicts)}",
                "",
                *[
                    "\n".join(
                        [
                            f"## {conflict.conflict_id}",
                            "",
                            f"- Rule: {conflict.rule}",
                            f"- Topic: {conflict.topic_id}",
                            f"- Accepted: {conflict.accepted_claim}",
                            f"- Candidate: {conflict.candidate_claim}",
                            f"- Accepted citations: {', '.join(conflict.accepted_citations)}",
                            f"- Candidate citations: {', '.join(conflict.candidate_citations)}",
                            "",
                        ]
                    )
                    for conflict in conflicts
                ],
                "## Suggested Next Action",
                "",
                "- Revise the candidate note, reject the run, or split the topic before accepting.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return report_path.relative_to(root).as_posix()
```

- [ ] **Step 4: Run conflict unit tests**

Run:

```bash
uv run --extra dev pytest tests/test_conflicts.py -v
```

Expected: all conflict unit tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/kb_agent/conflicts.py tests/test_conflicts.py
git commit -m "feat: add deterministic conflict rules"
```

## Task 3: Compile and Accept Conflict Gates

**Files:**
- Modify: `src/kb_agent/compile.py`
- Modify: `src/kb_agent/accept.py`
- Modify: `tests/test_conflicts.py`

- [ ] **Step 1: Add failing tests for compile and accept gates**

Append to `tests/test_conflicts.py`:

```python
import json
from pathlib import Path

from kb_agent.jsonl import append_jsonl, read_jsonl
from tests.conftest import run_cli


def accepted_claim_path(root: Path) -> Path:
    return root / ".kb" / "claims" / "claims.jsonl"


def test_compile_fast_fails_accepted_claim_conflict(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert run_cli("init", "pcie").exit_code == 0
    root = tmp_path / "pcie"
    append_jsonl(
        accepted_claim_path(root),
        [
            claim("claim.a", "topic.bar", "BAR0 is assigned by firmware."),
            claim("claim.b", "topic.bar", "BAR0 is not assigned by firmware."),
        ],
    )
    monkeypatch.chdir(root)

    result = run_cli("compile", "--fast")

    assert result.exit_code == 1
    assert "claim_conflict" in result.output
    state = json.loads((root / ".kb" / "compile_state.json").read_text())
    assert any(finding["code"] == "claim_conflict" for finding in state["findings"])


def test_accept_blocks_candidate_conflict_without_partial_promotion(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert run_cli("init", "pcie").exit_code == 0
    source = tmp_path / "manual.md"
    source.write_text("# BAR Assignment\nBAR notes\n", encoding="utf-8")
    root = tmp_path / "pcie"
    monkeypatch.chdir(root)
    assert run_cli("ingest", str(source)).exit_code == 0
    first = run_cli("learn")
    first_run_id = first.output.split("Learn run:", 1)[1].splitlines()[0].strip()
    assert run_cli("accept", first_run_id).exit_code == 0

    second = run_cli("learn")
    second_run_id = second.output.split("Learn run:", 1)[1].splitlines()[0].strip()
    claims_path = root / ".kb" / "learn_runs" / second_run_id / "claims.jsonl"
    claims = read_jsonl(claims_path)
    claims[0]["claim"] = claims[0]["claim"].replace("introduces", "does not introduce")
    claims_path.write_text(
        "".join(json.dumps(item, sort_keys=True) + "\n" for item in claims),
        encoding="utf-8",
    )

    result = run_cli("accept", second_run_id)

    assert result.exit_code == 1
    assert "conflict_report.md" in result.output
    conflict_root = root / "reviews" / "conflicts" / second_run_id
    assert (conflict_root / "conflicts.jsonl").is_file()
    assert (conflict_root / "conflict_report.md").is_file()
    accepted_claim_ids = {
        item["claim_id"] for item in read_jsonl(root / ".kb" / "claims" / "claims.jsonl")
    }
    assert claims[0]["claim_id"] not in accepted_claim_ids
```

- [ ] **Step 2: Run targeted tests and verify RED**

Run:

```bash
uv run --extra dev pytest tests/test_conflicts.py::test_compile_fast_fails_accepted_claim_conflict tests/test_conflicts.py::test_accept_blocks_candidate_conflict_without_partial_promotion -v
```

Expected: FAIL because compile and accept do not call conflict detection yet.

- [ ] **Step 3: Wire conflict checks into compile**

Modify `src/kb_agent/compile.py`:

```python
from kb_agent.conflicts import detect_accepted_conflicts
```

Add:

```python
def check_claim_conflicts(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for conflict in detect_accepted_conflicts(root):
        findings.append(
            Finding(
                "error",
                "claim_conflict",
                ".kb/claims/claims.jsonl",
                f"accepted claims conflict: {conflict.conflict_id}",
            )
        )
    return findings
```

Update `compile_fast` finding list to include `*check_claim_conflicts(root)` after `*check_claims(root)`.

- [ ] **Step 4: Wire conflict checks into accept**

Modify `src/kb_agent/accept.py`:

```python
from kb_agent.conflicts import (
    detect_claim_conflicts,
    load_accepted_claims,
    load_run_claims,
    write_conflict_artifacts,
)
```

Inside `accept_learn_run`, after `errors = validate_run_claims(...)` succeeds and before `compile_fast(root)`:

```python
    conflicts = detect_claim_conflicts(
        load_accepted_claims(root), load_run_claims(root, run_id), run_id
    )
    if conflicts:
        report_path = write_conflict_artifacts(root, run_id, conflicts)
        raise ValueError(f"candidate conflicts found: {report_path}")
```

- [ ] **Step 5: Run gate tests and full suite**

Run:

```bash
uv run --extra dev pytest tests/test_conflicts.py -v
uv run --extra dev pytest -q
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/kb_agent/compile.py src/kb_agent/accept.py tests/test_conflicts.py
git commit -m "feat: block conflicting claims"
```

## Task 4: Health Metrics

**Files:**
- Modify: `src/kb_agent/health.py`
- Modify: `src/kb_agent/cli.py`
- Modify: `tests/test_health.py`

- [ ] **Step 1: Add failing health metric test**

Append to `tests/test_health.py`:

```python
from pathlib import Path

from tests.conftest import run_cli


def test_health_reports_graph_and_conflict_metrics(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert run_cli("init", "pcie").exit_code == 0
    source = tmp_path / "manual.md"
    source.write_text("# BAR Assignment\nBAR notes\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path / "pcie")
    assert run_cli("ingest", str(source)).exit_code == 0
    learn = run_cli("learn")
    run_id = learn.output.split("Learn run:", 1)[1].splitlines()[0].strip()
    assert run_cli("accept", run_id).exit_code == 0
    assert run_cli("graph", "export").exit_code == 0

    result = run_cli("health")

    assert result.exit_code == 0
    assert "Graph nodes:" in result.output
    assert "Graph edges:" in result.output
    assert "Conflicts: 0" in result.output
```

- [ ] **Step 2: Run test and verify RED**

Run:

```bash
uv run --extra dev pytest tests/test_health.py::test_health_reports_graph_and_conflict_metrics -v
```

Expected: FAIL because health output does not include graph/conflict metrics.

- [ ] **Step 3: Extend health report**

Modify `src/kb_agent/health.py`:

```python
import json

from kb_agent.conflicts import detect_accepted_conflicts


@dataclass(frozen=True)
class HealthReport:
    status: str
    source_count: int
    finding_count: int
    graph_node_count: int
    graph_edge_count: int
    conflict_count: int


def _graph_counts(root: Path) -> tuple[int, int]:
    summary_path = root / ".kb" / "graph" / "summary.json"
    if not summary_path.is_file():
        return 0, 0
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    return int(summary.get("node_count", 0)), int(summary.get("edge_count", 0))
```

Update `build_health_report`:

```python
    graph_node_count, graph_edge_count = _graph_counts(root)
    conflict_count = len(detect_accepted_conflicts(root))
    return HealthReport(
        status=status,
        source_count=source_count,
        finding_count=finding_count,
        graph_node_count=graph_node_count,
        graph_edge_count=graph_edge_count,
        conflict_count=conflict_count,
    )
```

- [ ] **Step 4: Extend CLI health output**

Modify `src/kb_agent/cli.py` health command:

```python
    typer.echo(f"Graph nodes: {report.graph_node_count}")
    typer.echo(f"Graph edges: {report.graph_edge_count}")
    typer.echo(f"Conflicts: {report.conflict_count}")
```

- [ ] **Step 5: Run health tests and full suite**

Run:

```bash
uv run --extra dev pytest tests/test_health.py -v
uv run --extra dev pytest -q
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/kb_agent/health.py src/kb_agent/cli.py tests/test_health.py
git commit -m "feat: report graph conflict health metrics"
```

## Task 5: README and Phase 4 Demo

**Files:**
- Modify: `README.md`
- Create: `examples/phase4_demo.sh`

- [ ] **Step 1: Add README Phase 4 usage**

Add this section after Phase 3 in `README.md`:

````markdown
## Phase 4 graph and conflicts

```bash
kb graph export
kb compile --fast
kb health
```

Phase 4 exports a deterministic graph from accepted sources, topics, chunks,
claims, and notes. `kb compile --fast` fails when accepted claims conflict.
`kb accept <run_id>` blocks candidate claims that conflict with accepted
claims and writes review artifacts under `reviews/conflicts/<run_id>/`.
````

- [ ] **Step 2: Add end-to-end demo script**

Create `examples/phase4_demo.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

KB_BIN="${KB_BIN:-kb}"
DEMO_ROOT="${DEMO_ROOT:-$(mktemp -d)}"

echo "Demo root: ${DEMO_ROOT}"
cd "${DEMO_ROOT}"

cat > pcie.md <<'MARKDOWN'
# BAR Assignment

BAR0 is assigned by firmware.
MARKDOWN

echo
echo "== kb init pcie =="
"${KB_BIN}" init pcie

cd pcie

echo
echo "== kb ingest ../pcie.md =="
"${KB_BIN}" ingest ../pcie.md

echo
echo "== kb learn + accept =="
learn_output=$("${KB_BIN}" learn)
echo "${learn_output}"
learn_run_id=$(printf '%s\n' "${learn_output}" | awk -F': ' '/Learn run:/ {print $2}')
"${KB_BIN}" accept "${learn_run_id}"

echo
echo "== kb graph export =="
"${KB_BIN}" graph export

echo
echo "== create conflicting candidate run =="
conflict_output=$("${KB_BIN}" learn)
echo "${conflict_output}"
conflict_run_id=$(printf '%s\n' "${conflict_output}" | awk -F': ' '/Learn run:/ {print $2}')
python - "${conflict_run_id}" <<'PY'
import json
import pathlib
import sys

run_id = sys.argv[1]
path = pathlib.Path(".kb") / "learn_runs" / run_id / "claims.jsonl"
claims = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
claims[0]["claim"] = claims[0]["claim"].replace("introduces", "does not introduce")
path.write_text("".join(json.dumps(claim, sort_keys=True) + "\n" for claim in claims), encoding="utf-8")
PY

echo
echo "== kb accept conflicting run =="
if "${KB_BIN}" accept "${conflict_run_id}"; then
  echo "expected conflict accept failure" >&2
  exit 1
fi

echo
echo "== conflict artifacts =="
find "reviews/conflicts/${conflict_run_id}" -type f | sort

echo
echo "== kb compile --fast =="
"${KB_BIN}" compile --fast

echo
echo "== kb health =="
"${KB_BIN}" health

echo
echo "Demo completed."
```

- [ ] **Step 3: Run full tests and demo**

Run:

```bash
uv run --extra dev pytest -q
KB_BIN="$PWD/.venv/bin/kb" bash examples/phase4_demo.sh
```

Expected: tests pass and demo prints conflict artifacts plus healthy compile/health for accepted state.

- [ ] **Step 4: Commit**

```bash
git add README.md examples/phase4_demo.sh
git commit -m "docs: add phase 4 graph conflict demo"
```

## Task 6: Final Verification and Push

**Files:**
- No source files unless verification exposes a bug.

- [ ] **Step 1: Run complete verification**

Run:

```bash
uv run --extra dev pytest -v
KB_BIN="$PWD/.venv/bin/kb" bash examples/phase4_demo.sh
git status --short --branch
```

Expected:

- pytest reports all tests passed
- demo exits 0
- branch is clean

- [ ] **Step 2: Push branch**

Run:

```bash
git push -u origin phase-4-graph-conflicts
```

- [ ] **Step 3: Completion handoff**

Report:

- branch name
- commit range
- verification commands and pass counts
- whether PR/merge is ready

## Self-Review Checklist

- Graph export coverage: Task 1.
- Conflict rule coverage: Task 2.
- Compile and accept gates: Task 3.
- Health metrics: Task 4.
- README/demo: Task 5.
- Final verification/push: Task 6.
- Hooks and PCIe domain skills are intentionally excluded for Phase 4.3/4.4.
