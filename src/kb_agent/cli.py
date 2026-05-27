from pathlib import Path

import typer

from kb_agent import __version__
from kb_agent.accept import accept_learn_run
from kb_agent.ask import run_ask
from kb_agent.compile import compile_fast
from kb_agent.graph import export_graph
from kb_agent.health import build_health_report
from kb_agent.layout import create_kb, find_kb_root
from kb_agent.learn import run_learn
from kb_agent.sources import ingest_path

app = typer.Typer(
    name="kb",
    help="Local file-based knowledge base manager.",
    no_args_is_help=True,
)
graph_app = typer.Typer(help="Build and export KB graph artifacts.")
app.add_typer(graph_app, name="graph")


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
def learn(
    goal: str | None = typer.Option(None, "--goal", help="Learning goal for this run."),
    sources: str | None = typer.Option(
        None, "--sources", help="Comma-separated source ids."
    ),
    from_session: Path | None = typer.Option(
        None, "--from-session", help="Learn from a saved ask session."
    ),
) -> None:
    """Run deterministic staged learning."""
    try:
        root = find_kb_root(Path.cwd())
        source_ids = (
            [item.strip() for item in sources.split(",") if item.strip()]
            if sources
            else None
        )
        run = run_learn(
            root, goal=goal, source_ids=source_ids, from_session=from_session
        )
    except (FileNotFoundError, ValueError) as exc:
        typer.echo(str(exc))
        raise typer.Exit(code=1)

    typer.echo(f"Learn run: {run.run_id}")
    typer.echo(f"Selected sources: {len(run.selected_sources)}")


@app.command()
def ask(
    question: str = typer.Argument(...),
    with_: list[Path] | None = typer.Option(
        None, "--with", help="Attach a log, code file, dump, or screenshot."
    ),
    llm: bool = typer.Option(
        False, "--llm", help="Use configured LLM provider for answer generation."
    ),
    model: str | None = typer.Option(
        None, "--model", help="Override LLM model for this answer."
    ),
) -> None:
    """Ask a cited question and save the session."""
    try:
        root = find_kb_root(Path.cwd())
        result = run_ask(root, question, with_ or [], use_llm=llm, model=model)
    except (FileNotFoundError, ValueError) as exc:
        typer.echo(str(exc))
        raise typer.Exit(code=1)

    typer.echo(f"Session: {result.session_path}")
    typer.echo(result.answer)


@app.command()
def accept(run_id: str) -> None:
    """Accept a staged learn run."""
    try:
        root = find_kb_root(Path.cwd())
        result = accept_learn_run(root, run_id)
    except (FileNotFoundError, ValueError) as exc:
        typer.echo(str(exc))
        raise typer.Exit(code=1)

    typer.echo(f"Accepted learn run: {result.run_id}")
    typer.echo(f"Promoted notes: {len(result.promoted_notes)}")
    for note in result.promoted_notes:
        typer.echo(f"- {note}")


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
    typer.echo(f"Graph nodes: {report.graph_node_count}")
    typer.echo(f"Graph edges: {report.graph_edge_count}")
    typer.echo(f"Conflicts: {report.conflict_count}")


@graph_app.command(name="export")
def graph_export() -> None:
    """Export deterministic graph artifacts."""
    try:
        root = find_kb_root(Path.cwd())
        result = export_graph(root)
    except FileNotFoundError as exc:
        typer.echo(str(exc))
        raise typer.Exit(code=1)

    typer.echo(
        f"Graph exported: {len(result.nodes)} node(s), {len(result.edges)} edge(s)"
    )
    typer.echo(f"Report: {result.report_path}")


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
