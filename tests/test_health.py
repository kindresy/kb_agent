from pathlib import Path

import pytest

from tests.conftest import run_cli


def run_id_from(output: str) -> str:
    return output.split("Learn run:", 1)[1].splitlines()[0].strip()


def test_health_reports_clean_empty_kb(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert run_cli("init", "pcie").exit_code == 0
    monkeypatch.chdir(tmp_path / "pcie")

    result = run_cli("health")

    assert result.exit_code == 0
    assert "Health: ok" in result.stdout
    assert "Sources: 0" in result.stdout
    assert "Findings: 0" in result.stdout
    assert "Graph nodes: 0" in result.stdout
    assert "Graph edges: 0" in result.stdout
    assert "Conflicts: 0" in result.stdout


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


def test_health_reports_graph_and_conflict_metrics_after_graph_export(
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
    assert run_cli("graph", "export").exit_code == 0

    result = run_cli("health")

    assert result.exit_code == 0
    assert "Graph nodes:" in result.stdout
    assert "Graph edges:" in result.stdout
    assert "Conflicts: 0" in result.stdout


@pytest.mark.parametrize(
    "summary_text",
    [
        "{",
        "[]",
        '{"node_count": "many", "edge_count": "few"}',
        '{"node_count": true, "edge_count": false}',
    ],
)
def test_health_falls_back_to_zero_graph_counts_for_invalid_summary(
    tmp_path: Path, monkeypatch, summary_text: str
):
    monkeypatch.chdir(tmp_path)
    assert run_cli("init", "pcie").exit_code == 0
    graph_root = tmp_path / "pcie" / ".kb" / "graph"
    graph_root.mkdir(parents=True, exist_ok=True)
    (graph_root / "summary.json").write_text(summary_text, encoding="utf-8")
    monkeypatch.chdir(tmp_path / "pcie")

    result = run_cli("health")

    assert result.exit_code == 0
    assert "Graph nodes: 0" in result.stdout
    assert "Graph edges: 0" in result.stdout
