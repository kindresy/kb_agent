# KB Agent Phase 5.2 Evidence Rerank Design

Approved direction for Phase 5.2 implementation.

## Scope

Phase 5.2 improves `kb ask --llm` evidence quality before prompt construction.
The goal is to avoid sending broad, low-signal evidence such as thousands of
chapter headings when a question names a specific topic like PCIe BAR
assignment.

Included:

- Deterministic local evidence scoring.
- A bounded `prompt_evidence` slice for the LLM prompt.
- Session metadata that records why evidence was selected or omitted.
- No live LLM calls in automated tests.

Excluded:

- No embeddings or vector database.
- No LLM reranker.
- No `kb learn --llm`.
- No direct promotion of LLM answers into accepted notes.

## User Behavior

Existing command:

```bash
kb ask --llm "Explain PCIe BAR assignment with citations from my knowledge base."
```

Expected Phase 5.2 behavior:

- `evidence_pack.json` still stores the full retrieved `evidence` list.
- `evidence_pack.json` also stores `prompt_evidence`, the deterministic top-N
  subset sent to the LLM.
- `evidence_selection` records scoring method, evidence budget, selected count,
  omitted count, and each selected item's score.
- `answer.md` remains the LLM answer.

## Scoring

The scorer is intentionally deterministic and local:

- tokenize the question and candidate evidence text;
- score exact token overlap;
- give extra weight for multi-token phrase overlap from adjacent question
  tokens;
- give useful excerpts more weight than title-only evidence;
- prefer more concrete evidence types in this order:
  `accepted_claim`, `accepted_note`, `source_chunk`, `attachment`, `source`;
- keep ordering stable by sorting on score descending and original index
  ascending.

Evidence text for scoring comes from:

- `ref`,
- `citation`,
- `why_relevant`,
- `excerpt`.

## Prompt Boundary

The prompt builder should receive `prompt_evidence`, not the full evidence list.
The full evidence list remains available in the session for audit and future
learning workflows.

This preserves the trust model:

- retrieval remains auditable;
- prompt input is bounded;
- LLM output is still only an ask-session artifact;
- accepted notes still require `kb learn --from-session` and `kb accept`.

## Metadata Shape

`evidence_pack.json` gains:

```json
{
  "prompt_evidence": [
    {
      "type": "source_chunk",
      "ref": "kb://source/pci#chunk=bar",
      "why_relevant": "chunk text matched question terms",
      "excerpt": "BAR assignment text...",
      "score": 12
    }
  ],
  "evidence_selection": {
    "method": "deterministic_token_phrase_v1",
    "budget": 32,
    "candidate_count": 100,
    "selected_count": 32,
    "omitted_count": 68
  }
}
```

Existing consumers that only read `evidence` must continue to work.

## Acceptance Criteria

- Deterministic `kb ask` still works.
- `kb ask --llm` sends only `prompt_evidence` to the provider.
- `prompt_evidence` prioritizes BAR-specific evidence over generic fallback
  evidence for a BAR question.
- `evidence_pack.json` contains full `evidence`, selected `prompt_evidence`, and
  `evidence_selection` metadata.
- Full test suite passes without a live LLM call.

