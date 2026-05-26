from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from kb_agent.layout import CANONICAL_DIRS
from kb_agent.markdown import extract_kb_source_refs, extract_markdown_links
from kb_agent.sources import load_source_index


@dataclass(frozen=True)
class Finding:
    severity: str
    code: str
    path: str
    message: str


@dataclass(frozen=True)
class CompileResult:
    status: str
    findings: list[Finding]

    @property
    def passed(self) -> bool:
        return self.status == "passed"


def markdown_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for directory in ["notes", "sessions", "reviews"]:
        search_root = root / directory
        if search_root.is_dir():
            files.extend(search_root.rglob("*.md"))
    return sorted(files)


def _is_inside_root(root: Path, path: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def check_structure(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for path in ["kb.yaml", "AGENTS.md", "README.md"]:
        if not (root / path).is_file():
            findings.append(
                Finding("error", "missing_required_file", path, "missing required file")
            )

    for path in CANONICAL_DIRS:
        if not (root / path).is_dir():
            findings.append(
                Finding(
                    "error",
                    "missing_canonical_dir",
                    path,
                    "missing canonical directory",
                )
            )

    return findings


def check_source_files(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for record in load_source_index(root):
        source_path = Path(record.path)
        if source_path.is_absolute():
            findings.append(
                Finding(
                    "error",
                    "absolute_source_path",
                    record.path,
                    f"source path must be relative to knowledge base: {record.source_id}",
                )
            )
            continue

        resolved_path = root / source_path
        if not _is_inside_root(root, resolved_path):
            findings.append(
                Finding(
                    "error",
                    "source_path_outside_kb",
                    record.path,
                    f"source path escapes knowledge base: {record.source_id}",
                )
            )
        elif not resolved_path.is_file():
            findings.append(
                Finding(
                    "error",
                    "missing_source_file",
                    record.path,
                    f"indexed source file does not exist: {record.source_id}",
                )
            )
    return findings


def check_citations(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    source_ids = {record.source_id for record in load_source_index(root)}

    for path in markdown_files(root):
        text = path.read_text(encoding="utf-8")
        relative_path = path.relative_to(root).as_posix()
        for source_id in extract_kb_source_refs(text):
            if source_id not in source_ids:
                findings.append(
                    Finding(
                        "error",
                        "missing_source_reference",
                        relative_path,
                        f"missing source reference: {source_id}",
                    )
                )

    return findings


def check_markdown_links(root: Path) -> list[Finding]:
    findings: list[Finding] = []

    for path in markdown_files(root):
        text = path.read_text(encoding="utf-8")
        relative_path = path.relative_to(root).as_posix()
        for link in extract_markdown_links(text):
            target_path = path.parent / link
            if not _is_inside_root(root, target_path):
                findings.append(
                    Finding(
                        "error",
                        "external_markdown_link",
                        relative_path,
                        f"markdown link escapes knowledge base: {link}",
                    )
                )
            elif not target_path.exists():
                findings.append(
                    Finding(
                        "error",
                        "broken_markdown_link",
                        relative_path,
                        f"broken markdown link: {link}",
                    )
                )

    return findings


def compile_fast(root: Path) -> CompileResult:
    findings = [
        *check_structure(root),
        *check_source_files(root),
        *check_citations(root),
        *check_markdown_links(root),
    ]
    status = (
        "failed"
        if any(finding.severity == "error" for finding in findings)
        else "passed"
    )
    result = CompileResult(status, findings)
    write_compile_state(root, result)
    return result


def write_compile_state(root: Path, result: CompileResult) -> None:
    state_path = root / ".kb" / "compile_state.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state = {
        "status": result.status,
        "findings": [asdict(finding) for finding in result.findings],
    }
    state_path.write_text(
        json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
