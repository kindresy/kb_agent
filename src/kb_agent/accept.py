from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from kb_agent.compile import compile_fast
from kb_agent.conflicts import (
    detect_claim_conflicts,
    load_accepted_claims,
    load_run_claims,
    write_conflict_artifacts,
)
from kb_agent.jsonl import append_jsonl, read_jsonl
from kb_agent.markdown import extract_kb_source_refs
from kb_agent.sources import load_source_index


@dataclass(frozen=True)
class AcceptResult:
    run_id: str
    promoted_notes: list[str]


def validate_run_claims(root: Path, run_id: str) -> list[str]:
    errors: list[str] = []
    source_ids = {record.source_id for record in load_source_index(root)}
    claims_path = root / ".kb" / "learn_runs" / run_id / "claims.jsonl"
    for claim in read_jsonl(claims_path):
        claim_id = str(claim.get("claim_id", "<missing>"))
        citations = claim.get("citations") or []
        if not citations:
            errors.append(f"claim has no citation: {claim_id}")
            continue
        for citation in citations:
            refs = extract_kb_source_refs(str(citation))
            if not refs:
                errors.append(f"claim citation is not a kb source ref: {claim_id}")
            for source_id in refs:
                if source_id not in source_ids:
                    errors.append(f"claim references missing source: {source_id}")
    return errors


def accept_learn_run(root: Path, run_id: str) -> AcceptResult:
    run_root = root / ".kb" / "learn_runs" / run_id
    pending_root = root / "reviews" / "pending_notes" / run_id
    if not run_root.is_dir():
        raise FileNotFoundError(f"learn run not found: {run_id}")
    if not pending_root.is_dir():
        raise FileNotFoundError(f"pending notes not found for learn run: {run_id}")

    errors = validate_run_claims(root, run_id)
    if errors:
        raise ValueError("\n".join(errors))

    conflicts = detect_claim_conflicts(
        load_accepted_claims(root), load_run_claims(root, run_id), run_id
    )
    if conflicts:
        report_path = write_conflict_artifacts(root, run_id, conflicts)
        raise ValueError(f"claim conflict report written: {report_path}")

    compile_result = compile_fast(root)
    if not compile_result.passed:
        messages = [
            f"{finding.code}: {finding.path}: {finding.message}"
            for finding in compile_result.findings
        ]
        raise ValueError("compile gate failed before accept:\n" + "\n".join(messages))

    accepted_root = root / "notes" / "concepts" / "generated"
    accepted_root.mkdir(parents=True, exist_ok=True)
    promoted: list[str] = []
    for note in sorted(pending_root.glob("*.md")):
        destination = accepted_root / note.name
        shutil.copy2(note, destination)
        promoted.append(destination.relative_to(root).as_posix())

    append_jsonl(
        root / ".kb" / "topics" / "topics.jsonl",
        read_jsonl(run_root / "topics.jsonl"),
    )
    append_jsonl(
        root / ".kb" / "chunks" / "chunks.jsonl",
        read_jsonl(run_root / "chunks.jsonl"),
    )
    append_jsonl(
        root / ".kb" / "claims" / "claims.jsonl",
        read_jsonl(run_root / "claims.jsonl"),
    )
    return AcceptResult(run_id, promoted)
