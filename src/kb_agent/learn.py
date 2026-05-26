from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

from kb_agent.jsonl import write_jsonl
from kb_agent.sources import SourceRecord, load_source_index


@dataclass(frozen=True)
class LearnRun:
    run_id: str
    goal: str | None
    selected_sources: list[SourceRecord]
    skipped_sources: list[dict[str, str]]


def new_run_id(now: datetime | None = None) -> str:
    timestamp = now or datetime.now()
    return timestamp.strftime("learn_%Y%m%d_%H%M%S")


def select_sources(
    root: Path, source_ids: list[str] | None
) -> tuple[list[SourceRecord], list[dict[str, str]]]:
    records = load_source_index(root)
    if source_ids is None:
        return records, []

    by_id = {record.source_id: record for record in records}
    unknown = [source_id for source_id in source_ids if source_id not in by_id]
    if unknown:
        raise ValueError(f"unknown source id(s): {', '.join(unknown)}")

    selected = [by_id[source_id] for source_id in source_ids]
    selected_ids = set(source_ids)
    skipped = [
        {"source_id": record.source_id, "reason": "not selected"}
        for record in records
        if record.source_id not in selected_ids
    ]
    return selected, skipped


def write_snapshot(root: Path, run: LearnRun) -> None:
    run_root = root / ".kb" / "learn_runs" / run.run_id
    run_root.mkdir(parents=True, exist_ok=True)
    snapshot = {
        "run_id": run.run_id,
        "goal": run.goal,
        "selected_source_ids": [
            record.source_id for record in run.selected_sources
        ],
        "selected_sources": [asdict(record) for record in run.selected_sources],
        "skipped_sources": run.skipped_sources,
    }
    (run_root / "snapshot.json").write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def slug(value: str) -> str:
    result = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return result or "topic"


def source_content_path(root: Path, record: SourceRecord) -> Path:
    return root / record.path


def extract_markdown_headings(path: Path) -> list[str]:
    if not path.is_file() or path.suffix.lower() not in {".md", ".markdown"}:
        return []
    headings: list[str] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        match = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
        if match:
            headings.append(match.group(2).strip())
    return headings


def extract_code_symbols(path: Path) -> list[str]:
    if not path.is_file() or path.suffix.lower() not in {
        ".c",
        ".h",
        ".py",
        ".rs",
        ".go",
    }:
        return []
    symbols: list[str] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        stripped = line.strip()
        match = re.match(r"#\s*define\s+([A-Za-z_][A-Za-z0-9_]*)", stripped)
        if match:
            symbols.append(match.group(1))
            continue
        match = re.match(r"(?:struct|class)\s+([A-Za-z_][A-Za-z0-9_]*)", stripped)
        if match:
            symbols.append(match.group(1))
            continue
        match = re.match(
            r"(?:[A-Za-z_][A-Za-z0-9_*\s]+)\s+([A-Za-z_][A-Za-z0-9_]*)\s*\([^;]*\)\s*\{?",
            stripped,
        )
        if match:
            symbols.append(match.group(1))
    return symbols


def authority_for(record: SourceRecord) -> str:
    if record.type == "spec":
        return "primary"
    if record.type == "code":
        return "implementation"
    if record.type == "log":
        return "debug"
    if record.type in {"manual", "webpage"}:
        return "explanatory"
    return "secondary"


def build_profiles(root: Path, sources: list[SourceRecord]) -> list[dict[str, object]]:
    profiles: list[dict[str, object]] = []
    for record in sources:
        path = source_content_path(root, record)
        headings = extract_markdown_headings(path)
        symbols = extract_code_symbols(path)
        candidates = headings or symbols or [record.title]
        profiles.append(
            {
                "source_id": record.source_id,
                "type": record.type,
                "title": record.title,
                "path": record.path,
                "kind": record.kind,
                "authority": authority_for(record),
                "headings": headings,
                "symbols": symbols,
                "candidate_topics": candidates,
            }
        )
    return profiles


def build_topics(profiles: list[dict[str, object]]) -> list[dict[str, object]]:
    topics: list[dict[str, object]] = []
    used: set[str] = set()
    for profile in profiles:
        for candidate in profile["candidate_topics"]:
            base_id = f"topic.{slug(str(candidate))}"
            topic_id = base_id
            counter = 2
            while topic_id in used:
                topic_id = f"{base_id}_{counter}"
                counter += 1
            used.add(topic_id)
            topics.append(
                {
                    "topic_id": topic_id,
                    "name": str(candidate),
                    "source_id": profile["source_id"],
                    "source_path": profile["path"],
                    "basis": "profile",
                    "priority": "normal",
                    "citations": [f"kb://source/{profile['source_id']}"],
                }
            )
    return topics


