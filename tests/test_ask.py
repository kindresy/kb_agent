import json
from pathlib import Path

from kb_agent.ask import MAX_SOURCE_EXCERPT_BYTES, run_ask
from kb_agent.llm.base import LLMResponse
from tests.conftest import run_cli


def session_path_from(output: str, root: Path) -> Path:
    line = next(line for line in output.splitlines() if line.startswith("Session: "))
    return root / line.split("Session: ", 1)[1]


def test_ask_prints_cited_answer_and_writes_session(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert run_cli("init", "pcie").exit_code == 0
    source = tmp_path / "manual.md"
    source.write_text("# Configuration Space\nBAR notes\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path / "pcie")
    assert run_cli("ingest", str(source)).exit_code == 0

    result = run_cli("ask", "What is Configuration Space?")

    assert result.exit_code == 0
    assert "# Answer" in result.output
    assert "kb://source/manual" in result.output
    session = session_path_from(result.output, tmp_path / "pcie")
    assert session.parent.name == "questions"
    assert (session / "question.md").is_file()
    assert (session / "evidence_pack.json").is_file()
    assert (session / "answer.md").is_file()
    assert (session / "feedback_plan.md").is_file()
    evidence = json.loads((session / "evidence_pack.json").read_text())
    assert evidence["question"] == "What is Configuration Space?"
    assert evidence["answer_mode"] == "deterministic"
    assert evidence["llm_provider"] is None
    assert evidence["llm_model"] is None
    assert evidence["evidence"][0]["ref"] == "kb://source/manual"
    assert evidence["prompt_evidence"][0]["ref"] == "kb://source/manual"
    assert evidence["evidence_selection"]["candidate_count"] == len(evidence["evidence"])
    assert evidence["evidence_selection"]["selected_count"] == len(
        evidence["prompt_evidence"]
    )


def test_ask_with_attachment_writes_debug_session_and_copies_file(
    tmp_path: Path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    assert run_cli("init", "pcie").exit_code == 0
    source = tmp_path / "manual.md"
    source.write_text("# BAR Assignment\nBAR notes\n", encoding="utf-8")
    boot_log = tmp_path / "boot.log"
    boot_log.write_text("BAR0 not assigned\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path / "pcie")
    assert run_cli("ingest", str(source)).exit_code == 0

    result = run_cli("ask", "--with", str(boot_log), "Why was BAR0 not assigned?")

    assert result.exit_code == 0
    session = session_path_from(result.output, tmp_path / "pcie")
    assert session.parent.name == "debug_cases"
    copied = session / "attachments" / "boot.log"
    assert copied.read_text() == "BAR0 not assigned\n"
    evidence = json.loads((session / "evidence_pack.json").read_text())
    assert evidence["attachments"][0]["original_path"] == str(boot_log)
    assert evidence["attachments"][0]["copied_path"].endswith("attachments/boot.log")


def test_ask_missing_attachment_fails_without_session(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert run_cli("init", "pcie").exit_code == 0
    monkeypatch.chdir(tmp_path / "pcie")

    result = run_cli("ask", "--with", str(tmp_path / "missing.log"), "Why fail?")

    assert result.exit_code == 1
    assert "attachment does not exist" in result.output
    assert not any((tmp_path / "pcie" / "sessions" / "questions").iterdir())
    assert not any((tmp_path / "pcie" / "sessions" / "debug_cases").iterdir())


def test_repeated_ask_allocates_unique_session_ids(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert run_cli("init", "pcie").exit_code == 0
    source = tmp_path / "manual.md"
    source.write_text("# Configuration Space\nBAR notes\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path / "pcie")
    assert run_cli("ingest", str(source)).exit_code == 0

    first = run_cli("ask", "What is Configuration Space?")
    second = run_cli("ask", "What is Configuration Space?")

    assert first.exit_code == 0
    assert second.exit_code == 0
    first_session = session_path_from(first.output, tmp_path / "pcie")
    second_session = session_path_from(second.output, tmp_path / "pcie")
    assert first_session != second_session
    assert first_session.is_dir()
    assert second_session.is_dir()


def test_ask_retrieves_matching_claims_notes_and_chunks(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert run_cli("init", "pcie").exit_code == 0
    source = tmp_path / "manual.md"
    source.write_text("# BAR Assignment\nBAR notes\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path / "pcie")
    assert run_cli("ingest", str(source)).exit_code == 0
    learn = run_cli("learn")
    run_id = learn.output.split("Learn run:", 1)[1].splitlines()[0].strip()
    assert run_cli("accept", run_id).exit_code == 0

    result = run_cli("ask", "Explain BAR Assignment")

    assert result.exit_code == 0
    session = session_path_from(result.output, tmp_path / "pcie")
    evidence = json.loads((session / "evidence_pack.json").read_text())
    evidence_types = {item["type"] for item in evidence["evidence"]}
    assert {"accepted_claim", "accepted_note", "source_chunk", "source"} <= evidence_types


def test_run_ask_llm_mode_writes_provider_answer_and_metadata(
    tmp_path: Path, monkeypatch
):
    provider_evidence_refs = []

    class FakeProvider:
        def answer(self, *, question, intent, evidence, attachments):
            assert question == "Explain BAR Assignment"
            assert intent == "concept"
            assert evidence
            assert attachments == []
            provider_evidence_refs.extend(item["ref"] for item in evidence)
            return LLMResponse(
                text="# Answer\n\nLLM cited answer using kb://source/manual",
                provider="anthropic",
                model="claude-sonnet-4-20250514",
            )

    monkeypatch.chdir(tmp_path)
    assert run_cli("init", "pcie").exit_code == 0
    source = tmp_path / "manual.md"
    source.write_text("# BAR Assignment\nBAR notes\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path / "pcie")
    assert run_cli("ingest", str(source)).exit_code == 0

    result = run_ask(
        tmp_path / "pcie",
        "Explain BAR Assignment",
        use_llm=True,
        llm_provider=FakeProvider(),
    )

    session = tmp_path / "pcie" / result.session_path
    assert result.answer == "# Answer\n\nLLM cited answer using kb://source/manual"
    assert (session / "answer.md").read_text(encoding="utf-8") == result.answer
    evidence = json.loads((session / "evidence_pack.json").read_text())
    assert evidence["answer_mode"] == "llm"
    assert evidence["llm_provider"] == "anthropic"
    assert evidence["llm_model"] == "claude-sonnet-4-20250514"
    assert evidence["evidence"][0]["excerpt"] == "# BAR Assignment\nBAR notes"
    assert evidence["prompt_evidence"][0]["ref"] == "kb://source/manual"
    assert evidence["prompt_evidence"][0]["score"] > 0
    assert evidence["evidence_selection"]["method"] == "deterministic_token_phrase_v1"
    assert evidence["evidence_selection"]["candidate_count"] == len(evidence["evidence"])
    assert provider_evidence_refs == [
        item["ref"] for item in evidence["prompt_evidence"]
    ]


def test_ask_llm_passes_reranked_prompt_evidence_to_provider(
    tmp_path: Path, monkeypatch
):
    provider_evidence_refs = []

    class FakeProvider:
        def answer(self, *, question, intent, evidence, attachments):
            provider_evidence_refs.extend(item["ref"] for item in evidence)
            return LLMResponse(
                text="# Answer\n\nLLM answer",
                provider="anthropic",
                model="claude-sonnet-4-20250514",
            )

    monkeypatch.chdir(tmp_path)
    assert run_cli("init", "pcie").exit_code == 0
    generic = tmp_path / "pcie.md"
    generic.write_text("# PCIe Overview\nGeneric PCIe text\n", encoding="utf-8")
    bar = tmp_path / "pcie-bar-assignment.md"
    bar.write_text(
        "# PCIe BAR Assignment\nBAR assignment maps Base Address Registers.\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path / "pcie")
    assert run_cli("ingest", str(generic)).exit_code == 0
    assert run_cli("ingest", str(bar)).exit_code == 0

    result = run_ask(
        tmp_path / "pcie",
        "Explain PCIe BAR assignment",
        use_llm=True,
        llm_provider=FakeProvider(),
    )

    session = tmp_path / "pcie" / result.session_path
    evidence_pack = json.loads((session / "evidence_pack.json").read_text())
    assert len(evidence_pack["evidence"]) == 2
    assert evidence_pack["prompt_evidence"][0]["ref"] == "kb://source/pcie_bar_assignment"
    assert provider_evidence_refs[0] == "kb://source/pcie_bar_assignment"


def test_ask_source_excerpt_is_bounded_for_large_text_sources(
    tmp_path: Path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    assert run_cli("init", "pcie").exit_code == 0
    source = tmp_path / "large_manual.md"
    source.write_text("# BAR Assignment\n" + ("BAR notes\n" * 20_000), encoding="utf-8")
    monkeypatch.chdir(tmp_path / "pcie")
    assert run_cli("ingest", str(source)).exit_code == 0

    result = run_cli("ask", "Explain BAR Assignment")

    assert result.exit_code == 0
    session = session_path_from(result.output, tmp_path / "pcie")
    evidence = json.loads((session / "evidence_pack.json").read_text())
    excerpt = evidence["evidence"][0]["excerpt"]
    assert len(excerpt.encode("utf-8")) < MAX_SOURCE_EXCERPT_BYTES
    assert excerpt.endswith("...")


def test_ask_llm_without_api_key_fails_before_creating_session(
    tmp_path: Path, monkeypatch
):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    monkeypatch.setattr("kb_agent.llm.anthropic_provider.load_claude_settings_env", lambda: {})
    monkeypatch.chdir(tmp_path)
    assert run_cli("init", "pcie").exit_code == 0
    monkeypatch.chdir(tmp_path / "pcie")

    result = run_cli("ask", "--llm", "What is Configuration Space?")

    assert result.exit_code == 1
    assert "ANTHROPIC_API_KEY or ANTHROPIC_AUTH_TOKEN" in result.output
    assert not any((tmp_path / "pcie" / "sessions" / "questions").iterdir())


def test_run_ask_llm_provider_failure_does_not_leave_partial_session(
    tmp_path: Path, monkeypatch
):
    class FailingProvider:
        def answer(self, *, question, intent, evidence, attachments):
            raise ValueError("provider failed")

    monkeypatch.chdir(tmp_path)
    assert run_cli("init", "pcie").exit_code == 0
    source = tmp_path / "manual.md"
    source.write_text("# BAR Assignment\nBAR notes\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path / "pcie")
    assert run_cli("ingest", str(source)).exit_code == 0

    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    monkeypatch.setattr("kb_agent.llm.anthropic_provider.load_claude_settings_env", lambda: {})
    result = run_cli("ask", "--llm", "Explain BAR Assignment")
    assert result.exit_code == 1
    assert "ANTHROPIC_API_KEY or ANTHROPIC_AUTH_TOKEN" in result.output
    assert not any((tmp_path / "pcie" / "sessions" / "questions").iterdir())

    with monkeypatch.context() as context:
        context.setenv("ANTHROPIC_API_KEY", "test-key")
        try:
            run_ask(
                tmp_path / "pcie",
                "Explain BAR Assignment",
                use_llm=True,
                llm_provider=FailingProvider(),
            )
        except ValueError as exc:
            assert "provider failed" in str(exc)
        else:
            raise AssertionError("provider failure should raise ValueError")

    assert not any((tmp_path / "pcie" / "sessions" / "questions").iterdir())
