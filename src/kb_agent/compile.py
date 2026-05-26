from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from kb_agent.jsonl import read_jsonl
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


def check_source_packages(root: Path) -> list[Finding]:
    findings: list[Finding] = []

    for record in load_source_index(root):
        if record.kind != "package":
            continue

        if record.package_path is None:
            findings.append(
                Finding(
                    "error",
                    "missing_package_path",
                    record.path,
                    f"package source is missing package_path: {record.source_id}",
                )
            )
            continue

        package_path = Path(record.package_path)
        if package_path.is_absolute():
            findings.append(
                Finding(
                    "error",
                    "absolute_package_path",
                    record.package_path,
                    f"package path must be relative to knowledge base: {record.source_id}",
                )
            )
            continue

        resolved_package = root / package_path
        if not _is_inside_root(root, resolved_package):
            findings.append(
                Finding(
                    "error",
                    "package_path_outside_kb",
                    record.package_path,
                    f"package path escapes knowledge base: {record.source_id}",
                )
            )
            continue
        if not resolved_package.is_dir():
            findings.append(
                Finding(
                    "error",
                    "missing_package_directory",
                    record.package_path,
                    f"package directory does not exist: {record.source_id}",
                )
            )
            continue

        source_path = root / record.path
        if not _is_inside_root(resolved_package, source_path):
            findings.append(
                Finding(
                    "error",
                    "package_source_outside_package",
                    record.path,
                    f"package source file is outside package: {record.source_id}",
                )
            )
        if not source_path.is_file():
            continue

        for asset in record.assets or []:
            asset_path = Path(asset)
            if asset_path.is_absolute():
                findings.append(
                    Finding(
                        "error",
                        "absolute_package_asset",
                        asset,
                        f"package asset path must be relative: {record.source_id}",
                    )
                )
                continue
            resolved_asset = root / asset_path
            if not _is_inside_root(root, resolved_asset):
                findings.append(
                    Finding(
                        "error",
                        "package_asset_outside_kb",
                        asset,
                        f"package asset escapes knowledge base: {record.source_id}",
                    )
                )
            elif not _is_inside_root(resolved_package, resolved_asset):
                findings.append(
                    Finding(
                        "error",
                        "package_asset_outside_package",
                        asset,
                        f"package asset escapes package: {record.source_id}",
                    )
                )
            elif not resolved_asset.is_file():
                findings.append(
                    Finding(
                        "error",
                        "missing_package_asset",
                        asset,
                        f"missing package asset: {record.source_id}",
                    )
                )

        text = source_path.read_text(encoding="utf-8")
        for link in extract_markdown_links(text):
            target_path = source_path.parent / link
            if not _is_inside_root(root, target_path):
                findings.append(
                    Finding(
                        "error",
                        "package_markdown_link_outside_kb",
                        record.path,
                        f"package markdown link escapes knowledge base: {link}",
                    )
                )
            elif not _is_inside_root(resolved_package, target_path):
                findings.append(
                    Finding(
                        "error",
                        "package_markdown_link_outside_package",
                        record.path,
                        f"package markdown link escapes package: {link}",
                    )
                )
            elif not target_path.exists():
                findings.append(
                    Finding(
                        "error",
                        "broken_package_markdown_link",
                        record.path,
                        f"broken package markdown link: {link}",
                    )
                )

    return findings


def check_claims(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    source_ids = {record.source_id for record in load_source_index(root)}
    claims_root = root / ".kb" / "claims"
    if not claims_root.is_dir():
        return findings

    for path in sorted(claims_root.rglob("*.jsonl")):
        relative_path = path.relative_to(root).as_posix()
        for claim in read_jsonl(path):
            claim_id = str(claim.get("claim_id", "<missing>"))
            citations = claim.get("citations") or []
            if not citations:
                findings.append(
                    Finding(
                        "error",
                        "claim_missing_citation",
                        relative_path,
                        f"claim has no citation: {claim_id}",
                    )
                )
                continue
            for citation in citations:
                refs = extract_kb_source_refs(str(citation))
                if not refs:
                    findings.append(
                        Finding(
                            "error",
                            "claim_invalid_citation",
                            relative_path,
                            f"claim citation is not a kb source ref: {claim_id}",
                        )
                    )
                for source_id in refs:
                    if source_id not in source_ids:
                        findings.append(
                            Finding(
                                "error",
                                "claim_missing_source_reference",
                                relative_path,
                                f"claim references missing source: {source_id}",
                            )
                        )
    return findings


def compile_fast(root: Path) -> CompileResult:
    findings = [
        *check_structure(root),
        *check_source_files(root),
        *check_source_packages(root),
        *check_citations(root),
        *check_markdown_links(root),
        *check_claims(root),
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