def stable_hash(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def build_chunks(root: Path, topics: list[dict[str, object]]) -> list[dict[str, object]]:
    chunks: list[dict[str, object]] = []
    text_suffixes = {".md", ".markdown", ".txt", ".log", ".c", ".h", ".py", ".rs", ".go"}
    for index, topic in enumerate(topics, start=1):
        source_path = root / str(topic["source_path"])
        text = ""
        if source_path.is_file() and source_path.suffix.lower() in text_suffixes:
            text = source_path.read_text(encoding="utf-8", errors="replace")[:1000]
        if not text:
            text = f"File-level evidence for {topic['name']} from {topic['source_id']}."
        chunk_id = f"chunk.{str(topic['topic_id']).removeprefix('topic.')}.{index}"
        chunks.append(
            {
                "chunk_id": chunk_id,
                "source_id": topic["source_id"],
                "source_path": topic["source_path"],
                "topic_id": topic["topic_id"],
                "kind": "deterministic_excerpt",
                "text": text,
                "hash": stable_hash(text),
                "citation": f"kb://source/{topic['source_id']}#chunk={chunk_id}",
            }
        )
    return chunks


def build_claims(
    topics: list[dict[str, object]], chunks: list[dict[str, object]]
) -> list[dict[str, object]]:
    chunk_by_topic = {chunk["topic_id"]: chunk for chunk in chunks}
    claims: list[dict[str, object]] = []
    for index, topic in enumerate(topics, start=1):
        chunk = chunk_by_topic[topic["topic_id"]]
        claims.append(
            {
                "claim_id": f"claim.{str(topic['topic_id']).removeprefix('topic.')}.{index}",
                "topic_id": topic["topic_id"],
                "type": "source_observation",
                "claim": f"The source introduces {topic['name']}.",
                "citations": [chunk["citation"]],
                "confidence": "deterministic",
            }
        )
    return claims


def write_pending_notes(
    root: Path,
    run_id: str,
    topics: list[dict[str, object]],
    claims: list[dict[str, object]],
) -> list[str]:
    pending_root = root / "reviews" / "pending_notes" / run_id
    pending_root.mkdir(parents=True, exist_ok=True)
    claims_by_topic = {claim["topic_id"]: claim for claim in claims}
    paths: list[str] = []
    for topic in topics:
        claim = claims_by_topic[topic["topic_id"]]
        path = pending_root / f"{topic['topic_id']}.md"
        path.write_text(
            "\n".join(
                [
                    f"# {topic['name']}",
                    "",
                    "## One-Sentence Conclusion",
                    "",
                    str(claim["claim"]),
                    "",
                    "## What Was Found",
                    "",
                    f"`kb learn` identified this topic from `{topic['source_id']}`.",
                    "",
                    "## Evidence",
                    "",
                    f"- {claim['citations'][0]}",
                    "",
                    "## Open Questions",
                    "",
                    "- Needs human review before becoming authoritative.",
                    "",
                    "## Related Sources",
                    "",
                    f"- kb://source/{topic['source_id']}",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        paths.append(path.relative_to(root).as_posix())
    return paths


def write_learn_report(
    root: Path,
    run: LearnRun,
    profiles: list[dict[str, object]],
    topics: list[dict[str, object]],
    chunks: list[dict[str, object]],
    claims: list[dict[str, object]],
    pending_notes: list[str],
) -> None:
    report_path = root / "reports" / "learn" / run.run_id / "learn_report.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        "\n".join(
            [
                "# Learn Report",
                "",
                f"Run: `{run.run_id}`",
                f"Goal: {run.goal or 'not specified'}",
                "",
                "## Selected Sources",
                *[
                    f"- {record.source_id}: {record.path}"
                    for record in run.selected_sources
                ],
                "",
                "## Generated Artifacts",
                "",
                f"- Profiles: {len(profiles)}",
                f"- Topics: {len(topics)}",
                f"- Chunks: {len(chunks)}",
                f"- Claims: {len(claims)}",
                f"- Pending notes: {len(pending_notes)}",
                "",
                "## Pending Notes",
                *[f"- {path}" for path in pending_notes],
                "",
                "## Next Suggested Command",
                "",
                f"`kb accept {run.run_id}`",
                "",
            ]
        ),
        encoding="utf-8",
    )


def run_learn(
    root: Path, goal: str | None = None, source_ids: list[str] | None = None
) -> LearnRun:
    selected, skipped = select_sources(root, source_ids)
    run = LearnRun(new_run_id(), goal, selected, skipped)
    run_root = root / ".kb" / "learn_runs" / run.run_id
    write_snapshot(root, run)
    profiles = build_profiles(root, selected)
    topics = build_topics(profiles)
    chunks = build_chunks(root, topics)
    claims = build_claims(topics, chunks)
    write_jsonl(run_root / "profiles.jsonl", profiles)
    write_jsonl(run_root / "topics.jsonl", topics)
    write_jsonl(run_root / "chunks.jsonl", chunks)
    write_jsonl(run_root / "claims.jsonl", claims)
    pending_notes = write_pending_notes(root, run.run_id, topics, claims)
    write_learn_report(root, run, profiles, topics, chunks, claims, pending_notes)
    return run
