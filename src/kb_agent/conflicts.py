from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from pathlib import Path

from kb_agent.jsonl import read_jsonl, write_jsonl

NEGATION_WORDS = {"not", "no", "never", "without", "disabled", "unsupported", "cannot", "cant"}
AUXILIARY_WORDS = {"do", "does", "did"}
REQUIREMENT_MODALS = {"must", "required", "shall", "always"}
PROHIBITION_PATTERNS = {"must not", "shall not", "forbidden", "prohibited", "never"}


@dataclass(frozen=True)
class ClaimConflict:
    conflict_id: str
    rule: str
    severity: str
    topic_id: str
    accepted_claim_id: str
    candidate_claim_id: str
    accepted_claim: str
    candidate_claim: str
    accepted_citations: list[str]
    candidate_citations: list[str]
    message: str


def tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9_]+", text.lower().replace("can't", "cannot"))


def has_phrase(text: str, phrase: str) -> bool:
    words = [re.escape(word) for word in phrase.lower().split()]
    pattern = r"(?<![a-z0-9_])" + r"\s+".join(words) + r"(?![a-z0-9_])"
    return re.search(pattern, text.lower()) is not None


def normalized_without_negation(text: str) -> str:
    ignored = NEGATION_WORDS | AUXILIARY_WORDS
    return " ".join(token for token in tokens(text) if token not in ignored)


def has_negation(text: str) -> bool:
    lowered = text.lower().replace("can't", "cannot")
    return any(has_phrase(lowered, pattern) for pattern in ["must not", "shall not"]) or any(
        token in NEGATION_WORDS for token in tokens(lowered)
    )


def has_requirement_modal(text: str) -> bool:
    return bool(set(tokens(text)) & REQUIREMENT_MODALS)


def has_prohibition_modal(text: str) -> bool:
    return any(has_phrase(text, pattern) for pattern in PROHIBITION_PATTERNS)


def has_requirement_without_prohibition(text: str) -> bool:
    return has_requirement_modal(text) and not has_prohibition_modal(text)


def token_overlap_ratio(left: str, right: str) -> float:
    left_tokens = set(tokens(left))
    right_tokens = set(tokens(right))
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / max(len(left_tokens), len(right_tokens))


def parse_assignment(text: str) -> tuple[str, str] | None:
    match = re.match(r"\s*(.+?)\s*(?:=|\bis\b|\buses\b)\s*(.+?)\s*$", text.lower())
    if not match:
        return None
    left = " ".join(tokens(match.group(1)))
    right = " ".join(tokens(match.group(2)))
    if not left or not right:
        return None
    return left, right


def validate_run_id(run_id: str) -> None:
    path = Path(run_id)
    if not run_id or path.is_absolute() or path.name != run_id or run_id in {".", ".."}:
        raise ValueError("run_id must be a safe single path component")


def conflict_rule(accepted: dict, candidate: dict) -> str | None:
    if str(accepted.get("topic_id", "")) != str(candidate.get("topic_id", "")):
        return None

    accepted_text = str(accepted.get("claim", ""))
    candidate_text = str(candidate.get("claim", ""))
    if token_overlap_ratio(accepted_text, candidate_text) >= 0.6 and (
        (
            has_requirement_without_prohibition(accepted_text)
            and has_prohibition_modal(candidate_text)
        )
        or (
            has_prohibition_modal(accepted_text)
            and has_requirement_without_prohibition(candidate_text)
        )
    ):
        return "modal_conflict"

    if (
        normalized_without_negation(accepted_text)
        == normalized_without_negation(candidate_text)
        and has_negation(accepted_text) != has_negation(candidate_text)
    ):
        return "negation_polarity"

    accepted_assignment = parse_assignment(accepted_text)
    candidate_assignment = parse_assignment(candidate_text)
    if accepted_assignment and candidate_assignment:
        left_side_matches = accepted_assignment[0] == candidate_assignment[0]
        right_side_differs = accepted_assignment[1] != candidate_assignment[1]
        if left_side_matches and right_side_differs:
            return "single_valued_assignment"

    return None


def make_claim_conflict(
    left: dict,
    right: dict,
    run_id: str,
    conflict_number: int,
    rule: str,
    message: str,
) -> ClaimConflict:
    return ClaimConflict(
        conflict_id=f"conflict.{run_id}.{conflict_number}",
        rule=rule,
        severity="error",
        topic_id=str(left.get("topic_id", "")),
        accepted_claim_id=str(left.get("claim_id", "<missing>")),
        candidate_claim_id=str(right.get("claim_id", "<missing>")),
        accepted_claim=str(left.get("claim", "")),
        candidate_claim=str(right.get("claim", "")),
        accepted_citations=[str(item) for item in left.get("citations") or []],
        candidate_citations=[str(item) for item in right.get("citations") or []],
        message=message,
    )


