from kb_agent.evidence import select_prompt_evidence


def test_select_prompt_evidence_prioritizes_phrase_and_excerpt_matches():
    evidence = [
        {
            "type": "source",
            "ref": "kb://source/generic",
            "why_relevant": "fallback source evidence",
            "excerpt": "Generic PCIe overview",
        },
        {
            "type": "source_chunk",
            "ref": "kb://source/pci#chunk=bar",
            "why_relevant": "chunk text matched question terms",
            "excerpt": "PCIe BAR assignment programs Base Address Registers for memory windows.",
        },
    ]

    selected, metadata = select_prompt_evidence(
        "Explain PCIe BAR assignment", evidence, budget=1
    )

    assert selected[0]["ref"] == "kb://source/pci#chunk=bar"
    assert selected[0]["score"] > 0
    assert metadata == {
        "method": "deterministic_token_phrase_v1",
        "budget": 1,
        "candidate_count": 2,
        "selected_count": 1,
        "omitted_count": 1,
    }


def test_select_prompt_evidence_keeps_stable_order_for_equal_scores():
    evidence = [
        {
            "type": "source",
            "ref": "kb://source/first",
            "why_relevant": "source metadata matched question terms",
            "excerpt": "BAR overview",
        },
        {
            "type": "source",
            "ref": "kb://source/second",
            "why_relevant": "source metadata matched question terms",
            "excerpt": "BAR overview",
        },
    ]

    selected, metadata = select_prompt_evidence("BAR", evidence, budget=2)

    assert [item["ref"] for item in selected] == [
        "kb://source/first",
        "kb://source/second",
    ]
    assert metadata["selected_count"] == 2
    assert metadata["omitted_count"] == 0


def test_select_prompt_evidence_handles_empty_evidence():
    selected, metadata = select_prompt_evidence("BAR", [], budget=32)

    assert selected == []
    assert metadata == {
        "method": "deterministic_token_phrase_v1",
        "budget": 32,
        "candidate_count": 0,
        "selected_count": 0,
        "omitted_count": 0,
    }

