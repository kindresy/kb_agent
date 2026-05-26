# KB Agent Phase 2 Deterministic Learn Design

## Status

Approved design for Phase 2 implementation.

## Goal

Implement the minimum `kb learn` loop as a local deterministic pipeline. Phase 2 establishes the learning file protocol, staged review flow, reports, and accept gate without calling a real LLM.

## Non-Goals

- No LLM or embedding API calls.
- No semantic conflict detection.
- No PDF full-text extraction.
- No teacher Q&A mode.
- No session capture.
- No domain skill execution.

These remain later phase work. Phase 2 output is intentionally structured draft material, not final expert-quality prose.

## User Commands

```bash
kb learn
kb learn --goal "Build PCIe enumeration notes"
kb learn --sources pcie_base_spec_5_0,linux_kernel
kb accept <learn_run_id>
```

`kb learn` reads accepted sources and writes staged learning artifacts. It never writes directly to accepted `notes/`.

`kb accept <learn_run_id>` validates staged artifacts, runs compile gates, and promotes accepted pending notes plus machine indexes into the knowledge base.

## Data Flow

```text
.kb/source_index.jsonl
        |
        v
kb learn
        |
        +-- .kb/learn_runs/<run_id>/snapshot.json
        +-- .kb/learn_runs/<run_id>/profiles.jsonl
        +-- .kb/learn_runs/<run_id>/topics.jsonl
        +-- .kb/learn_runs/<run_id>/chunks.jsonl
        +-- .kb/learn_runs/<run_id>/claims.jsonl
        +-- reviews/pending_notes/<run_id>/*.md
        +-- reports/learn/<run_id>/learn_report.md
        |
        v
kb accept <run_id>
        |
        +-- notes/concepts/generated/*.md
        +-- .kb/topics/topics.jsonl
        +-- .kb/chunks/chunks.jsonl
        +-- .kb/claims/claims.jsonl
```

## Run Snapshot

Every learn run receives a stable run id:

```text
learn_YYYYMMDD_HHMMSS
```

The snapshot records:

- run id
- timestamp
- optional goal
- selected source ids
- all source records used by the run
- skipped sources and reasons

If `--sources` is omitted, all accepted source records are selected. Unknown source ids cause `kb learn` to fail before writing artifacts.

## Source Profiles

Phase 2 profiles are deterministic and shallow.

Profile fields:

- `source_id`
- `type`
- `title`
- `path`
- `kind`
- `authority`
- `headings`
- `symbols`
- `candidate_topics`

Authority is derived from source type and path:

- specs: `primary`
- code: `implementation`
- logs: `debug`
- manuals, books, datasheets, webpages: `explanatory`
- unknown: `secondary`

Markdown profiles extract ATX headings (`#`, `##`, etc.) from the source file. Package Markdown uses the package main Markdown file. Code profiles extract simple function, struct, class, and define-like symbols. PDF profiles use only file-level metadata in Phase 2.

## Topic Extraction

Topics are deterministic records derived from profile metadata.

Priority order:

1. Markdown headings.
2. Code symbols.
3. Source title fallback.

Topic records contain:

- `topic_id`
- `name`
- `source_id`
- `source_path`
- `basis`
- `priority`
- `citations`

Topic ids are slugs under `topic.`. Example:

```text
topic.configuration_space
topic.pci_scan_device
topic.pci_express_base_specification_revision_5_0_version_1_0
```

If multiple sources produce the same topic id, a numeric suffix is appended deterministically.

## Evidence Chunks

Evidence chunks are compact source excerpts with stable hashes.

Chunk rules:

- Markdown: create chunks from heading sections when possible, with a bounded character limit.
- Code: create chunks around extracted symbols or line windows.
- Text and logs: create line-window chunks.
- PDF and binary-like sources: create a file-level chunk that cites the source record.

Chunk records contain:

- `chunk_id`
- `source_id`
- `source_path`
- `topic_id`
- `kind`
- `text`
- `hash`
- `citation`

The citation format is:

```text
kb://source/<source_id>#chunk=<chunk_id>
```

## Claim Drafting

Phase 2 claims are conservative template claims. They are designed to prove the pipeline and citation gates, not to make deep technical assertions.

Example:

```json
{
  "claim_id": "claim.topic.configuration_space.1",
  "topic_id": "topic.configuration_space",
  "type": "source_observation",
  "claim": "The source introduces Configuration Space.",
  "citations": ["kb://source/pci_express_base_spec#chunk=chunk.topic.configuration_space.1"],
  "confidence": "deterministic"
}
```

Every claim must have at least one citation. Uncited claims are invalid and cannot be accepted.

## Pending Notes

`kb learn` writes one pending note per topic:

```text
reviews/pending_notes/<run_id>/<topic_id>.md
```

Template:

```markdown
# Topic Title

## One-Sentence Conclusion

## What Was Found

## Evidence

## Open Questions

## Related Sources
```

Every pending note must include at least one `kb://source/...` citation in `Evidence`.

## Learn Report

Every run writes:

```text
reports/learn/<run_id>/learn_report.md
```

The report includes:

- goal
- selected sources
- skipped sources
- profiles written
- topics generated
- chunks generated
- claims generated
- pending notes generated
- citations
- conflicts or invalid claims
- next suggested command

## Accept Gate

`kb accept <run_id>` performs these checks:

1. The run directory exists.
2. Pending notes for the run exist.
3. Claims exist and every claim has at least one citation.
4. All `kb://source/...` citations resolve to known source ids.
5. `compile_fast` passes before promotion.

On success:

- pending notes are copied to `notes/concepts/generated/`
- run topics append to `.kb/topics/topics.jsonl`
- run chunks append to `.kb/chunks/chunks.jsonl`
- run claims append to `.kb/claims/claims.jsonl`

On failure:

- no accepted notes are written
- no accepted indexes are updated
- the command prints actionable error messages

## Compile Extensions

Phase 2 extends `kb compile --fast` with claim validation:

- `.kb/claims/*.jsonl` is scanned.
- claims without citations produce an error.
- claim citations to unknown sources produce an error.

Existing Markdown citation and link checks continue to cover `notes/`, `sessions/`, and `reviews/`.

## Test Strategy

Tests must cover:

- `kb learn` creates snapshot, profiles, topics, chunks, claims, pending notes, and report.
- `kb learn --sources` limits selected sources and rejects unknown source ids.
- Markdown headings become deterministic topics.
- Code symbols become deterministic topics.
- Claims always include citations.
- `kb accept <run_id>` promotes notes and indexes when gates pass.
- `kb accept <run_id>` refuses uncited claims without partial promotion.
- `kb compile --fast` reports claim citation errors.

## Phase 2 Completion Criteria

Phase 2 is complete when:

- a PCIe knowledge base can run `kb learn`
- the run produces staged notes and a learn report
- staged notes cite accepted sources
- `kb accept <run_id>` promotes valid staged notes
- invalid claims or unresolved citations block acceptance
- full test suite passes
