from pathlib import Path

import typer

from kb_agent import __version__
from kb_agent.compile import compile_fast
from kb_agent.health import build_health_report
from kb_agent.layout import create_kb, find_kb_root
from kb_agent.sources import ingest_path

app = typer.Typer(
    name="kb",
    help="Local file-based knowledge base manager.",
    no_args_is_help=True,
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"kb-agent {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False,
        "--version",
        help="Show version and exit.",
        callback=_version_callback,
        is_eager=True,
    )
) -> None:
    return None


@app.command()
def init(domain: str) -> None:
    """Create a new domain knowledge base."""
    root = Path(domain)
    try:
        create_kb(root, domain)
    except FileExistsError as exc:
        typer.echo(str(exc))
        raise typer.Exit(code=1)
    typer.echo(f"Initialized knowledge base at {root}")


@app.command()
def ingest(path: Path | None = typer.Argument(None)) -> None:
    """Copy files into sources/ and update .kb/source_index.jsonl."""
    try:
        root = find_kb_root(Path.cwd())
        input_path = root / "inbox" if path is None else path
        records = ingest_path(root, input_path)
    except (FileNotFoundError, ValueError) as exc:
        typer.echo(str(exc))
        raise typer.Exit(code=1)

    typer.echo(f"Ingested {len(records)} source file(s)")
    for record in records:
        typer.echo(f"- {record.source_id}: {record.path}")


@app.command()
def health() -> None:
    """Print a static health summary."""
    try:
        root = find_kb_root(Path.cwd())
        report = build_health_report(root)
    except FileNotFoundError as exc:
        typer.echo(str(exc))
        raise typer.Exit(code=1)

    typer.echo(f"Health: {report.status}")
    typer.echo(f"Sources: {report.source_count}")
    typer.echo(f"Findings: {report.finding_count}")


@app.command(name="compile")
def compile_command(
    fast: bool = typer.Option(False, "--fast", help="Run fast compile checks."),
) -> None:
    """Validate the knowledge base."""
    if not fast:
        typer.echo("Phase 1 supports only: kb compile --fast")
        raise typer.Exit(code=1)

    try:
        root = find_kb_root(Path.cwd())
        result = compile_fast(root)
    except (FileNotFoundError, ValueError) as exc:
        typer.echo(str(exc))
        raise typer.Exit(code=1)

    for finding in result.findings:
        typer.echo(
            f"{finding.severity}: {finding.code}: {finding.path}: {finding.message}"
        )

    if result.passed:
        typer.echo("Compile passed")
        raise typer.Exit(code=0)

    typer.echo("Compile failed")
    raise typer.Exit(code=1)
