from __future__ import annotations

import hashlib
import json
import re
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from kb_agent.jsonl import read_jsonl
from kb_agent.markdown import extract_kb_source_refs
from kb_agent.sources import load_source_index


@dataclass(frozen=True)
class AskResult:
    session_id: str
    session_path: str
    answer: str


DEBUG_WORDS = {
    "fail",
    "failure",
    "error",
    "stuck",
    "assigned",
    "enumerate",
    "bar0",
    "ltssm",
    "timeout",
    "log",
    "trace",
    "dump",
    "register",
}


def new_session_id(now: datetime | None = None) -> str:
    timestamp = now or datetime.now()
    return timestamp.strftime("ask_%Y%m%d_%H%M%S")


def allocate_session_dir(root: Path, parent: str) -> tuple[str, Path]:
    base_id = new_session_id()
    base_dir = root / "sessions" / parent / base_id
    if not base_dir.exists():
        return base_id, base_dir
    for counter in range(2, 10_000):
        session_id = f"{base_id}_{counter}"
        session_dir = root / "sessions" / parent / session_id
        if not session_dir.exists():
            return session_id, session_dir
    raise ValueError(f"could not allocate ask session id for {base_id}")


def tokens(text: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9_]+", text.lower()) if len(token) > 1}


def classify_intent(question: str, has_attachments: bool) -> str:
    question_tokens = tokens(question)
    if has_attachments or question_tokens & DEBUG_WORDS or "why was" in question.lower():
        return "debug"
    if question_tokens & {"code", "function", "struct", "driver", "source"}:
        return "code_reading"
    if question_tokens & {"compare", "difference", "versus", "vs"}:
        return "comparison"
    if question_tokens & {"design", "architecture", "integrate", "integration"}:
        return "design"
    if question_tokens & {"experiment", "validate", "measure", "test"}:
        return "experiment"
    return "concept"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def validate_attachments(paths: list[Path]) -> None:
    missing = [path for path in paths if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"attachment does not exist: {missing[0]}")


def copy_attachments(root: Path, session_dir: Path, paths: list[Path]) -> list[dict[str, object]]:
    if not paths:
        return []
    destination_root = session_dir / "attachments"
    destination_root.mkdir(parents=True, exist_ok=True)
    attachments: list[dict[str, object]] = []
    for path in paths:
        destination = destination_root / path.name
        shutil.copy2(path, destination)
        attachments.append(
            {
                "original_path": str(path),
                "copied_path": destination.relative_to(root).as_posix(),
                "type": path.suffix.lower().lstrip(".") or "unknown",
                "size": path.stat().st_size,
                "hash": sha256_file(path),
            }
        )
    return attachments


def overlaps(question_tokens: set[str], text: str) -> bool:
    return bool(question_tokens & tokens(text))


def retrieve_evidence(
    root: Path, question: str, attachments: list[dict[str, object]]
) -> list[dict[str, str]]:
    question_tokens = tokens(question)
    evidence: list[dict[str, str]] = []

    for claim_path in sorted((root / ".kb" / "claims").rglob("*.jsonl")):
        for claim in read_jsonl(claim_path):
            claim_text = " ".join(
                str(claim.get(key, "")) for key in ["claim_id", "topic_id", "claim"]
            )
            if overlaps(question_tokens, claim_text):
                citations = claim.get("citations") or []
                evidence.append(
                    {
                        "type": "accepted_claim",
                        "ref": str(claim.get("claim_id", "<missing>")),
                        "why_relevant": "claim text matched question terms",
                        "citation": str(citations[0]) if citations else "",
                    }
                )

    notes_root = root / "notes"
    if notes_root.is_dir():
        for note in sorted(notes_root.rglob("*.md")):
            text = note.read_text(encoding="utf-8", errors="replace")
            if overlaps(question_tokens, f"{note.name} {text}"):
                refs = extract_kb_source_refs(text)
                evidence.append(
                    {
                        "type": "accepted_note",
                        "ref": note.relative_to(root).as_posix(),
                        "why_relevant": "note text matched question terms",
                        "citation": f"kb://source/{refs[0]}" if refs else "",
                    }
                )

    for chunk_path in sorted((root / ".kb" / "chunks").rglob("*.jsonl")):
        for chunk in read_jsonl(chunk_path):
            chunk_text = " ".join(
                str(chunk.get(key, "")) for key in ["chunk_id", "topic_id", "text"]
            )
            if overlaps(question_tokens, chunk_text):
                evidence.append(
                    {
                        "type": "source_chunk",
                        "ref": str(chunk.get("citation", "")),
                        "why_relevant": "chunk text matched question terms",
                    }
                )

    source_records = load_source_index(root)
    for record in source_records:
        if overlaps(question_tokens, f"{record.source_id} {record.title} {record.path}"):
            evidence.append(
                {
                    "type": "source",
                    "ref": f"kb://source/{record.source_id}",
                    "why_relevant": "source metadata matched question terms",
                }
            )

    evidence_source_ids: set[str] = set()
    for item in evidence:
        for value in [item.get("ref", ""), item.get("citation", "")]:
            evidence_source_ids.update(extract_kb_source_refs(value))
    existing_source_refs = {
        item["ref"] for item in evidence if item.get("type") == "source"
    }
    for record in source_records:
        ref = f"kb://source/{record.source_id}"
        if record.source_id in evidence_source_ids and ref not in existing_source_refs:
            evidence.append(
                {
                    "type": "source",
                    "ref": ref,
                    "why_relevant": "source referenced by retrieved evidence",
                }
            )

    for attachment in attachments:
        if overlaps(question_tokens, str(attachment["original_path"])):
            evidence.append(
                {
                    "type": "attachment",
                    "ref": str(attachment["copied_path"]),
                    "why_relevant": "attachment name matched question terms",
                }
            )

    if not evidence and source_records:
        first = source_records[0]
        evidence.append(
            {
                "type": "source",
                "ref": f"kb://source/{first.source_id}",
                "why_relevant": "fallback source evidence",
            }
        )
    return evidence


