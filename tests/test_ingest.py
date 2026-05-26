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


def test_ingest_duplicate_basenames_creates_unique_paths_and_source_ids(
    tmp_path: Path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    assert run_cli("init", "pcie").exit_code == 0
    package = tmp_path / "package"
    first = package / "first"
    second = package / "second"
    first.mkdir(parents=True)
    second.mkdir(parents=True)
    (first / "manual.md").write_text("first manual\n", encoding="utf-8")
    (second / "manual.md").write_text("second manual\n", encoding="utf-8")

    monkeypatch.chdir(tmp_path / "pcie")
    result = run_cli("ingest", str(package))

    assert result.exit_code == 0
    records = read_jsonl(tmp_path / "pcie" / ".kb" / "source_index.jsonl")
    assert {record["path"] for record in records} == {
        "sources/manuals/manual.md",
        "sources/manuals/manual_2.md",
    }
    assert {record["source_id"] for record in records} == {"manual", "manual_2"}


def test_default_ingest_uses_root_inbox_from_nested_directory(
    tmp_path: Path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    assert run_cli("init", "pcie").exit_code == 0
    root = tmp_path / "pcie"
    (root / "inbox" / "boot.log").write_text("link down\n", encoding="utf-8")

    monkeypatch.chdir(root / "notes" / "concepts")
    result = run_cli("ingest")

    assert result.exit_code == 0
    records = read_jsonl(root / ".kb" / "source_index.jsonl")
    assert len(records) == 1
    assert records[0]["source_id"] == "boot"
    assert records[0]["path"] == "sources/logs/boot.log"


def test_ingest_markdown_with_assets_as_single_package(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert run_cli("init", "pcie").exit_code == 0
    package = tmp_path / "pcie_book"
    assets = package / "pcie_book.assets"
    assets.mkdir(parents=True)
    (package / "pcie_book.md").write_text(
        "# PCIe Book\n\n![LTSSM](pcie_book.assets/ltssm.png)\n",
        encoding="utf-8",
    )
    (assets / "ltssm.png").write_bytes(b"png bytes")

    monkeypatch.chdir(tmp_path / "pcie")
    result = run_cli("ingest", str(package))

    assert result.exit_code == 0
    records = read_jsonl(tmp_path / "pcie" / ".kb" / "source_index.jsonl")
    assert len(records) == 1
    record = records[0]
    assert record["source_id"] == "pcie_book"
    assert record["type"] == "manual"
    assert record["kind"] == "package"
    assert record["path"] == "sources/manuals/pcie_book/pcie_book.md"
    assert record["package_path"] == "sources/manuals/pcie_book"
    assert record["assets"] == [
        "sources/manuals/pcie_book/pcie_book.assets/ltssm.png"
    ]
    assert (
        tmp_path / "pcie" / "sources" / "manuals" / "pcie_book" / "pcie_book.md"
    ).is_file()
    assert (
        tmp_path
        / "pcie"
        / "sources"
        / "manuals"
        / "pcie_book"
        / "pcie_book.assets"
        / "ltssm.png"
    ).is_file()


def test_ingest_markdown_file_with_sibling_assets_as_package(
    tmp_path: Path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    assert run_cli("init", "pcie").exit_code == 0
    markdown = tmp_path / "pcie_notes.md"
    assets = tmp_path / "pcie_notes.assets"
    assets.mkdir()
    markdown.write_text("![Diagram](pcie_notes.assets/topology.png)\n", encoding="utf-8")
    (assets / "topology.png").write_bytes(b"png bytes")

    monkeypatch.chdir(tmp_path / "pcie")
    result = run_cli("ingest", str(markdown))

    assert result.exit_code == 0
    records = read_jsonl(tmp_path / "pcie" / ".kb" / "source_index.jsonl")
    assert len(records) == 1
    assert records[0]["kind"] == "package"
    assert records[0]["path"] == "sources/manuals/pcie_notes/pcie_notes.md"
    assert records[0]["assets"] == [
        "sources/manuals/pcie_notes/pcie_notes.assets/topology.png"
    ]


def test_ingest_markdown_with_dash_assets_as_single_package(
    tmp_path: Path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    assert run_cli("init", "pcie").exit_code == 0
    package = tmp_path / "pcie_spec"
    assets = package / "PCI Express Base-assets" / "part_0001" / "images"
    assets.mkdir(parents=True)
    (package / "PCI Express Base.md").write_text(
        "# PCI Express Base\n\n![Figure](PCI Express Base-assets/part_0001/images/fig.jpg)\n",
        encoding="utf-8",
    )
    (assets / "fig.jpg").write_bytes(b"jpg bytes")

    monkeypatch.chdir(tmp_path / "pcie")
    result = run_cli("ingest", str(package))

    assert result.exit_code == 0
    records = read_jsonl(tmp_path / "pcie" / ".kb" / "source_index.jsonl")
    assert len(records) == 1
    assert records[0]["kind"] == "package"
    assert records[0]["path"] == "sources/manuals/pci_express_base/PCI Express Base.md"
    assert records[0]["assets"] == [
        "sources/manuals/pci_express_base/PCI Express Base-assets/part_0001/images/fig.jpg"
    ]


def test_ingest_markdown_referenced_sibling_directory_as_package(
    tmp_path: Path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    assert run_cli("init", "pcie").exit_code == 0
    package = tmp_path / "pci_arch"
    assets = package / "parts" / "part_0001" / "images"
    assets.mkdir(parents=True)
    (package / "pci_express_arch.md").write_text(
        "# PCI Express Architecture\n\n![Topology](parts/part_0001/images/topology.jpg)\n",
        encoding="utf-8",
    )
    (assets / "topology.jpg").write_bytes(b"jpg bytes")

    monkeypatch.chdir(tmp_path / "pcie")
    result = run_cli("ingest", str(package))

    assert result.exit_code == 0
    records = read_jsonl(tmp_path / "pcie" / ".kb" / "source_index.jsonl")
    assert len(records) == 1
    assert records[0]["kind"] == "package"
    assert records[0]["path"] == "sources/manuals/pci_express_arch/pci_express_arch.md"
    assert records[0]["assets"] == [
        "sources/manuals/pci_express_arch/parts/part_0001/images/topology.jpg"
    ]


def test_reingesting_same_file_skips_duplicate_hash(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert run_cli("init", "pcie").exit_code == 0
    source_file = tmp_path / "manual.md"
    source_file.write_text("# Manual\n", encoding="utf-8")

    monkeypatch.chdir(tmp_path / "pcie")
    first = run_cli("ingest", str(source_file))
    second = run_cli("ingest", str(source_file))

    assert first.exit_code == 0
    assert second.exit_code == 0
    assert "Ingested 0 source file(s)" in second.output
    records = read_jsonl(tmp_path / "pcie" / ".kb" / "source_index.jsonl")
    assert len(records) == 1
    assert records[0]["path"] == "sources/manuals/manual.md"


def test_reingesting_same_markdown_package_skips_duplicate_hash(
    tmp_path: Path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    assert run_cli("init", "pcie").exit_code == 0
    markdown = tmp_path / "pcie_notes.md"
    assets = tmp_path / "pcie_notes.assets"
    assets.mkdir()
    markdown.write_text("![Diagram](pcie_notes.assets/topology.png)\n", encoding="utf-8")
    (assets / "topology.png").write_bytes(b"png bytes")

    monkeypatch.chdir(tmp_path / "pcie")
    first = run_cli("ingest", str(markdown))
    second = run_cli("ingest", str(markdown))

    assert first.exit_code == 0
    assert second.exit_code == 0
    assert "Ingested 0 source file(s)" in second.output
    records = read_jsonl(tmp_path / "pcie" / ".kb" / "source_index.jsonl")
    assert len(records) == 1
    assert records[0]["kind"] == "package"
