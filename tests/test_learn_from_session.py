import json
from pathlib import Path

from tests.conftest import run_cli


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def session_path_from(output: str, root: Path) -> Path:
    line = next(line for line in output.splitlines() if line.startswith("Session: "))
    return root / line.split("Session: ", 1)[1]


def test_learn_from_session_creates_staged_run(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert run_cli("init", "pcie").exit_code == 0
    source = tmp_path / "manual.md"
    source.write_text("# Configuration Space\nBAR notes\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path / "pcie")
    assert run_cli("ingest", str(source)).exit_code == 0
    ask = run_cli("ask", "What is Configuration Space?")
    session = session_path_from(ask.output, tmp_path / "pcie")

    learn = run_cli("learn", "--from-session", str(session))

    assert learn.exit_code == 0
    run_id = learn.output.split("Learn run:", 1)[1].splitlines()[0].strip()
    run_root = tmp_path / "pcie" / ".kb" / "learn_runs" / run_id
    snapshot = json.loads((run_root / "snapshot.json").read_text())
    assert snapshot["from_session"].endswith(session.name)
    topics = read_jsonl(run_root / "topics.jsonl")
    assert topics[0]["topic_id"].startswith("topic.session_")
    pending_notes = list(
        (tmp_path / "pcie" / "reviews" / "pending_notes" / run_id).glob("*.md")
    )
    assert len(pending_notes) == 1
    assert "kb://source/manual" in pending_notes[0].read_text()
