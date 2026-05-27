import json
from pathlib import Path

from tests.conftest import run_cli


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def run_id_from(output: str) -> str:
    return output.split("Learn run:", 1)[1].splitlines()[0].strip()


def test_graph_export_writes_graph_artifacts_for_initialized_kb(
    tmp_path: Path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    assert run_cli("init", "pcie").exit_code == 0
    monkeypatch.chdir(tmp_path / "pcie")

    result = run_cli("graph", "export")

    assert result.exit_code == 0
    assert "Graph exported" in result.output
    assert "Report: reports/graph/graph_report.md" in result.output
    graph_root = tmp_path / "pcie" / ".kb" / "graph"
    nodes = read_jsonl(graph_root / "nodes.jsonl")
    edges = read_jsonl(graph_root / "edges.jsonl")
    assert {node["node_id"] for node in nodes} == {
        "note:notes/_glossary.md",
        "note:notes/_index.md",
        "note:notes/_open_questions.md",
    }
    assert read_jsonl(graph_root / "edges.jsonl") == []
    summary = json.loads((graph_root / "summary.json").read_text())
    assert summary["node_count"] == len(nodes)
    assert summary["edge_count"] == len(edges)
    report = tmp_path / "pcie" / "reports" / "graph" / "graph_report.md"
    assert report.is_file()
    report_text = report.read_text()
    assert "## Source Coverage" in report_text
    assert "- Total sources: 0" in report_text
    assert "- Linked sources: 0" in report_text
    assert "- Unlinked sources: 0" in report_text
    assert "## Claim Citation Coverage" in report_text
    assert "- Total claims: 0" in report_text
    assert "- Cited claims: 0" in report_text
    assert "- Uncited claims: 0" in report_text


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
    run_id = run_id_from(learn.output)
    assert run_cli("accept", run_id).exit_code == 0
    debug_note = tmp_path / "pcie" / "notes" / "debug" / "bar_debug.md"
    debug_note.write_text(
        "# BAR Debug\n\nRelated source: kb://source/manual\n", encoding="utf-8"
    )

    result = run_cli("graph", "export")

    assert result.exit_code == 0
    assert "Report: reports/graph/graph_report.md" in result.output
    nodes = read_jsonl(tmp_path / "pcie" / ".kb" / "graph" / "nodes.jsonl")
    edges = read_jsonl(tmp_path / "pcie" / ".kb" / "graph" / "edges.jsonl")
    node_types = {node["type"] for node in nodes}
    edge_types = {edge["type"] for edge in edges}
    assert {"source", "topic", "claim", "chunk", "note"} <= node_types
    assert "note:notes/debug/bar_debug.md" in {node["node_id"] for node in nodes}
    assert {
        "topic_from_source",
        "claim_about_topic",
        "claim_cites_source",
        "note_mentions_source",
    } <= edge_types
    assert {
        "from": "note:notes/debug/bar_debug.md",
        "to": "source:manual",
        "type": "note_mentions_source",
        "evidence": "manual",
    } in edges
    summary = json.loads(
        (tmp_path / "pcie" / ".kb" / "graph" / "summary.json").read_text()
    )
    assert summary["node_count"] == len(nodes)
    assert summary["edge_count"] == len(edges)
    report_text = (
        tmp_path / "pcie" / "reports" / "graph" / "graph_report.md"
    ).read_text()
    assert "## Source Coverage" in report_text
    assert "- Total sources: 1" in report_text
    assert "- Linked sources: 1" in report_text
    assert "- Unlinked sources: 0" in report_text
    assert "## Claim Citation Coverage" in report_text
    assert "- Total claims: 1" in report_text
    assert "- Cited claims: 1" in report_text
    assert "- Uncited claims: 0" in report_text


def test_graph_export_deduplicates_edges_before_writing_artifacts(
    tmp_path: Path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    assert run_cli("init", "pcie").exit_code == 0
    kb_root = tmp_path / "pcie"
    claims_root = kb_root / ".kb" / "claims"
    claims_root.mkdir(parents=True, exist_ok=True)
    (claims_root / "claims.jsonl").write_text(
        json.dumps(
            {
                "claim_id": "claim.duplicate",
                "claim": "Duplicate citations point to the same source.",
                "citations": ["kb://source/manual", "kb://source/manual"],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(kb_root)

    result = run_cli("graph", "export")

    assert result.exit_code == 0
    edges = read_jsonl(kb_root / ".kb" / "graph" / "edges.jsonl")
    assert edges == [
        {
            "from": "claim:claim.duplicate",
            "to": "source:manual",
            "type": "claim_cites_source",
            "evidence": "kb://source/manual",
        }
    ]
    summary = json.loads((kb_root / ".kb" / "graph" / "summary.json").read_text())
    assert summary["edge_count"] == 1
    assert summary["edge_counts"] == {"claim_cites_source": 1}


def test_graph_export_matches_note_topics_by_words_not_substrings(
    tmp_path: Path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    assert run_cli("init", "pcie").exit_code == 0
    kb_root = tmp_path / "pcie"
    topics_root = kb_root / ".kb" / "topics"
    topics_root.mkdir(parents=True, exist_ok=True)
    (topics_root / "topics.jsonl").write_text(
        json.dumps(
            {
                "topic_id": "topic.bar",
                "name": "BAR",
                "aliases": ["base address register"],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    notes_root = kb_root / "notes"
    (notes_root / "barrier.md").write_text(
        "# Barrier\n\nThis note discusses a barrier transaction.\n",
        encoding="utf-8",
    )
    (notes_root / "bar.md").write_text(
        "# BAR\n\nThis note discusses bar sizing.\n",
        encoding="utf-8",
    )
    (notes_root / "alias.md").write_text(
        "# Alias\n\nThe base address register is programmed during enumeration.\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(kb_root)

    result = run_cli("graph", "export")

    assert result.exit_code == 0
    topic_edges = [
        edge
        for edge in read_jsonl(kb_root / ".kb" / "graph" / "edges.jsonl")
        if edge["type"] == "note_mentions_topic"
    ]
    assert {
        "from": "note:notes/barrier.md",
        "to": "topic:topic.bar",
        "type": "note_mentions_topic",
        "evidence": "topic.bar",
    } not in topic_edges
    assert {
        "from": "note:notes/bar.md",
        "to": "topic:topic.bar",
        "type": "note_mentions_topic",
        "evidence": "topic.bar",
    } in topic_edges
    assert {
        "from": "note:notes/alias.md",
        "to": "topic:topic.bar",
        "type": "note_mentions_topic",
        "evidence": "topic.bar",
    } in topic_edges
