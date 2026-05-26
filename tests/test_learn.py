import json
from pathlib import Path

from tests.conftest import run_cli


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def run_id_from(output: str) -> str:
    return output.split("Learn run:", 1)[1].splitlines()[0].strip()


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
    run_id = run_id_from(result.output)
    run_root = tmp_path / "pcie" / ".kb" / "learn_runs" / run_id
    snapshot = json.loads((run_root / "snapshot.json").read_text())
    assert snapshot["run_id"] == run_id
    assert snapshot["goal"] == "Build config notes"
    assert snapshot["selected_source_ids"] == ["manual"]
    assert snapshot["skipped_sources"] == []


def test_learn_profiles_markdown_headings_and_topics(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert run_cli("init", "pcie").exit_code == 0
    source = tmp_path / "manual.md"
    source.write_text("# Configuration Space\n\n## BAR Assignment\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path / "pcie")
    assert run_cli("ingest", str(source)).exit_code == 0

    result = run_cli("learn")

    assert result.exit_code == 0
    run_id = run_id_from(result.output)
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


def test_learn_writes_chunks_claims_pending_notes_and_report(
    tmp_path: Path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    assert run_cli("init", "pcie").exit_code == 0
    source = tmp_path / "manual.md"
    source.write_text("# Configuration Space\nBAR notes\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path / "pcie")
    assert run_cli("ingest", str(source)).exit_code == 0

    result = run_cli("learn", "--goal", "Build config notes")

    assert result.exit_code == 0
    run_id = run_id_from(result.output)
    root = tmp_path / "pcie"
    run_root = root / ".kb" / "learn_runs" / run_id
    chunks = read_jsonl(run_root / "chunks.jsonl")
    claims = read_jsonl(run_root / "claims.jsonl")
    assert chunks[0]["citation"].startswith("kb://source/manual#chunk=")
    assert claims[0]["citations"] == [chunks[0]["citation"]]
    pending_note = (
        root
        / "reviews"
        / "pending_notes"
        / run_id
        / "topic.configuration_space.md"
    )
    assert "kb://source/manual#chunk=" in pending_note.read_text()
    report = root / "reports" / "learn" / run_id / "learn_report.md"
    report_text = report.read_text()
    assert "# Learn Report" in report_text
    assert "Build config notes" in report_text
