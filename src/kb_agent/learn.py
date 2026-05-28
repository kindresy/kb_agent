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
    from_session: str | None = None


def new_run_id(now: datetime | None = None) -> str:
    timestamp = now or datetime.now()
    return timestamp.strftime("learn_%Y%m%d_%H%M%S")


def allocate_run_id(root: Path) -> str:
    base_id = new_run_id()
    if not (root / ".kb" / "learn_runs" / base_id).exists():
        return base_id
    for counter in range(2, 10_000):
        candidate = f"{base_id}_{counter}"
        if not (root / ".kb" / "learn_runs" / candidate).exists():
            return candidate
    raise ValueError(f"could not allocate learn run id for {base_id}")


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
        "from_session": run.from_session,
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


def markdown_excerpt(text: str, limit: int = 2000) -> str:
    normalized = text.strip()
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 3].rstrip() + "..."


def write_llm_session_pending_note(
    root: Path,
    run_id: str,
    topic: dict[str, object],
    claim: dict[str, object],
    session_dir: Path,
    question_text: str,
    answer_text: str,
    evidence_pack: dict[str, object],
) -> list[str]:
    pending_root = root / "reviews" / "pending_notes" / run_id
    pending_root.mkdir(parents=True, exist_ok=True)
    path = pending_root / f"{topic['topic_id']}.md"
    prompt_evidence = evidence_pack.get("prompt_evidence", [])
    evidence_lines: list[str] = []
    if isinstance(prompt_evidence, list):
        for item in prompt_evidence:
            if not isinstance(item, dict):
                continue
            ref = str(item.get("ref") or item.get("citation") or "<missing ref>")
            score = item.get("score", "n/a")
            why = str(item.get("why_relevant", "selected prompt evidence"))
            evidence_lines.append(f"- {ref} (score: {score}; {why})")
    if not evidence_lines:
        evidence_lines.append(f"- {claim['citations'][0]}")

    path.write_text(
        "\n".join(
            [
                f"# {topic['name']}",
                "",
                "## Review Status",
                "",
                "- Source: ask session",
                "- Answer mode: `llm`",
                "- Confidence: `llm_session_unverified`",
                "- This note is staged for human review. The LLM answer is not accepted source truth until `kb accept`.",
                "",
                "## Original Question",
                "",
                markdown_excerpt(question_text),
                "",
                "## Unverified LLM Answer Excerpt",
                "",
                markdown_excerpt(answer_text),
                "",
                "## Prompt Evidence Used",
                "",
                *evidence_lines,
                "",
                "## Required Human Checks",
                "",
                "- Verify the answer against the cited source material.",
                "- Remove or edit unsupported LLM statements before accepting.",
                "- Run `kb compile --fast` after acceptance.",
                "",
                "## Evidence",
                "",
                f"- {claim['citations'][0]}",
                "",
                "## Related Session",
                "",
                f"- {session_dir.relative_to(root).as_posix()}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return [path.relative_to(root).as_posix()]


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


def resolve_session_path(root: Path, session_path: Path) -> Path:
    resolved = session_path if session_path.is_absolute() else root / session_path
    if not resolved.is_dir():
        raise FileNotFoundError(f"session not found: {session_path}")
    try:
        resolved.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"session path escapes knowledge base: {session_path}") from exc
    return resolved


def source_records_from_session(root: Path, session_dir: Path) -> list[SourceRecord]:
    evidence_path = session_dir / "evidence_pack.json"
    if not evidence_path.is_file():
        return []
    evidence_pack = json.loads(evidence_path.read_text(encoding="utf-8"))
    refs: list[str] = []
    for item in evidence_pack.get("evidence", []):
        for field in ["ref", "citation"]:
            refs.extend(extract_source_ids(str(item.get(field, ""))))
    by_id = {record.source_id: record for record in load_source_index(root)}
    selected: list[SourceRecord] = []
    for source_id in refs:
        if source_id in by_id and by_id[source_id] not in selected:
            selected.append(by_id[source_id])
    return selected


def extract_source_ids(text: str) -> list[str]:
    return re.findall(r"kb://source/([^#)\s]+)", text)


def run_learn_from_session(root: Path, session_path: Path, goal: str | None) -> LearnRun:
    session_dir = resolve_session_path(root, session_path)
    selected = source_records_from_session(root, session_dir)
    run = LearnRun(
        allocate_run_id(root),
        goal or f"Learn from session {session_dir.name}",
        selected,
        [],
        session_dir.relative_to(root).as_posix(),
    )
    run_root = root / ".kb" / "learn_runs" / run.run_id
    write_snapshot(root, run)

    question_path = session_dir / "question.md"
    answer_path = session_dir / "answer.md"
    evidence_path = session_dir / "evidence_pack.json"
    question_text = question_path.read_text(encoding="utf-8", errors="replace")
    answer_text = answer_path.read_text(encoding="utf-8", errors="replace")
    evidence_pack = json.loads(evidence_path.read_text(encoding="utf-8"))
    answer_mode = evidence_pack.get("answer_mode", "deterministic")
    source_id = selected[0].source_id if selected else "session"
    citation = f"kb://source/{source_id}"
    for item in evidence_pack.get("evidence", []):
        refs = extract_source_ids(str(item.get("ref", ""))) or extract_source_ids(
            str(item.get("citation", ""))
        )
        if refs:
            citation = f"kb://source/{refs[0]}"
            break

    topic_id = f"topic.session_{slug(session_dir.name)}"
    topic = {
        "topic_id": topic_id,
        "name": f"Session {session_dir.name}",
        "source_id": source_id,
        "source_path": session_dir.relative_to(root).as_posix(),
        "basis": "session",
        "priority": "normal",
        "citations": [citation],
    }
    if answer_mode == "llm":
        chunk_kind = "session_question_and_evidence"
        chunk_text = (
            question_text
            + "\n\nEvidence:\n"
            + json.dumps(
                evidence_pack.get("evidence", []),
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
        )[:1000]
        confidence = "llm_session_unverified"
    else:
        chunk_kind = "session_summary"
        chunk_text = f"{question_text}\n\n{answer_text}"[:1000]
        confidence = "deterministic"
    chunk = {
        "chunk_id": f"chunk.session_{slug(session_dir.name)}.1",
        "source_id": source_id,
        "source_path": session_dir.relative_to(root).as_posix(),
        "topic_id": topic_id,
        "kind": chunk_kind,
        "text": chunk_text,
        "hash": stable_hash(chunk_text),
        "citation": citation,
        "answer_mode": answer_mode,
        "llm_provider": evidence_pack.get("llm_provider"),
        "llm_model": evidence_pack.get("llm_model"),
    }
    claim = {
        "claim_id": f"claim.session_{slug(session_dir.name)}.1",
        "topic_id": topic_id,
        "type": "session_observation",
        "claim": f"The saved ask session {session_dir.name} contains reusable learning material.",
        "citations": [citation],
        "confidence": confidence,
        "answer_mode": answer_mode,
    }
    profile = {
        "source_id": source_id,
        "type": "session",
        "title": f"Session {session_dir.name}",
        "path": session_dir.relative_to(root).as_posix(),
        "kind": "session",
        "authority": "debug",
        "headings": [f"Session {session_dir.name}"],
        "symbols": [],
        "candidate_topics": [f"Session {session_dir.name}"],
    }
    write_jsonl(run_root / "profiles.jsonl", [profile])
    write_jsonl(run_root / "topics.jsonl", [topic])
    write_jsonl(run_root / "chunks.jsonl", [chunk])
    write_jsonl(run_root / "claims.jsonl", [claim])
    if answer_mode == "llm":
        pending_notes = write_llm_session_pending_note(
            root,
            run.run_id,
            topic,
            claim,
            session_dir,
            question_text,
            answer_text,
            evidence_pack,
        )
    else:
        pending_notes = write_pending_notes(root, run.run_id, [topic], [claim])
    write_learn_report(root, run, [profile], [topic], [chunk], [claim], pending_notes)
    return run


def run_learn(
    root: Path,
    goal: str | None = None,
    source_ids: list[str] | None = None,
    from_session: Path | None = None,
) -> LearnRun:
    if from_session is not None:
        return run_learn_from_session(root, from_session, goal)
    selected, skipped = select_sources(root, source_ids)
    run = LearnRun(allocate_run_id(root), goal, selected, skipped)
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
