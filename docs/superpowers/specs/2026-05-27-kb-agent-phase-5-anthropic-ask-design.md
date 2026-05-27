# KB Agent Phase 5 Anthropic Ask Design

Approved direction for Phase 5.1 implementation.

## Scope

Phase 5.1 adds optional real LLM answer generation to the existing local,
file-based `kb ask` workflow.

Included:

- `kb ask --llm "QUESTION"` uses Anthropic Claude when explicitly requested.
- The default `kb ask "QUESTION"` remains deterministic and offline.
- LLM prompts are constrained to the retrieved local evidence pack.
- Ask sessions still write `question.md`, `evidence_pack.json`, `answer.md`,
  and `feedback_plan.md`.
- Retrieved evidence includes bounded text excerpts where local text is
  available, so the LLM receives actual evidence content rather than only refs.
- Tests use fake providers and do not require a live Claude API key.

Excluded:

- No LLM-backed `kb learn`.
- No embeddings or vector database.
- No LLM conflict detection.
- No automatic promotion of LLM output into accepted notes.
- No storage of API keys in the knowledge base.

## User Interface

Default deterministic mode:

```bash
kb ask "What is PCIe Configuration Space?"
```

Anthropic mode:

```bash
export ANTHROPIC_API_KEY="..."
kb ask --llm "What is PCIe Configuration Space?"
```

Optional model override:

```bash
kb ask --llm --model claude-sonnet-4-20250514 "Explain BAR assignment"
```

Environment variables:

- `ANTHROPIC_API_KEY`: required only when `--llm` is used.
- `KB_AGENT_LLM_MODEL`: optional default model override.
- `KB_AGENT_LLM_MAX_TOKENS`: optional output-token limit.

The built-in default model is `claude-sonnet-4-20250514`, a stable Anthropic
API snapshot model. A stable snapshot is preferred over a latest alias because
knowledge-base answers should be reproducible.

## Architecture

Add a narrow provider boundary under `src/kb_agent/llm/`:

- `base.py`: protocol and response dataclass.
- `prompts.py`: evidence-constrained ask prompt builder.
- `anthropic_provider.py`: Anthropic Messages API adapter.

`kb_agent.ask.run_ask()` remains the workflow owner:

1. Validate attachments.
2. Classify intent.
3. Allocate session directory.
4. Copy attachments.
5. Retrieve deterministic evidence.
6. Generate either deterministic or LLM answer.
7. Persist session files.

The LLM provider receives only:

- question text,
- classified intent,
- retrieved evidence rows, including refs and bounded excerpts,
- copied attachment metadata.

It does not receive the API key through persisted session artifacts.

## Prompt Contract

The prompt must instruct the model to:

- answer as a careful embedded/OS/firmware teacher,
- use only the supplied evidence when making cited claims,
- cite evidence refs exactly as provided,
- distinguish conclusion, mechanism, project mapping, evidence, next checks,
  and uncertainty,
- say clearly when evidence is insufficient.

This is intentionally conservative. Phase 5.1 improves answer quality without
changing the acceptance or compilation trust model.

## Session Metadata

`evidence_pack.json` gains:

```json
{
  "answer_mode": "deterministic|llm",
  "llm_provider": "anthropic|null",
  "llm_model": "model-name|null"
}
```

Existing consumers must continue to work by reading the existing `evidence`
field.

## Error Behavior

When `--llm` is requested:

- missing `ANTHROPIC_API_KEY` fails before creating a session;
- missing Anthropic SDK fails with a direct installation/configuration message;
- provider/API failures remove the newly allocated partial session before
  returning the error.

## Learning From LLM Sessions

`kb learn --from-session` remains available for LLM ask sessions, but it must
preserve provenance:

- generated chunks include `answer_mode`, `llm_provider`, and `llm_model`;
- LLM answers are not marked as deterministic source truth;
- LLM-session claims use `confidence: llm_session_unverified`;
- the staged learning artifact is based on the question and evidence metadata,
  not the model answer as an authoritative source.

## Verification

Required automated checks:

- deterministic `kb ask` behavior remains unchanged;
- `run_ask(..., use_llm=True, llm_provider=fake)` writes an LLM answer and
  metadata;
- prompt builder includes the question, intent, evidence refs, and citation
  rules;
- CLI `kb ask --llm` fails cleanly when `ANTHROPIC_API_KEY` is not set;
- provider failure leaves no partial ask session;
- LLM `learn --from-session` preserves non-deterministic provenance;
- full test suite passes without a live API key.
