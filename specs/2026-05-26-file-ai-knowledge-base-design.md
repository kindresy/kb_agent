# File-Based AI Knowledge Base Design

Date: 2026-05-26

Status: approved design draft

Target repository: `kindresy/kb_agent`

## 1. Goal

Build a local CLI-first, file-based AI knowledge base management system for technical domains such as PCIe, SPI, DDR, OS, firmware, drivers, SoC integration, and board-level debugging.

The system must manage large mixed knowledge collections: specifications, books, databooks, protocol manuals, web links, source code, logs, screenshots, register dumps, and project-specific notes. It should digest them incrementally, produce human-readable learning notes with strong evidence links, answer user questions like a teacher, preserve debugging conversations as files, and continuously check knowledge consistency.

The core principle is:

> Files are the source of truth. AI and indexes assist the workflow, but accepted knowledge must remain auditable as files.

## 2. Chosen Architecture

Use a local CLI plus file-system-first architecture.

Rejected alternatives:

- Pure Markdown plus scripts: simple, but too weak for citation checking, conflict detection, and incremental learning at scale.
- Database-first local RAG: can answer quickly, but weakens auditability and makes long-term knowledge ownership harder.

Chosen approach:

- Original sources, notes, sessions, reviews, and reports are stored as files.
- `.kb/` stores rebuildable machine indexes: source index, chunks, topic graph, claim graph, citation graph, embeddings, and compile state.
- All knowledge changes pass through staged review, compile checks, conflict detection, and user acceptance.

## 3. Per-Domain Knowledge Base Layout

Each domain is a normal directory:

```text
<domain-kb>/
├── AGENTS.md
├── README.md
├── kb.yaml
├── inbox/
├── sources/
│   ├── specs/
│   ├── books/
│   ├── datasheets/
│   ├── manuals/
│   ├── webpages/
│   ├── code/
│   ├── logs/
│   ├── images/
│   └── unknown/
├── notes/
│   ├── _index.md
│   ├── _glossary.md
│   ├── _open_questions.md
│   ├── concepts/
│   ├── mechanisms/
│   ├── workflows/
│   ├── registers/
│   ├── software/
│   ├── hardware/
│   ├── debug/
│   └── experiments/
├── sessions/
│   ├── questions/
│   ├── debug_cases/
│   ├── design_reviews/
│   └── experiments/
├── reports/
│   ├── ingest/
│   ├── learn/
│   ├── compile/
│   └── health/
├── reviews/
│   ├── routing/
│   ├── conflicts/
│   └── pending_notes/
├── skills/
├── tools/
└── .kb/
    ├── manifest.json
    ├── source_index.jsonl
    ├── chunks/
    ├── embeddings/
    ├── topics/
    ├── claims/
    ├── citations/
    ├── graph/
    ├── compile_state.json
    └── cache/
```

### 3.1 Directory Semantics

`inbox/`
: User drop zone. New books, specs, PDFs, code, logs, links, screenshots, and raw material packages enter here.

`sources/`
: AI-read-only source archive. The system may classify and move material into `sources/`, but must not rewrite the original content. Every source has a stable `source_id`.

`notes/`
: AI-readable and AI-writable accepted learning notes. Notes are structured for human learning, not raw summaries. Important claims must cite original evidence.

`sessions/`
: Saved question, debugging, design review, and experiment conversations. Sessions preserve project context and may later feed back into notes.

`reports/`
: Audit reports for ingest, learn, compile, and health runs.

`reviews/`
: Human decision area. Routing suggestions, pending notes, and conflicts are placed here before they can enter accepted knowledge.

`.kb/`
: Rebuildable machine workspace. It stores indexes, chunks, embeddings, graphs, and compile state. It is not the knowledge source of truth.

## 4. Core Data Model

The knowledge base is organized around six objects:

```text
Source    Original input: PDF, webpage, code repo, log package, screenshot, manual.
Chunk     Citable fragment from a Source, with page, section, line, anchor, or hash.
Topic     Learnable subject, such as "PCIe LTSSM" or "MSI-X Table".
Claim     Verifiable technical statement extracted into notes.
Citation  Evidence edge from Claim to Chunk.
Session   Saved question, debugging, experiment, or design discussion.
```

Example claim:

```yaml
claim_id: claim_pcie_msi_address_001
topic: pcie.interrupt.msix
type: spec_fact
text: "MSI-X uses a device memory table to store message address, message data, and vector control fields."
scope: "PCIe Base Specification 5.0"
confidence: high
citations:
  - source_id: pcie_base_spec_5_0
    locator: "sec 6.1.4, page 427"
status: accepted
```

