from __future__ import annotations

import json
from pathlib import Path

from kb_agent.config import default_config, write_config


CANONICAL_DIRS = [
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
]


def create_kb(root: Path, domain: str) -> None:
    if root.exists() and any(root.iterdir()):
        raise FileExistsError(f"{root} already exists and is not empty")

    root.mkdir(parents=True, exist_ok=True)
    for directory in CANONICAL_DIRS:
        (root / directory).mkdir(parents=True, exist_ok=True)

    write_config(root, default_config(domain))
    (root / "AGENTS.md").write_text(
        f"# AGENTS.md instructions for {domain}\n\n", encoding="utf-8"
    )
    (root / "README.md").write_text(f"# {domain} Knowledge Base\n", encoding="utf-8")
    (root / "notes" / "_index.md").write_text("# Index\n", encoding="utf-8")
    (root / "notes" / "_glossary.md").write_text("# Glossary\n", encoding="utf-8")
    (root / "notes" / "_open_questions.md").write_text(
        "# Open Questions\n", encoding="utf-8"
    )
    (root / ".kb" / "manifest.json").write_text("{}\n", encoding="utf-8")
    (root / ".kb" / "source_index.jsonl").write_text("", encoding="utf-8")
    (root / ".kb" / "compile_state.json").write_text(
        json.dumps({"status": "never_run"}) + "\n", encoding="utf-8"
    )


def find_kb_root(start: Path) -> Path:
    current = start.resolve()
    if current.is_file():
        current = current.parent

    for directory in [current, *current.parents]:
        if (directory / "kb.yaml").is_file() and (directory / ".kb").is_dir():
            return directory

    raise FileNotFoundError("not inside a kb-agent knowledge base")
