# KB Agent Project Continuation

Last updated: 2026-05-28

## Current Branch and PR

- Repository: `kindresy/kb_agent`
- Active worktree: `/home/luyuan/docs/superpowers/.worktrees/phase-5-anthropic-ask`
- Branch: `phase-5-anthropic-ask`
- PR: https://github.com/kindresy/kb_agent/pull/4
- Current head: `1d89b55 feat: improve LLM session review notes`
- Base on main: `2535e68 Merge pull request #3 from kindresy/phase-4-graph-conflicts`

Do not continue from `/home/luyuan/docs/superpowers` main until PR #4 is merged
or the Phase 5 branch is checked out. Phase 5 work is still on the PR branch.

## Verification Snapshot

Last verified command:

```bash
uv run --extra dev pytest -q
```

Last result:

```text
113 passed in 1.07s
```

## Implemented Phases

### Phase 1: Local CLI and KB Layout

Status: complete and merged.

Implemented:

- `kb init`
- `kb ingest`
- `kb compile --fast`
- `kb health`
- local file-first layout
- Markdown package ingest with adjacent assets

### Phase 2: Deterministic Learn Skeleton

Status: complete and merged.

Implemented:

- `kb learn`
- `kb accept`
- staged learn runs under `.kb/learn_runs/<run_id>/`
- pending notes under `reviews/pending_notes/<run_id>/`
- reports under `reports/learn/<run_id>/`
- citation validation and accept gate

Important limitation:

- This is still a deterministic skeleton. It does not yet deeply learn source
  material.

### Phase 3: Deterministic Ask and Sessions

Status: complete and merged.

Implemented:

- `kb ask`
- ask sessions under `sessions/questions/` or `sessions/debug_cases/`
- attachments
- evidence packs
- `kb learn --from-session`

### Phase 4: Graph and Conflicts

Status: complete and merged.

Implemented:

- `kb graph export`
- deterministic graph artifacts
- conflict detection
- compile and accept conflict gates
- hooks were explicitly removed from scope by user request.

### Phase 5.1: Optional LLM Ask

Status: implemented on PR #4.

Implemented:

- `kb ask --llm`
- Anthropic provider abstraction
- standard `ANTHROPIC_API_KEY`
- Claude Code style settings from `~/.claude/settings.json`
- `ANTHROPIC_AUTH_TOKEN`
- `ANTHROPIC_BASE_URL`
- `ANTHROPIC_CUSTOM_HEADERS`
- `ANTHROPIC_DEFAULT_SONNET_MODEL`
- clean API error wrapping
- partial session cleanup on LLM failure

### Phase 5.2: Evidence Rerank for LLM Ask

Status: implemented on PR #4.

Implemented:

- deterministic evidence scoring in `src/kb_agent/evidence.py`
- `prompt_evidence` in `evidence_pack.json`
- `evidence_selection` metadata
- LLM provider receives only bounded `prompt_evidence`
- full retrieved `evidence` remains in session for audit

### Phase 5.3: LLM Session Review Notes

Status: implemented on PR #4.

Implemented:

- richer pending notes for LLM `kb learn --from-session`
- original question
- unverified LLM answer excerpt
- prompt evidence refs and scores
- `llm_session_unverified` provenance
- no automatic acceptance of LLM output

## Current Product Assessment

The project is now an MVP+ CLI knowledge-base product:

- Python source: about 3.7k lines.
- Tests: 113 tests.
- Core modules: ingest, learn, ask, LLM, compile, health, graph, conflicts.
- The CLI is usable for local file-based KB experiments.

The core limitation is now `kb learn`, not `kb ask`.

`kb ask --llm` is usable, but answer quality depends on source chunks. Current
`kb learn` still produces weak chunks and generic claims. It needs a real
Learning Engine v1.

## Next Recommended Phase

Start Phase 6: Learning Engine v1.

Recommended first subphase:

### Phase 6.1: Section Chunking and Source-Aware Learning

Goal:

Improve `kb learn` so it creates section-level evidence chunks and more useful
pending notes.

Scope:

- Split `learn.py` responsibilities into a small `kb_agent/learning/` package.
- Add deterministic section chunking:
  - Markdown: split by headings.
  - Text/log: split by line windows.
  - Code: split by symbol or line windows.
- Each chunk should include:
  - `chunk_id`
  - `source_id`
  - `source_path`
  - `topic_id`
  - `heading`
  - `start_line`
  - `end_line`
  - `text`
  - `hash`
  - `citation`
- `build_topics()` should use section headings and symbols more directly.
- `build_claims()` should generate conservative but more specific claims from
  section chunks.
- pending notes should include section excerpts and line ranges.
- `kb ask` should improve automatically because it already retrieves
  `.kb/chunks` and reranks evidence.

Explicit non-goals for Phase 6.1:

- No embeddings.
- No vector DB.
- No LLM calls during `kb learn`.
- No direct accepted-note writes.
- No bypass of `kb accept`, conflict checks, or compile checks.

Suggested files:

- Create `src/kb_agent/learning/__init__.py`
- Create `src/kb_agent/learning/chunking.py`
- Create `src/kb_agent/learning/topics.py`
- Create `src/kb_agent/learning/claims.py`
- Create `src/kb_agent/learning/notes.py`
- Modify `src/kb_agent/learn.py` to orchestrate these modules.
- Add tests:
  - `tests/test_learning_chunking.py`
  - updates to `tests/test_learn.py`
  - updates to `tests/test_ask.py`

Suggested acceptance tests:

1. Markdown with two headings generates two section chunks.
2. Chunk citations include `kb://source/<id>#chunk=<chunk_id>`.
3. Chunks include `heading`, `start_line`, and `end_line`.
4. `kb ask "BAR assignment"` retrieves the BAR section chunk.
5. `kb accept <run_id>` still promotes notes and appends topics/chunks/claims.
6. `kb compile --fast` still passes.
7. Full suite passes.

## Recovery Instructions for Future Agent

When resuming:

1. Start in:

   ```bash
   cd /home/luyuan/docs/superpowers/.worktrees/phase-5-anthropic-ask
   ```

2. Check state:

   ```bash
   git status --short --branch
   git log --oneline --decorate -6
   uv run --extra dev pytest -q
   ```

3. If PR #4 has not been merged, continue on branch `phase-5-anthropic-ask`.

4. If PR #4 has been merged, switch to main and create a new worktree/branch for
   Phase 6:

   ```bash
   cd /home/luyuan/docs/superpowers
   git checkout main
   git pull
   git worktree add .worktrees/phase-6-learning-engine -b phase-6-learning-engine
   cd .worktrees/phase-6-learning-engine
   uv run --extra dev pytest -q
   ```

5. Use these skills before implementation:

   - `using-superpowers`
   - `brainstorming`
   - `writing-plans`
   - `test-driven-development`
   - `verification-before-completion`

6. First work item:

   Write Phase 6.1 spec and plan:

   - `docs/superpowers/specs/YYYY-MM-DD-kb-agent-phase-6-1-section-learning-design.md`
   - `docs/superpowers/plans/YYYY-MM-DD-kb-agent-phase-6-1-section-learning.md`

7. Then implement with TDD.

## Operational Notes

- User prefers Chinese conversation.
- User wants local CLI + filesystem first.
- User explicitly removed hooks from scope.
- User has a Claude Code style proxy config at `~/.claude/settings.json`.
- Do not print secrets from that file.
- `kb ask --llm` can use that config automatically after PR #4.
- Current `main` may not include Phase 5 until PR #4 is merged.

