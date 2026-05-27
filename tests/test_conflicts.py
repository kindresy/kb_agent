import json
from pathlib import Path

import pytest

from kb_agent.conflicts import detect_claim_conflicts, write_conflict_artifacts
from kb_agent.sources import SourceRecord, write_source_index
from tests.conftest import run_cli


def claim(claim_id: str, topic_id: str, text: str) -> dict:
    return {
        "claim_id": claim_id,
        "topic_id": topic_id,
        "type": "source_observation",
        "claim": text,
        "citations": [f"kb://source/{claim_id}"],
        "confidence": "deterministic",
    }


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(row, sort_keys=True) for row in rows)
        + ("\n" if rows else ""),
        encoding="utf-8",
    )


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def read_jsonl_or_empty(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return read_jsonl(path)


def write_source(root: Path, source_id: str) -> SourceRecord:
    path = root / "sources" / "manuals" / f"{source_id}.md"
    path.write_text(f"# {source_id}\n", encoding="utf-8")
    return SourceRecord(
        source_id=source_id,
        type="manual",
        title=source_id,
        path=path.relative_to(root).as_posix(),
        original_path=str(path),
        hash=f"sha256:{source_id}",
    )


def initialize_kb_with_sources(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, source_ids: list[str]
) -> Path:
    monkeypatch.chdir(tmp_path)
    assert run_cli("init", "pcie").exit_code == 0
    root = tmp_path / "pcie"
    write_source_index(root, [write_source(root, source_id) for source_id in source_ids])
    return root


def test_compile_fast_fails_when_accepted_claims_conflict(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    root = initialize_kb_with_sources(tmp_path, monkeypatch, ["accepted", "candidate"])
    write_jsonl(
        root / ".kb" / "claims" / "claims.jsonl",
        [
            claim("accepted", "topic.bar", "BAR0 is assigned by firmware."),
            claim("candidate", "topic.bar", "BAR0 is not assigned by firmware."),
        ],
    )
    monkeypatch.chdir(root)

    result = run_cli("compile", "--fast")

    assert result.exit_code == 1
    assert "claim_conflict" in result.output
    assert "accepted claims conflict: conflict.accepted.1" in result.output
    state = json.loads((root / ".kb" / "compile_state.json").read_text())
    assert state["status"] == "failed"
    conflict_findings = [
        finding for finding in state["findings"] if finding["code"] == "claim_conflict"
    ]
    assert conflict_findings == [
        {
            "severity": "error",
            "code": "claim_conflict",
            "path": ".kb/claims/claims.jsonl",
            "message": "accepted claims conflict: conflict.accepted.1",
        }
    ]


def test_accept_blocks_candidate_claims_that_conflict_with_accepted_claims(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    root = initialize_kb_with_sources(tmp_path, monkeypatch, ["accepted", "candidate"])
    run_id = "learn_conflict"
    accepted_claim = claim("accepted", "topic.bar", "BAR0 is assigned by firmware.")
    candidate_claim = claim(
        "candidate", "topic.bar", "BAR0 is not assigned by firmware."
    )
    write_jsonl(root / ".kb" / "claims" / "claims.jsonl", [accepted_claim])
    run_root = root / ".kb" / "learn_runs" / run_id
    write_jsonl(run_root / "claims.jsonl", [candidate_claim])
    write_jsonl(run_root / "topics.jsonl", [{"topic_id": "topic.bar"}])
    write_jsonl(run_root / "chunks.jsonl", [{"chunk_id": "chunk.one"}])
    pending_note = root / "reviews" / "pending_notes" / run_id / "topic.bar.md"
    pending_note.parent.mkdir(parents=True, exist_ok=True)
    pending_note.write_text("# BAR\n", encoding="utf-8")
    monkeypatch.chdir(root)

    result = run_cli("accept", run_id)

    assert result.exit_code == 1
    assert "reviews/conflicts/learn_conflict/conflict_report.md" in result.output
    conflict_root = root / "reviews" / "conflicts" / run_id
    assert (conflict_root / "conflicts.jsonl").is_file()
    assert (conflict_root / "conflict_report.md").is_file()
    assert read_jsonl(conflict_root / "conflicts.jsonl")[0]["rule"] == "negation_polarity"
    assert read_jsonl(root / ".kb" / "claims" / "claims.jsonl") == [accepted_claim]
    assert read_jsonl_or_empty(root / ".kb" / "topics" / "topics.jsonl") == []
    assert read_jsonl_or_empty(root / ".kb" / "chunks" / "chunks.jsonl") == []
    assert not (root / "notes" / "concepts" / "generated" / "topic.bar.md").exists()


def test_accept_malformed_topics_does_not_partially_promote(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    root = initialize_kb_with_sources(tmp_path, monkeypatch, ["candidate"])
    run_id = "learn_bad_topics"
    candidate_claim = claim("candidate", "topic.bar", "BAR0 is assigned by firmware.")
    run_root = root / ".kb" / "learn_runs" / run_id
    write_jsonl(run_root / "claims.jsonl", [candidate_claim])
    (run_root / "topics.jsonl").write_text("{not valid json}\n", encoding="utf-8")
    write_jsonl(run_root / "chunks.jsonl", [{"chunk_id": "chunk.one"}])
    pending_note = root / "reviews" / "pending_notes" / run_id / "topic.bar.md"
    pending_note.parent.mkdir(parents=True, exist_ok=True)
    pending_note.write_text("# BAR\n", encoding="utf-8")
    monkeypatch.chdir(root)

    result = run_cli("accept", run_id)

    assert result.exit_code == 1
    assert not (root / "notes" / "concepts" / "generated" / "topic.bar.md").exists()
    assert read_jsonl_or_empty(root / ".kb" / "topics" / "topics.jsonl") == []
    assert read_jsonl_or_empty(root / ".kb" / "chunks" / "chunks.jsonl") == []
    assert read_jsonl_or_empty(root / ".kb" / "claims" / "claims.jsonl") == []


@pytest.mark.parametrize("run_id", ["", "../outside", "nested/run", "/absolute", ".."])
def test_accept_rejects_invalid_pathlike_run_id_before_path_traversal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, run_id: str
):
    root = initialize_kb_with_sources(tmp_path, monkeypatch, ["candidate"])
    traversal_run = root / ".kb" / "outside"
    traversal_run.mkdir(parents=True)
    write_jsonl(traversal_run / "claims.jsonl", [])
    (root / "reviews" / "outside").mkdir(parents=True)
    monkeypatch.chdir(root)

    result = run_cli("accept", run_id)

    assert result.exit_code == 1
    assert "run_id must be a safe single path component" in result.output


def test_detects_negation_polarity_conflict():
    accepted = [claim("accepted", "topic.bar", "BAR0 is assigned by firmware.")]
    candidate = [claim("candidate", "topic.bar", "BAR0 is not assigned by firmware.")]

    conflicts = detect_claim_conflicts(accepted, candidate, "learn_test")

    assert len(conflicts) == 1
    assert conflicts[0].rule == "negation_polarity"
    assert conflicts[0].accepted_claim_id == "accepted"
    assert conflicts[0].candidate_claim_id == "candidate"


def test_detects_modal_conflict():
    accepted = [
        claim("accepted", "topic.ltssm", "PERST must be asserted before link training.")
    ]
    candidate = [
        claim(
            "candidate",
            "topic.ltssm",
            "PERST must not be asserted before link training.",
        )
    ]

    conflicts = detect_claim_conflicts(accepted, candidate, "learn_test")

    assert len(conflicts) == 1
    assert conflicts[0].rule == "modal_conflict"


def test_detects_single_valued_assignment_conflict():
    accepted = [claim("accepted", "topic.msi", "MSI vector count is 32.")]
    candidate = [claim("candidate", "topic.msi", "MSI vector count is 64.")]

    conflicts = detect_claim_conflicts(accepted, candidate, "learn_test")

    assert len(conflicts) == 1
    assert conflicts[0].rule == "single_valued_assignment"


def test_detects_equals_single_valued_assignment_conflict():
    accepted = [claim("accepted", "topic.msi", "MSI vector count = 32.")]
    candidate = [claim("candidate", "topic.msi", "MSI vector count = 64.")]

    conflicts = detect_claim_conflicts(accepted, candidate, "learn_test")

    assert len(conflicts) == 1
    assert conflicts[0].rule == "single_valued_assignment"


def test_modal_conflict_uses_word_boundaries_for_prohibition_phrases():
    accepted = [
        claim(
            "accepted",
            "topic.ltssm",
            "PERST must be asserted whenever link training starts.",
        )
    ]
    candidate = [
        claim(
            "candidate",
            "topic.ltssm",
            "PERST must not be asserted whenever link training starts.",
        )
    ]

    conflicts = detect_claim_conflicts(accepted, candidate, "learn_test")

    assert len(conflicts) == 1
    assert conflicts[0].rule == "modal_conflict"


def test_multiple_conflict_ids_are_deterministic_and_order_stable():
    accepted = [
        claim("accepted_a", "topic.bar", "BAR0 is assigned by firmware."),
        claim("accepted_b", "topic.msi", "MSI vector count = 32."),
    ]
    candidate = [
        claim("candidate_a", "topic.bar", "BAR0 is not assigned by firmware."),
        claim("candidate_b", "topic.msi", "MSI vector count = 64."),
    ]

    conflicts = detect_claim_conflicts(accepted, candidate, "learn_test")

    assert [conflict.conflict_id for conflict in conflicts] == [
        "conflict.learn_test.1",
        "conflict.learn_test.2",
    ]
    assert [conflict.accepted_claim_id for conflict in conflicts] == [
        "accepted_a",
        "accepted_b",
    ]
    assert [conflict.candidate_claim_id for conflict in conflicts] == [
        "candidate_a",
        "candidate_b",
    ]


def test_different_topics_do_not_conflict():
    accepted = [claim("accepted", "topic.a", "BAR0 is assigned by firmware.")]
    candidate = [claim("candidate", "topic.b", "BAR0 is not assigned by firmware.")]

    assert detect_claim_conflicts(accepted, candidate, "learn_test") == []


def test_write_conflict_artifacts_writes_jsonl_and_report_under_run_path(
    tmp_path: Path,
):
    conflicts = detect_claim_conflicts(
        [claim("accepted", "topic.bar", "BAR0 is assigned by firmware.")],
        [claim("candidate", "topic.bar", "BAR0 is not assigned by firmware.")],
        "learn_test",
    )

    report_path = write_conflict_artifacts(tmp_path, "learn_test", conflicts)

    assert report_path == "reviews/conflicts/learn_test/conflict_report.md"
    conflict_root = tmp_path / "reviews" / "conflicts" / "learn_test"
    rows = [
        json.loads(line)
        for line in (conflict_root / "conflicts.jsonl").read_text().splitlines()
    ]
    assert rows == [
        {
            "accepted_citations": ["kb://source/accepted"],
            "accepted_claim": "BAR0 is assigned by firmware.",
            "accepted_claim_id": "accepted",
            "candidate_citations": ["kb://source/candidate"],
            "candidate_claim": "BAR0 is not assigned by firmware.",
            "candidate_claim_id": "candidate",
            "conflict_id": "conflict.learn_test.1",
            "message": "candidate claim conflicts with an accepted claim",
            "rule": "negation_polarity",
            "severity": "error",
            "topic_id": "topic.bar",
        }
    ]
    report_text = (conflict_root / "conflict_report.md").read_text()
    assert "Conflicts: 1" in report_text
    assert "## conflict.learn_test.1" in report_text


@pytest.mark.parametrize("run_id", ["", "../outside", "nested/run", "/absolute", ".."])
def test_write_conflict_artifacts_rejects_invalid_pathlike_run_id(
    tmp_path: Path, run_id: str
):
    with pytest.raises(ValueError, match="run_id"):
        write_conflict_artifacts(tmp_path, run_id, [])
