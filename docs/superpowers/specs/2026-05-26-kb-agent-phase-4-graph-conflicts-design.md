# KB Agent Phase 4 Graph and Conflict Detection Design

Approved direction for Phase 4.1 and Phase 4.2 implementation.

## Scope

Phase 4 is split into smaller deliverables. This design covers only:

- Phase 4.1: deterministic claim/topic graph skeleton.
- Phase 4.2: deterministic conflict detector and accept/compile gates.

This design intentionally excludes PCIe domain skills. Those remain later work after the graph and conflict data model is stable.

## Goals

The goal is to make accepted knowledge inspectable as a graph and prevent clearly conflicting claims from entering accepted notes without review.

The first implementation remains local, deterministic, and file-based. It should work without LLM calls, embeddings, vector stores, or external services. The graph and conflict outputs are rebuildable machine artifacts under `.kb/graph/`, while human-facing reports live under `reports/graph/` and `reviews/conflicts/`.

## Recommended Approach

Three approaches were considered:

1. Deterministic local graph and conflict rules.
2. LLM-assisted contradiction detection.
3. Full graph database integration.

Use option 1 now. It matches the current deterministic pipeline, keeps tests exact, and creates stable artifacts that later LLM/domain-skill layers can consume. Option 2 is more semantically powerful but would make Phase 4 hard to verify. Option 3 is premature for a CLI-first file-system product.

## Data Inputs

The graph builder reads existing accepted artifacts:

- `.kb/topics/**/*.jsonl`
- `.kb/claims/**/*.jsonl`
- `.kb/chunks/**/*.jsonl`
- `.kb/source_index.jsonl`
- accepted notes under `notes/**/*.md`

The conflict detector reads:

- accepted claims from `.kb/claims/**/*.jsonl`
- candidate run claims from `.kb/learn_runs/<run_id>/claims.jsonl`
- source metadata from `.kb/source_index.jsonl`

## Graph Artifacts

`kb graph export` writes these files:

```text
.kb/graph/nodes.jsonl
.kb/graph/edges.jsonl
.kb/graph/summary.json
reports/graph/graph_report.md
```

Nodes use a small typed shape:

```json
{
  "node_id": "claim:claim.configuration_space.1",
  "type": "claim",
  "label": "The source introduces Configuration Space.",
  "ref": ".kb/claims/claims.jsonl"
}
```

Edges use:

```json
{
  "from": "claim:claim.configuration_space.1",
  "to": "topic:topic.configuration_space",
  "type": "about_topic",
  "evidence": "topic_id"
}
```

Initial node types:

- `source`
- `topic`
- `claim`
- `chunk`
- `note`

Initial edge types:

- `topic_from_source`
- `claim_about_topic`
- `claim_cites_source`
- `chunk_supports_topic`
- `chunk_from_source`
- `note_mentions_source`
- `note_mentions_topic`

The graph is an index, not an authority. Accepted claims and notes remain authoritative. Graph files can be deleted and rebuilt.

## `kb graph export`

Add a Typer subcommand group:

```bash
kb graph export
```

The command locates the KB root, rebuilds graph artifacts from accepted state, prints a short summary, and exits nonzero only for structural read/write errors.

Example output:

```text
Graph exported
Nodes: 8
Edges: 10
Report: reports/graph/graph_report.md
```

## Conflict Model

The first conflict detector uses deterministic, narrow rules. It should catch obvious contradictions without pretending to understand every technical statement.

Each claim is normalized into:

- `claim_id`
- `topic_id`
- `claim`
- `type`
- `citations`
- normalized text tokens

Conflict candidates are grouped by `topic_id`. Claims with different topics do not conflict in Phase 4.2.

### Rule 1: Negation Polarity Conflict

Two claims conflict when all conditions are true:

- same `topic_id`
- same normalized key phrase after removing negation words
- one claim is positive and the other is negative

Negation words:

- `not`
- `no`
- `never`
- `without`
- `disabled`
- `unsupported`
- `cannot`
- `can't`
- `must not`

Example:

- Accepted: `BAR0 is assigned by firmware.`
- Candidate: `BAR0 is not assigned by firmware.`

### Rule 2: Mutually Exclusive Modal Conflict

Two claims conflict when all conditions are true:

