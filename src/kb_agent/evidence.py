from __future__ import annotations

import re
from typing import Any


DEFAULT_PROMPT_EVIDENCE_BUDGET = 32
EVIDENCE_SELECTION_METHOD = "deterministic_token_phrase_v1"

TYPE_BONUS = {
    "accepted_claim": 5,
    "accepted_note": 4,
    "source_chunk": 3,
    "attachment": 2,
    "source": 1,
}


def evidence_tokens(text: str) -> list[str]:
    return [
        token
        for token in re.findall(r"[a-z0-9_]+", text.lower())
        if len(token) > 1
    ]


def question_phrases(question_tokens: list[str]) -> set[str]:
    return {
        f"{left} {right}"
        for left, right in zip(question_tokens, question_tokens[1:], strict=False)
    }


def evidence_text(item: dict[str, Any]) -> str:
    return " ".join(
        str(item.get(key, "")) for key in ["ref", "citation", "why_relevant", "excerpt"]
    )


def score_evidence(question: str, item: dict[str, Any]) -> int:
    q_tokens = evidence_tokens(question)
    q_token_set = set(q_tokens)
    text = evidence_text(item)
    text_tokens = set(evidence_tokens(text))
    overlap = q_token_set & text_tokens
    score = len(overlap) * 2

    text_lower = text.lower()
    for phrase in question_phrases(q_tokens):
        if phrase in text_lower:
            score += 3

    excerpt_tokens = set(evidence_tokens(str(item.get("excerpt", ""))))
    if q_token_set & excerpt_tokens:
        score += 2

    score += TYPE_BONUS.get(str(item.get("type", "")), 0)
    return score


def select_prompt_evidence(
    question: str,
    evidence: list[dict[str, str]],
    budget: int = DEFAULT_PROMPT_EVIDENCE_BUDGET,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    scored = [
        (score_evidence(question, item), index, item)
        for index, item in enumerate(evidence)
    ]
    scored.sort(key=lambda candidate: (-candidate[0], candidate[1]))
    selected = []
    for score, _index, item in scored[:budget]:
        selected_item = dict(item)
        selected_item["score"] = score
        selected.append(selected_item)

    metadata = {
        "method": EVIDENCE_SELECTION_METHOD,
        "budget": budget,
        "candidate_count": len(evidence),
        "selected_count": len(selected),
        "omitted_count": max(0, len(evidence) - len(selected)),
    }
    return selected, metadata