def detect_claim_conflicts(
    accepted_claims: list[dict], candidate_claims: list[dict], run_id: str
) -> list[ClaimConflict]:
    conflicts: list[ClaimConflict] = []
    for accepted in accepted_claims:
        for candidate in candidate_claims:
            rule = conflict_rule(accepted, candidate)
            if rule is None:
                continue
            conflicts.append(
                make_claim_conflict(
                    accepted,
                    candidate,
                    run_id,
                    len(conflicts) + 1,
                    rule,
                    message="candidate claim conflicts with an accepted claim",
                )
            )
    return conflicts


def detect_would_be_accepted_conflicts(
    accepted_claims: list[dict], candidate_claims: list[dict], run_id: str
) -> list[ClaimConflict]:
    conflicts = detect_claim_conflicts(accepted_claims, candidate_claims, run_id)
    for index, left in enumerate(candidate_claims):
        for right in candidate_claims[index + 1 :]:
            rule = conflict_rule(left, right)
            if rule is None:
                continue
            conflicts.append(
                make_claim_conflict(
                    left,
                    right,
                    run_id,
                    len(conflicts) + 1,
                    rule,
                    message="candidate claims conflict with each other",
                )
            )
    return conflicts


def load_accepted_claims(root: Path) -> list[dict]:
    claims_root = root / ".kb" / "claims"
    claims: list[dict] = []
    if claims_root.is_dir():
        for path in sorted(claims_root.rglob("*.jsonl")):
            claims.extend(read_jsonl(path))
    return claims


def load_run_claims(root: Path, run_id: str) -> list[dict]:
    return read_jsonl(root / ".kb" / "learn_runs" / run_id / "claims.jsonl")


def detect_accepted_conflicts(root: Path) -> list[ClaimConflict]:
    claims = load_accepted_claims(root)
    conflicts: list[ClaimConflict] = []
    for index, left in enumerate(claims):
        for right in claims[index + 1 :]:
            rule = conflict_rule(left, right)
            if rule is None:
                continue
            conflicts.append(
                ClaimConflict(
                    conflict_id=f"conflict.accepted.{len(conflicts) + 1}",
                    rule=rule,
                    severity="error",
                    topic_id=str(left.get("topic_id", "")),
                    accepted_claim_id=str(left.get("claim_id", "<missing>")),
                    candidate_claim_id=str(right.get("claim_id", "<missing>")),
                    accepted_claim=str(left.get("claim", "")),
                    candidate_claim=str(right.get("claim", "")),
                    accepted_citations=[str(item) for item in left.get("citations") or []],
                    candidate_citations=[str(item) for item in right.get("citations") or []],
                    message="accepted claims conflict",
                )
            )
    return conflicts


def write_conflict_artifacts(
    root: Path, run_id: str, conflicts: list[ClaimConflict]
) -> str:
    validate_run_id(run_id)
    conflict_root = root / "reviews" / "conflicts" / run_id
    conflict_root.mkdir(parents=True, exist_ok=True)
    write_jsonl(
        conflict_root / "conflicts.jsonl",
        [asdict(conflict) for conflict in conflicts],
    )
    report_path = conflict_root / "conflict_report.md"
    report_path.write_text(
        "\n".join(
            [
                "# Conflict Report",
                "",
                f"Run: `{run_id}`",
                f"Conflicts: {len(conflicts)}",
                "",
                *[
                    "\n".join(
                        [
                            f"## {conflict.conflict_id}",
                            "",
                            f"- Rule: {conflict.rule}",
                            f"- Topic: {conflict.topic_id}",
                            f"- Accepted: {conflict.accepted_claim}",
                            f"- Candidate: {conflict.candidate_claim}",
                            f"- Accepted citations: {', '.join(conflict.accepted_citations)}",
                            f"- Candidate citations: {', '.join(conflict.candidate_citations)}",
                            "",
                        ]
                    )
                    for conflict in conflicts
                ],
                "## Suggested Next Action",
                "",
                "- Revise the candidate note, reject the run, or split the topic before accepting.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return report_path.relative_to(root).as_posix()