Claim types:

```text
spec_fact       Protocol or standard fact.
vendor_fact     Vendor IP, chip manual, or datasheet fact.
code_fact       Project code, kernel code, firmware code, or driver implementation fact.
debug_fact      Observed fact from a specific issue or experiment.
inference       Reasoned conclusion based on evidence.
practice        Engineering advice or recommended practice.
```

`inference` and `practice` must not be presented as protocol facts.

## 5. Citation Format

Notes use stable internal `kb://` references:

```markdown
## MSI-X Table

MSI-X Table stores per-vector message address, message data, and mask state.

Evidence:
- [PCIe Base Spec 5.0 §6.1.4 p427](kb://source/pcie_base_spec_5_0#page=427&section=6.1.4)
- [Linux drivers/pci/msi/msi.c:1420](kb://source/linux_kernel#path=drivers/pci/msi/msi.c&line=1420)
```

`kb compile` resolves these references and verifies that the target source, page, section, path, line, or chunk hash still exists.

## 6. CLI Commands

Initial command surface:

```bash
kb init <domain>
kb ingest [path]
kb route
kb learn
kb ask "<question>"
kb save-session
kb compile
kb health
kb accept <review-id>
kb reject <review-id>
kb status
kb graph
```

Common flows:

```bash
kb ingest inbox/
kb route
kb accept routing/<run_id>
```

```bash
kb learn --goal "Build PCIe configuration space and enumeration notes"
kb compile --staged
kb accept learn_<run_id>
```

```bash
kb ask "Why can Type 0 configuration requests not cross a bridge?"
kb ask --with boot.log --with lspci.txt "Why was BAR0 not assigned?"
```

```bash
kb save-session
kb learn --from-session sessions/debug_cases/2026-05-26-bar0
kb accept learn_<run_id>
```

## 7. `kb learn` Design

`kb learn` is a controlled learning pipeline, not a one-shot summarizer.

Pipeline:

```text
1. Intake Snapshot       Freeze this run's inputs.
2. Source Profiling      Build lightweight source profiles.
3. Reading Plan          Decide a reasonable learning order.
4. Topic Extraction      Extract topics with low token cost.
5. Evidence Harvesting   Collect high-value source chunks.
6. Claim Drafting        Produce candidate claims.
7. Note Synthesis        Write human learning notes.
8. Compile & Conflict    Check citations, links, and conflicts.
9. Review & Commit       User accepts before notes are finalized.
```

### 7.1 Intake Snapshot

Every learn run records exact inputs:

```yaml
learn_run_id: learn_2026_05_26_093000
input:
  - inbox/PCIe_Base_Spec_5.0.pdf
  - inbox/Cadence_PCIE_userdoc.pdf
  - inbox/linux/drivers/pci/
mode: incremental
goal: "Build PCIe enumeration and configuration space topics"
```

The report must show what was read, skipped, and why.

### 7.2 Source Profiling

The system first reads metadata, tables of contents, headings, paths, symbols, and indexes instead of full content.

Profile fields:

- Material type: spec, book, datasheet, manual, webpage, code, log, image.
- Authority: primary, vendor, implementation, explanatory, secondary.
- Version and date.
- Structure: chapters, headings, page count, code directories, symbols.
- Candidate topics.

### 7.3 Reading Plan

The AI chooses a technical learning order:

1. Primary protocol or standard source.
2. Explanatory books and training material.
3. Vendor manuals, databooks, and controller IP documents.
4. Project code, firmware, OS driver, and logs.
5. Historical debugging cases and experiments.

For PCIe, a reasonable sequence is:

```text
Topology and layering
Transaction model
Configuration space and enumeration
BAR, capability, bus numbers
Interrupts: INTx, MSI, MSI-X
LTSSM and physical layer
DMA, IOMMU, AER, power management
Controller IP and Linux driver mapping
```

### 7.4 Low-Token Topic Extraction

Topic extraction is hierarchical:

```text
document -> chapter topics -> section topics -> chunk candidates
```

Only compact metadata is retained:

```yaml
topic_id: pcie.config.bar
name: BAR and Address Assignment
source_refs:
  - pcie_base_spec_5_0: "sec 7.5.1"
  - linux_kernel: "drivers/pci/setup-res.c"
related:
  - pcie.config.enumeration
  - pcie.transaction.memory_request
priority: high
```

This allows the system to understand large collections without sending all text to the model.

