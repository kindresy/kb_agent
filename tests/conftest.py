from typer.testing import CliRunner

from kb_agent.cli import app


def run_cli(*args: str):
    runner = CliRunner()
    return runner.invoke(app, list(args))
