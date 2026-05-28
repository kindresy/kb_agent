# kb-agent

`kb-agent` is a local CLI-first, file-based knowledge base manager.

## Install for development

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
```

## Phase 1 commands

```bash
kb init pcie
cd pcie
kb ingest ../some-manual.md
kb compile --fast
kb health
```

## Markdown packages

`kb ingest` preserves Markdown exports with adjacent assets directories as one source package:

```text
pcie-book/
├── pcie-book.md
└── pcie-book.assets/
    └── ltssm.png
```

Supported package layouts:

```text
<stem>.assets/
<stem>-assets/
<stem>_assets/
parts/ or images/ directories referenced by relative Markdown links
```

Run:

```bash
kb ingest ../pcie-book/
```

The package is archived under `sources/manuals/pcie-book/`, and `kb compile --fast` checks that package assets and relative Markdown links still resolve. Re-running `kb ingest` on already indexed content skips matching source hashes instead of creating duplicate `_2` records.

## Demo

```bash
bash examples/phase1_demo.sh
```

## Phase 2 deterministic learn

```bash
kb learn --goal "Build PCIe configuration notes"
kb accept <learn_run_id>
kb compile --fast
kb health
```

Phase 2 uses deterministic local rules. It stages generated notes under
`reviews/pending_notes/<run_id>/` and writes reports under
`reports/learn/<run_id>/`. Accepted notes are promoted only through
`kb accept <run_id>`.

## Phase 3 deterministic ask

```bash
kb ask "What is Configuration Space?"
kb ask --with ../boot.log "Why was BAR0 not assigned?"
kb learn --from-session sessions/questions/<session_id>
```

Phase 3 uses deterministic local evidence retrieval. It saves questions,
answers, evidence packs, attachments, and feedback plans under `sessions/`.
Session feedback only enters accepted notes through `kb learn` and
`kb accept`.

## Phase 4 graph and conflicts

```bash
kb graph export
kb compile --fast
kb health
```

Phase 4 exports deterministic graph artifacts from accepted sources, topics,
claims, chunks, and notes. Re-running `kb graph export` writes stable node and
edge files plus a graph report under `reports/graph/`.

Conflict gates protect accepted knowledge. `kb compile --fast` fails when
accepted claims conflict with each other. `kb accept <run_id>` blocks candidate
claims that would conflict with accepted state or with each other, and writes
review artifacts under `reviews/conflicts/<run_id>/`.

## Phase 5 optional LLM ask

`kb ask` remains deterministic by default. To use Claude for answer generation:

```bash
export ANTHROPIC_API_KEY="..."
kb ask --llm "Explain PCIe BAR assignment"
```

Optional model controls:

```bash
export KB_AGENT_LLM_MODEL=claude-sonnet-4-20250514
export KB_AGENT_LLM_MAX_TOKENS=2048
kb ask --llm --model claude-sonnet-4-20250514 "Why was BAR0 not assigned?"
```

LLM answers are saved only into the ask session. They are generated from the
same local evidence pack used by deterministic ask, including bounded evidence
excerpts. If an LLM call fails, `kb-agent` removes the partial session.
For prompt stability, `kb ask --llm` reranks retrieved evidence locally and sends
only the bounded `prompt_evidence` slice to the model. The complete retrieved
`evidence` list and `evidence_selection` metadata remain in the session for
audit.

Promote useful findings through the existing review path:

```bash
kb learn --from-session sessions/questions/<session_id>
kb accept <learn_run_id>
```

LLM session learning preserves `answer_mode=llm` provenance and does not treat
the LLM answer itself as deterministic source truth.

## Design

See `specs/2026-05-26-file-ai-knowledge-base-design.md`.
