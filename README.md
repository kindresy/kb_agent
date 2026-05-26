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

## Design

See `specs/2026-05-26-file-ai-knowledge-base-design.md`.