- same `topic_id`
- overlapping normalized claim tokens above threshold
- one claim contains a requirement modal and the other contains a prohibition modal

Requirement modals:

- `must`
- `required`
- `shall`
- `always`

Prohibition modals:

- `must not`
- `shall not`
- `forbidden`
- `prohibited`
- `never`

### Rule 3: Single-Valued Assignment Conflict

Two claims conflict when all conditions are true:

- same `topic_id`
- both match `X is Y`, `X = Y`, or `X uses Y`
- same normalized left side
- different normalized right side

This catches deterministic conflicts such as:

- `MSI vector count is 32.`
- `MSI vector count is 64.`

## Conflict Artifacts

When conflicts are found, write:

```text
reviews/conflicts/<run_id>/conflicts.jsonl
reviews/conflicts/<run_id>/conflict_report.md
```

JSONL record shape:

```json
{
  "conflict_id": "conflict.learn_20260526_120000.1",
  "rule": "negation_polarity",
  "severity": "error",
  "topic_id": "topic.bar_assignment",
  "accepted_claim_id": "claim.bar_assignment.1",
  "candidate_claim_id": "claim.bar_assignment.2",
  "accepted_claim": "BAR0 is assigned by firmware.",
  "candidate_claim": "BAR0 is not assigned by firmware.",
  "accepted_citations": ["kb://source/manual#chunk=chunk.bar_assignment.1"],
  "candidate_citations": ["kb://source/debug_log"],
  "message": "candidate claim conflicts with an accepted claim"
}
```

## Gates

### Compile Gate

`kb compile --fast` checks accepted claims for internal conflicts. If accepted state already contains conflicting claims, compile fails with:

```text
error: claim_conflict: .kb/claims/claims.jsonl: accepted claims conflict: <conflict_id>
```

It also writes the usual `.kb/compile_state.json`.

### Accept Gate

`kb accept <run_id>` checks candidate claims against accepted claims before promotion.

If conflicts exist:

- do not promote any notes
- do not append candidate topics/chunks/claims to accepted indexes
- write conflict artifacts under `reviews/conflicts/<run_id>/`
- return exit code 1
- print the conflict report path

This preserves the current all-or-nothing accept behavior.

## Health Metrics

`kb health` should include graph and conflict metrics after Phase 4.2:

```text
Health: ok
Sources: 1
Findings: 0
Graph nodes: 8
Graph edges: 10
Conflicts: 0
```

Health remains warning if `compile --fast` fails.

## Reports

`reports/graph/graph_report.md` includes:

- total node count
- total edge count
- counts by node type
- counts by edge type
- source coverage
- claim citation coverage

`reviews/conflicts/<run_id>/conflict_report.md` includes:

- candidate run id
- number of conflicts
- conflicts grouped by rule
- accepted claim and citation
- candidate claim and citation
- suggested next action: revise source material, reject run, or split topic

## Error Handling

Graph export should tolerate missing optional accepted artifacts and produce an empty graph for an initialized KB with no learned material.

Conflict detection should treat malformed claim records as compile/accept validation errors only when the existing claim checker already considers them invalid. Conflict detection should not replace citation validation.

If conflict artifact writing fails, `kb accept` fails before promotion.

## Testing Strategy

Add tests at three levels:

- graph unit tests for node/edge construction
- conflict unit tests for each deterministic conflict rule
- CLI/integration tests for `kb graph export`, `kb compile --fast`, `kb health`, and `kb accept <run_id>`

Regression cases:

- empty initialized KB exports an empty graph
- learned and accepted PCIe material exports source/topic/claim/chunk/note nodes
- accepted conflicting claims fail compile
- candidate conflicting claims fail accept without partial promotion
- non-conflicting candidate claims still accept

## Completion Criteria

Phase 4.1 and Phase 4.2 are complete when:

- `kb graph export` rebuilds `.kb/graph/` and `reports/graph/graph_report.md`
- `kb compile --fast` fails on accepted claim conflicts
- `kb accept <run_id>` blocks candidate conflicts and writes review artifacts
- `kb health` reports graph and conflict metrics
- tests cover graph export, conflict rules, compile gate, accept gate, and health metrics
- a demo script shows the conflict review loop end to end
