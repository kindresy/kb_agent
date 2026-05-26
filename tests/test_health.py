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