def primary_citations(evidence: list[dict[str, str]]) -> list[str]:
    citations: list[str] = []
    for item in evidence:
        for candidate in [item.get("citation", ""), item.get("ref", "")]:
            if extract_kb_source_refs(candidate):
                citations.append(candidate)
                break
    return citations


def render_answer(question: str, intent: str, evidence: list[dict[str, str]]) -> str:
    citations = primary_citations(evidence)
    citation_text = citations[0] if citations else "No source citation available."
    lines = [
        "# Answer",
        "",
        "## Direct Conclusion",
        "",
        f"Deterministic answer for: {question}",
        "",
        "## Background Mechanism",
        "",
        "This local skeleton uses accepted notes, claims, chunks, sources, and attachments as evidence.",
        "",
        "## Mapping to Your Project",
        "",
        "Review the evidence list and attached files for project-specific context.",
        "",
        "## Evidence",
        "",
    ]
    lines.extend(f"- {item['ref']} ({item['why_relevant']})" for item in evidence)
    lines.extend(
        [
            "",
            "## Debug Path / Next Experiment",
            "",
        ]
    )
    if intent == "debug":
        lines.extend(
            [
                "- Restate the symptom and preserve logs/register dumps.",
                "- Check the cited source and accepted notes first.",
                "- Validate reset, clock, enumeration, and driver assignment paths.",
                "- Record missing observations before drawing a conclusion.",
            ]
        )
    else:
        lines.append("- Use the cited sources to deepen this topic through `kb learn`.")
    lines.extend(
        [
            "",
            "## Uncertainty",
            "",
            f"Confidence: deterministic skeleton. Primary citation: {citation_text}",
            "",
        ]
    )
    return "\n".join(lines)


def write_feedback_plan(root: Path, session_dir: Path) -> None:
    session_path = session_dir.relative_to(root).as_posix()
    (session_dir / "feedback_plan.md").write_text(
        "\n".join(
            [
                "# Feedback Plan",
                "",
                "## Candidate Learning Input",
                "",
                f"- {session_path}",
                "",
                "## Suggested Command",
                "",
                f"`kb learn --from-session {session_path}`",
                "",
            ]
        ),
        encoding="utf-8",
    )


def run_ask(root: Path, question: str, attachment_paths: list[Path] | None = None) -> AskResult:
    attachment_paths = attachment_paths or []
    validate_attachments(attachment_paths)
    intent = classify_intent(question, bool(attachment_paths))
    session_parent = "debug_cases" if intent == "debug" else "questions"
    session_id, session_dir = allocate_session_dir(root, session_parent)
    session_dir.mkdir(parents=True, exist_ok=False)

    attachments = copy_attachments(root, session_dir, attachment_paths)
    evidence = retrieve_evidence(root, question, attachments)
    answer = render_answer(question, intent, evidence)

    (session_dir / "question.md").write_text(
        f"# Question\n\n{question}\n\nIntent: `{intent}`\n", encoding="utf-8"
    )
    (session_dir / "evidence_pack.json").write_text(
        json.dumps(
            {
                "session_id": session_id,
                "question": question,
                "intent": intent,
                "attachments": attachments,
                "evidence": evidence,
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    (session_dir / "answer.md").write_text(answer, encoding="utf-8")
    write_feedback_plan(root, session_dir)
    return AskResult(session_id, session_dir.relative_to(root).as_posix(), answer)
