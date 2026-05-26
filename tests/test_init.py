from pathlib import Path

import pytest
import yaml

from kb_agent.layout import find_kb_root
from tests.conftest import run_cli


def test_cli_version_command():
    result = run_cli("--version")

    assert result.exit_code == 0
    assert "kb-agent" in result.stdout


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
        "hooks",
        "tools",
        ".kb/chunks",
        ".kb/topics",
        ".kb/claims",
        ".kb/citations",
        ".kb/graph",
        ".kb/embeddings",
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


def test_init_refuses_existing_file_target(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "pcie").write_text("already here\n")

    result = run_cli("init", "pcie")

    assert result.exit_code != 0
    assert "already exists and is not empty" in result.stdout


def test_find_kb_root_from_root(tmp_path: Path):
    root = tmp_path / "pcie"
    result = run_cli("init", str(root))

    assert result.exit_code == 0
    assert find_kb_root(root) == root


def test_find_kb_root_from_nested_directory(tmp_path: Path):
    root = tmp_path / "pcie"
    result = run_cli("init", str(root))

    assert result.exit_code == 0
    assert find_kb_root(root / "notes" / "concepts") == root


def test_find_kb_root_raises_outside_kb(tmp_path: Path):
    with pytest.raises(
        FileNotFoundError, match="not inside a kb-agent knowledge base"
    ):
        find_kb_root(tmp_path)