### 7.5 Evidence Harvesting

Only high-priority topics enter deep reading.

Evidence examples:

- Spec section, page, table, figure, state machine.
- Book explanation or example.
- Databook register definition or initialization sequence.
- Code function, macro, struct, or call path.
- Log line, timestamp sequence, register dump.
- Screenshot OCR plus original image reference.

Each chunk has a stable hash.

### 7.6 Claim Drafting

Candidate claims must be:

- Verifiable.
- Cited.
- Scoped by version or context.
- Typed as spec, vendor, code, debug, inference, or practice.

Example:

```yaml
type: spec_fact
claim: "Configuration Read Request TLPs use Type 0 for devices on the same bus and Type 1 when forwarded across bridges."
scope: "PCIe Base Specification 5.0"
citations:
  - kb://source/pcie_base_spec_5_0#section=2.2.6
```

### 7.7 Note Synthesis

Notes are organized for human learning:

```markdown
# Topic Title

## One-Sentence Conclusion

## Why This Mechanism Exists

## Core Concepts

## Workflow

## Key Data Structures, Registers, or Packet Formats

## Mapping to Project Code or Hardware

## Common Problems and Debugging

## Confusing Points

## Evidence

## Related Notes
```

### 7.8 Report

Every learn run produces:

```text
reports/learn/<run_id>/learn_report.md
```

The report must include:

- Goal.
- Input files.
- Sources and chunks actually read.
- Skipped files and reasons.
- New topics.
- New or modified notes.
- New claims.
- Citation list.
- Conflict list.
- Open questions.
- Token and cost estimate.
- Suggested next learning run.

## 8. `kb ask` Teacher Mode

`kb ask` should behave like a domain teacher and project debugging expert, not only a RAG search box.

Pipeline:

```text
1. Question Capture      Freeze question and attachments.
2. Intent Classification Classify the question type.
3. Evidence Retrieval    Retrieve notes, sources, code, and sessions.
4. Answer Planning       Build a teaching path.
5. Cited Answer          Generate answer with evidence.
6. Session Capture       Save discussion when useful.
7. Knowledge Feedback    Propose feedback into notes.
```

Question examples:

```bash
kb ask "Why can my Endpoint not enumerate BAR0?"
kb ask --with logs/boot.log --with dumps/lspci-vvv.txt --with src/pcie_ep.c
kb ask --image screenshots/ltssm.png "Why is LTSSM stuck in Polling?"
```

### 8.1 Question Types

```text
concept        Concept explanation.
mechanism      Mechanism or flow explanation.
code_reading   Code behavior explanation.
debug          Debugging and root-cause analysis.
design         Architecture or integration design.
experiment     Experiment planning.
comparison     Version or implementation comparison.
```

Debug answers must include:

- Symptom restatement.
- Known facts.
- Evidence references.
- Ranked hypotheses.
- Validation steps.
- Missing information.
- Confidence.
- Suggested session or note feedback.

### 8.2 Retrieval Priority

Evidence retrieval order:

1. Accepted notes and claims.
2. Primary sources: specs, databooks, IP manuals.
3. Project code, firmware, Linux or RTOS code.
4. Historical sessions and debug cases.
5. Books and training material.
6. Web pages and blogs.

The system builds an evidence pack:

```yaml
question_id: q_2026_05_26_bar0
evidence:
  - type: accepted_claim
    ref: claim_pcie_bar_probe_001
    why_relevant: "Explains BAR size probing"
  - type: source_chunk
    ref: kb://source/pcie_base_spec_5_0#section=7.5.1
    why_relevant: "BAR register definition"
  - type: code_chunk
    ref: kb://source/linux_kernel#path=drivers/pci/probe.c&line=1800
    why_relevant: "Linux resource assignment path"
```

### 8.3 Answer Shape

Default answer format:

```markdown
# Answer

## Direct Conclusion

## Background Mechanism

## Mapping to Your Project

## Evidence

## Debug Path / Next Experiment

## Uncertainty
```

For embedded, OS, firmware, and driver topics, the answer must distinguish:

- Protocol facts.
- Controller IP behavior.
- SoC glue logic.
- Firmware initialization responsibility.
- Linux or RTOS driver responsibility.
- Board, PHY, clock, and reset factors.

### 8.4 Session Capture

Sessions are saved when:

- The question includes logs, screenshots, code, or register dumps.
- A root cause or useful workaround is found.
- The user explicitly runs `kb save-session`.
- The answer produces new claims or reusable debugging method.

Debug session structure:

```markdown
# BAR0 Enumeration Failure On <project>

## Problem

## Environment

## Symptoms

## Inputs

## Evidence Reviewed

## Timeline

## Hypotheses

## Experiments

## Conclusion

## Fix / Workaround

## Follow-up

## Backlinks
```

### 8.5 Feedback Into Notes

Sessions do not directly modify accepted notes. They generate:

```text
sessions/.../feedback_plan.md
```

The user then runs:

```bash
kb learn --from-session sessions/debug_cases/<session-id>
```

The session enters the same learn, compile, conflict, and review flow.

## 9. `kb compile`

`kb compile` treats the knowledge base like source code.

Checks:

```text
1. Structure Check       Directory and config checks.
2. Source Check          Source metadata and traceability.
3. Citation Check        `kb://` reference resolution.
4. Link Check            Markdown and note graph links.
5. Claim Check           Claim schema and evidence rules.
6. Conflict Check        Semantic and scope conflicts.
7. Topic Graph Check     Topic consistency and coverage.
8. Drift Check           File/index divergence.
```

Compile modes:

```bash
kb compile --fast
kb compile --full
kb compile --staged
```

`--fast`
: Daily check for structure, links, citations, and index drift.

`--full`
: Deep check including conflict detection, topic graph, and claim graph.

`--staged`
: Gate for pending notes and new claims before user acceptance.

### 9.1 Conflict Classes

```text
direct_contradiction  Direct contradiction.
scope_mismatch        Both claims may be true, but scope is missing or wrong.
version_mismatch      Different protocol, chip, software, or board version.
terminology_conflict  Same term defined differently.
authority_conflict    Low-authority source overriding high-authority source.
```

Resolution choices:

```text
keep-old
accept-new
merge
mark-version-specific
mark-scope-specific
downgrade-confidence
reject-new
```

Conflict reports go to:

```text
reviews/conflicts/<run_id>.md
```

## 10. `kb health`

`kb health` is a static diagnostic report. It may warn without blocking.

Metrics:

- Source coverage.
- Citation quality.
- Knowledge shape.
- Conflict status.
- Learning progress.
- Session reuse.

Example output:

```text
Health: warning

Blocking:
- 3 citations point to missing source chunks
- 1 high severity conflict unresolved

Warnings:
- 12 accepted claims cite secondary sources only
- 8 source files have no profile
- topic pcie.config.bar has no backlink from enumeration learning path

Suggestions:
- run: kb compile --fix-index
- run: kb learn --topic pcie.config.bar --sources pcie_base_spec_5_0,linux_kernel
```

Supported commands:

```bash
kb health
kb health --json
kb health --topic pcie.config
kb health --fail-on high
```

## 11. Hooks

Hooks enforce critical process gates:

```text
pre-learn
  Run kb compile --fast before learning.

post-ingest
  Generate routing report. Do not write notes directly.

pre-accept
  Run kb compile --staged and block uncited or conflicting knowledge.

post-accept
  Update .kb indexes, write learn report, run kb compile --fast.

pre-ask
  Check whether .kb indexes are stale.

post-session-save
  Generate feedback_plan.md.

pre-commit or pre-sync
  Run kb compile --fast or kb health --fail-on high.
```

Hooks are extension points declared in `kb.yaml` and implemented as executable scripts or CLI plugins. Domain repositories can add stronger policies. For example, PCIe can require every accepted claim to declare whether it is `spec_fact`, `vendor_fact`, `code_fact`, `debug_fact`, `inference`, or `practice`.

## 12. Skills

Skills are workflow contracts for AI agents. They define:

- When to use the skill.
- Required context files.
- Mandatory checks.
- Output templates.
- Review gates.
- Commands that must run.

### 12.1 System Skills

```text
kb-inbox-triage
  Preview inbox, classify material, and generate routing reports.

kb-source-profile
  Build source profiles and extract candidate topics.

kb-topic-learn
  Learn by topic and generate claims, notes, and citations.

kb-cited-answer
  Answer questions with evidence packs and citations.

kb-debug-session
  Save debugging context, hypotheses, experiments, and conclusions.

kb-conflict-review
  Help the user resolve conflict reports.

kb-note-review
  Check note quality before acceptance.

kb-compile-fix
  Repair mechanical index, metadata, and link problems.
```

### 12.2 Domain Skills

PCIe examples:

```text
pcie-enumeration-teacher
  Configuration space, BAR, capabilities, bus numbers, and enumeration.

pcie-link-training-debugger
  LTSSM, link down, speed downgrade, lane width, PHY, clock, reset.

