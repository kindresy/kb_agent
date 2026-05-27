import json
from pathlib import Path

import pytest

from kb_agent.conflicts import detect_claim_conflicts, write_conflict_artifacts


def claim(claim_id: str, topic_id: str, text: str) -> dict:
    return {
        "claim_id": claim_id,
        "topic_id": topic_id,
        "type": "source_observation",
        "claim": text,
        "citations": [f"kb://source/{claim_id}"],
        "confidence": "deterministic",
    }


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
