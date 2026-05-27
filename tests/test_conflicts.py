from kb_agent.conflicts import detect_claim_conflicts


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


def test_different_topics_do_not_conflict():
    accepted = [claim("accepted", "topic.a", "BAR0 is assigned by firmware.")]
    candidate = [claim("candidate", "topic.b", "BAR0 is not assigned by firmware.")]

    assert detect_claim_conflicts(accepted, candidate, "learn_test") == []
