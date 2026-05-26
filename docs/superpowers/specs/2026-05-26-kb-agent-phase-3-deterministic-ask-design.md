# KB Agent Phase 3 Deterministic Ask Design

## Status

Approved design for Phase 3 implementation.

## Goal

Implement a local deterministic `kb ask` and session capture loop. Phase 3 establishes the question, evidence, answer, attachment, session, and feedback file protocol without calling a real LLM.

## Non-Goals

- No LLM calls.
- No vector search.
- No screenshot OCR or image understanding.
- No semantic root-cause inference.
- No direct modification of accepted notes.

## Commands

```bash
kb ask "Why can my Endpoint not enumerate BAR0?"
kb ask --with logs/boot.log --with dumps/lspci.txt "Why was BAR0 not assigned?"
kb learn --from-session sessions/questions/<session_id>
```

`kb ask` prints a deterministic cited answer and saves a session directory. `kb learn --from-session` routes a saved session back into the staged Phase 2 learning pipeline.

## Data Flow

```text
notes/ + .kb/claims/ + .kb/chunks/ + sources/
        |
        v
kb ask
        |
        +-- sessions/questions/<session_id>/question.md
        +-- sessions/questions/<session_id>/evidence_pack.json
        +-- sessions/questions/<session_id>/answer.md
        +-- sessions/questions/<session_id>/feedback_plan.md
        +-- sessions/questions/<session_id>/attachments/
```

If the question looks like a debug question or includes attachments, the session is saved under `sessions/debug_cases/<session_id>/`.

## Session Id

Session ids use:

```text
ask_YYYYMMDD_HHMMSS
```

## Intent Classification

Intent is deterministic:

- `debug`: question includes words such as fail, failure, error, stuck, not assigned, enumerate, BAR0, LTSSM, timeout, log, trace, dump, register, why was.
- `code_reading`: question includes code, function, struct, driver, source, call path.
- `comparison`: question includes compare, difference, versus, vs.
- `design`: question includes design, architecture, integrate, integration.
- `experiment`: question includes experiment, validate, measure, test plan.
- `concept`: fallback.

## Attachments

`--with <path>` may be repeated. Attachments are copied into the session `attachments/` directory. The session records original path, copied path, file type, size, and hash.

Missing attachment paths make `kb ask` fail before writing a session.

## Evidence Retrieval

Evidence retrieval is deterministic and shallow:

1. Accepted claims from `.kb/claims/*.jsonl`.
2. Accepted notes from `notes/**/*.md`.
3. Source index records from `.kb/source_index.jsonl`.
4. Accepted chunks from `.kb/chunks/*.jsonl`.
5. Attachment metadata.

The evidence pack stores compact records:

```json
{
  "type": "source",
  "ref": "kb://source/manual",
  "why_relevant": "source title matched question terms"
}
```

Matching uses lowercase token overlap between the question and titles, note text, claim text, source ids, source titles, and attachment names. If no overlap is found, `kb ask` still includes the first available source as fallback evidence so the answer remains cited when a source exists.

## Answer Shape

`kb ask` writes and prints:

```markdown
# Answer

## Direct Conclusion

## Background Mechanism

## Mapping to Your Project

## Evidence

## Debug Path / Next Experiment

## Uncertainty
```

For `debug` intent, the answer includes:

- symptom restatement
- known facts
- ranked deterministic hypotheses
- validation steps
- missing information
- confidence

All answers must include citations when evidence is available.

## Feedback Plan

Every session writes `feedback_plan.md`:

```markdown
# Feedback Plan

## Candidate Learning Input

## Suggested Command

kb learn --from-session <session_path>
```

The feedback plan does not modify accepted notes. It only points back to the Phase 2 learn/accept flow.

## Learn From Session

Phase 3 extends `kb learn` with:

```bash
kb learn --from-session sessions/questions/<session_id>
```

This creates a normal staged learn run whose snapshot records `from_session`. The generated pending note summarizes:

- the question
- evidence reviewed
- answer path
- feedback plan path

It still requires `kb accept <run_id>` to promote notes.

## Compile Extensions

`kb compile --fast` continues to validate Markdown links and `kb://source` references in `sessions/`, including generated answer and feedback plan files.

## Test Strategy

Tests cover:

- `kb ask` prints a cited answer and saves session files.
- `kb ask --with <file>` copies attachments and chooses debug session path.
- missing attachments fail without partial session writes.
- evidence pack includes claims, notes, sources, or fallback source evidence.
- `kb learn --from-session <path>` creates staged pending notes and report.
- full compile passes after ask and learn-from-session flows.

## Completion Criteria

Phase 3 is complete when a local PCIe KB can ask a question, save a cited session, attach logs/code, generate feedback, and route that session back through `kb learn --from-session` plus `kb accept`.
