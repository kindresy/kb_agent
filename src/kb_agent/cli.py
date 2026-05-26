from pathlib import Path

import typer

from kb_agent import __version__
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
def ingest(path: Path = typer.Argument(Path("inbox"))) -> None:
    """Copy files into sources/ and update .kb/source_index.jsonl."""
    try:
        root = find_kb_root(Path.cwd())
        records = ingest_path(root, path)
    except (FileNotFoundError, ValueError) as exc:
        typer.echo(str(exc))
        raise typer.Exit(code=1)

    typer.echo(f"Ingested {len(records)} source file(s)")
    for record in records:
        typer.echo(f"- {record.source_id}: {record.path}")
