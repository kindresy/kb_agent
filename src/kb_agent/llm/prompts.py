from __future__ import annotations

import json


MAX_PROMPT_EVIDENCE_ITEMS = 32
MAX_PROMPT_EXCERPT_CHARS = 1200


def compact_evidence_for_prompt(
    evidence: list[dict[str, str]],
) -> tuple[list[dict[str, str]], int]:
    compacted: list[dict[str, str]] = []
    for item in evidence[:MAX_PROMPT_EVIDENCE_ITEMS]:
        compact_item = dict(item)
        excerpt = compact_item.get("excerpt", "")
        if len(excerpt) > MAX_PROMPT_EXCERPT_CHARS:
            compact_item["excerpt"] = excerpt[: MAX_PROMPT_EXCERPT_CHARS - 3].rstrip() + "..."
        compacted.append(compact_item)
    return compacted, max(0, len(evidence) - len(compacted))


def build_ask_prompt(
    *,
    question: str,
    intent: str,
    evidence: list[dict[str, str]],
    attachments: list[dict[str, object]],
) -> str:
    compact_evidence, omitted = compact_evidence_for_prompt(evidence)
    evidence_json = json.dumps(
        compact_evidence, ensure_ascii=False, indent=2, sort_keys=True
    )
    attachments_json = json.dumps(
        attachments, ensure_ascii=False, indent=2, sort_keys=True
    )
    return "\n".join(
        [
            "You are a careful embedded systems, operating system, and firmware teacher.",
            "Use only the supplied local knowledge-base evidence for cited claims.",
            "If the evidence is insufficient, say the evidence is insufficient and list what is missing.",
            "You must cite evidence refs exactly as provided, for example kb://source/name.",
            "Do not invent citations, source titles, register names, code paths, or project facts.",
            "Return only the final Markdown answer. Do not include private reasoning, analysis, scratchpad, or planning.",
            "",
            f"Question: {question}",
            f"Intent: {intent}",
            "",
            "Evidence:",
            evidence_json,
            f"Evidence items omitted from prompt due to context budget: {omitted}",
            "",
            "Attachments:",
            attachments_json,
            "",
            "Write the answer in Markdown with these sections:",
            "# Answer",
            "## Direct Conclusion",
            "## Background Mechanism",
            "## Mapping to Your Project",
            "## Evidence",
            "## Debug Path / Next Experiment",
            "## Uncertainty",
        ]
    )
