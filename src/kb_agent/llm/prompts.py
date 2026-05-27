from __future__ import annotations

import json


def build_ask_prompt(
    *,
    question: str,
    intent: str,
    evidence: list[dict[str, str]],
    attachments: list[dict[str, object]],
) -> str:
    evidence_json = json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True)
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
            "",
            f"Question: {question}",
            f"Intent: {intent}",
            "",
            "Evidence:",
            evidence_json,
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

