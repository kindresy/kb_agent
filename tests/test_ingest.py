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
    assert (
        tmp_path / "pcie" / "sources" / "manuals" / "manual.md"
    ).read_text() == "# Controller Manual\nBAR config\n"


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
