# KB Agent Phase 5.3 LLM Session Review Notes Design

Approved direction for Phase 5.3 implementation.

## Scope

Phase 5.3 improves how `kb learn --from-session` stages review material from an
LLM-backed ask session.

Included:

- richer pending note content for LLM ask sessions;
- explicit unverified LLM provenance;
- original question and bounded LLM answer excerpt;
- prompt evidence used by the LLM, including scores when available;
- no automatic acceptance of model output.

Excluded:

- No `kb learn --llm`.
- No live LLM calls during learn.
- No automatic claim extraction from LLM answers.
- No bypass of `kb accept`, conflict checks, or compile checks.

## Behavior

For deterministic ask sessions, `kb learn --from-session` keeps the existing
generic session pending note behavior.

For LLM ask sessions, the pending note should be a review artifact with these
sections:

- `# Session <id>`
- `## Review Status`
- `## Original Question`
- `## Unverified LLM Answer Excerpt`
- `## Prompt Evidence Used`
- `## Required Human Checks`
- `## Evidence`

The note must clearly state:

- `Answer mode: llm`
- `Confidence: llm_session_unverified`
- the answer is not accepted source truth until human review and `kb accept`.

## Trust Model

LLM output is allowed into the staged review area because that directory is
already human-review-only. It remains untrusted until the user explicitly
accepts the learn run. Existing conflict and compile gates still apply.

## Acceptance Criteria

- LLM session pending notes contain the original question, LLM answer excerpt,
  prompt evidence refs, scores, and unverified provenance.
- Deterministic session pending notes remain compatible with existing tests.
- `claims.jsonl` continues to mark LLM session claims as
  `llm_session_unverified`.
- Full test suite passes without live LLM calls.

