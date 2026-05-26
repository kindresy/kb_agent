from tests.conftest import run_cli


def test_cli_version_command():
    result = run_cli("--version")

    assert result.exit_code == 0
    assert "kb-agent" in result.stdout
