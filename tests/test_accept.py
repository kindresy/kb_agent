import json
from pathlib import Path

from tests.conftest import run_cli


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def run_id_from(output: str) -> str:
    return output.split("Learn run:", 1)[1].splitlines()[0].strip()


def test_accept_promotes_pending_notes_and_indexes(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert run_cli("init", "pcie").exit_code == 0
    source = tmp_path / "manual.md"
    source.write_text("# Configuration Space\nBAR notes\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path / "pcie")
    assert run_cli("ingest", str(source)).exit_code == 0
    learn = run_cli("learn")
    run_id = run_id_from(learn.output)

    result = run_cli("accept", run_id)

    assert result.exit_code == 0
    assert "Accepted learn run" in result.output
    accepted_note = (
        tmp_path
        / "pcie"
        / "notes"
        / "concepts"
        / "generated"
        / "topic.configuration_space.md"
    )
    assert accepted_note.is_file()
    assert read_jsonl(tmp_path / "pcie" / ".kb" / "topics" / "topics.jsonl")
    assert read_jsonl(tmp_path / "pcie" / ".kb" / "chunks" / "chunks.jsonl")
    assert read_jsonl(tmp_path / "pcie" / ".kb" / "claims" / "claims.jsonl")


def test_accept_refuses_uncited_claim_without_partial_promotion(
    tmp_path: Path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    assert run_cli("init", "pcie").exit_code == 0
    source = tmp_path / "manual.md"
    source.write_text("# Configuration Space\nBAR notes\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path / "pcie")
    assert run_cli("ingest", str(source)).exit_code == 0
    learn = run_cli("learn")
    run_id = run_id_from(learn.output)
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
    accepted_note = (
        tmp_path
        / "pcie"
        / "notes"
        / "concepts"
        / "generated"
        / "topic.configuration_space.md"
    )
    assert not accepted_note.exists()