pcie-msi-msix-debugger
  MSI/MSI-X table, masking, IRQ domain, interrupt routing.

pcie-dma-iommu-debugger
  DMA address translation, cache coherency, SMMU/IOMMU, barriers.

pcie-controller-ip-reader
  Cadence, DesignWare, Xilinx, Intel controller manuals and registers.
```

Example skill manifest:

```yaml
name: pcie-link-training-debugger
description: Diagnose PCIe LTSSM and link training issues.
triggers:
  - LTSSM
  - Polling
  - Recovery
  - link down
  - Gen speed
  - lane width
required_context:
  - notes/04_physical_layer/
  - debug/ltssm_link_training/
  - sources/specs/
  - sources/datasheets/
must_check:
  - reset sequence
  - refclk presence
  - PERST#
  - lane polarity/reversal
  - equalization phase
  - controller LTSSM state register
output_template: sessions/debug_cases/templates/ltssm_debug.md
gates:
  - kb compile --fast
  - kb ask requires citations
```

## 13. MVP Phases

### Phase 1: File Framework and Compiler Skeleton

Goal: make the knowledge base organizable and checkable.

Includes:

- `kb init`
- `kb ingest`
- `kb compile --fast`
- `kb health`
- source manifest
- basic citation checker
- basic Markdown link checker
- learn report skeleton

Acceptance:

- Initialize a PCIe knowledge base.
- Import PDF, Markdown, code, log, and link material.
- Generate source metadata.
- Detect broken links and unresolved `kb://` citations.
- Output a health report.

### Phase 2: Controlled Learning Pipeline

Goal: implement the minimum `kb learn` loop.

Includes:

- source profiling
- topic extraction
- evidence harvesting
- claim drafting
- pending notes
- learn report
- pre-accept compile
- manual accept/reject

Acceptance:

- Given PCIe material, generate topic lists.
- Generate pending notes with citations.
- Block acceptance of uncited claims.
- Send conflicts or low-confidence material to `reviews/`.
- Produce a report for every learn run.

### Phase 3: Teacher Q&A and Session Capture

Goal: support long-term user interaction.

Includes:

- `kb ask`
- evidence pack
- cited answer
- debug session templates
- attachments
- `feedback_plan.md`
- `learn --from-session`

Acceptance:

- Answers include citations.
- Questions can include logs, code, screenshots, and register dumps.
- Debugging process is saved as a session.
- Sessions can feed notes only through learn, compile, and review.

### Phase 4: Conflict Detection and Domain Skills

Goal: improve quality and domain expertise.

Includes:

- claim graph
- topic graph
- conflict detector
- domain skills
- graph export
- advanced health metrics

Acceptance:

- Conflicting claims are intercepted.
- Claim types are enforced.
- PCIe domain skills guide learning and debugging.

## 14. Implementation Recommendations

Use Python for the MVP.

Recommended components:

```text
CLI: Typer or Click
Configuration: YAML plus JSON Schema
Markdown: markdown-it-py, mdformat, or mistune
PDF: PyMuPDF
Code indexing: tree-sitter plus ripgrep
Link checking: custom kb:// resolver
Index storage: JSONL, optionally SQLite
Vector search: optional later via LanceDB, Chroma, or sqlite-vec
Testing: pytest
```

Do not require a vector database in the MVP. Start with:

- source metadata
- heading index
- keyword and topic index
- claim index
- citation graph
- ripgrep

Add embeddings after the file and citation discipline is working.

## 15. Non-Negotiable Design Principles

1. Files are the source of truth; `.kb/` is rebuildable.
2. Original sources are read-only after archival.
3. AI cannot bypass review and compile gates.
4. Important claims require citations.
5. New knowledge is staged before acceptance.
6. Conflicts require explicit user decisions.
7. Sessions are experience inputs, not direct note mutations.
8. Skills define workflow discipline.
9. Learning is topic-incremental, not whole-library summarization.

## 16. Open Implementation Decisions

These are implementation choices, not design blockers:

- Exact CLI framework: Typer or Click.
- Initial index store: JSONL only or JSONL plus SQLite.
- Markdown parser and formatter.
- First supported PDF extraction quality level.
- Whether `kb accept` writes directly or opens an editable review patch first.
- Whether the first embedding backend is omitted or optional.

## 17. Repository Note

This design was written in `/home/luyuan/docs/superpowers`, which was initially an empty directory and not a git repository. The target remote provided by the user is:

```text
https://github.com/kindresy/kb_agent
```
