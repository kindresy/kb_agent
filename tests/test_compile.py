import json
from pathlib import Path

from kb_agent.markdown import extract_kb_source_refs, extract_markdown_links
from tests.conftest import run_cli


def test_extract_kb_source_refs_from_markdown():
    text = """
Evidence:
- [Spec](kb://source/pcie_base_spec_5_0#section=7.5.1)
- [Linux](kb://source/linux_kernel#path=drivers/pci/probe.c&line=1800)
"""

    refs = extract_kb_source_refs(text)

    assert refs == ["pcie_base_spec_5_0", "linux_kernel"]


def test_extract_relative_markdown_links():
    text = """
[BAR](../mechanisms/bar.md)
[Foo](foo.md)
[Docs](docs/foo.md)
[External](https://example.com)
[Source](kb://source/pcie_base_spec_5_0#section=7.5.1)
"""

    links = extract_markdown_links(text)

    assert links == ["../mechanisms/bar.md", "foo.md", "docs/foo.md"]


def test_extract_markdown_links_skips_non_relative_file_targets():
    text = """
[Anchor](#section)
[Root](/notes/foo.md)
[ProtocolRelative](//example.com/x)
[FTP](ftp://example.com/x)
[Tel](tel:123)
[File](file:///tmp/x)
[HTTP](http://example.com/x)
[HTTPS](https://example.com/x)
[Mail](mailto:user@example.com)
[Source](kb://source/pcie_base_spec_5_0#section=7.5.1)
[Relative](notes/foo.md)
"""

    links = extract_markdown_links(text)

    assert links == ["notes/foo.md"]


def test_extract_markdown_links_ignores_optional_titles():
    text = """
[BAR](../mechanisms/bar.md "title")
[Foo](foo.md 'title')
[Docs](docs/foo.md (title))
"""

    links = extract_markdown_links(text)

    assert links == ["../mechanisms/bar.md", "foo.md", "docs/foo.md"]


def test_extract_markdown_links_strips_fragments_from_relative_files():
    text = """
[Section](notes/foo.md#intro)
"""

    links = extract_markdown_links(text)

    assert links == ["notes/foo.md"]


def test_extract_markdown_links_allows_parentheses_in_relative_files():
    text = """
[Doc](notes/foo(bar).md)
"""

    links = extract_markdown_links(text)

    assert links == ["notes/foo(bar).md"]


def test_extract_markdown_links_allows_angle_wrapped_spaces():
    text = """
[Doc](<notes/foo bar.md>)
"""

    links = extract_markdown_links(text)

    assert links == ["notes/foo bar.md"]


def test_extract_markdown_links_unescapes_spaces_in_relative_files():
    text = r"""
[Doc](notes/foo\ bar.md)
"""

    links = extract_markdown_links(text)

    assert links == ["notes/foo bar.md"]


def test_extract_markdown_links_preserves_escaped_hash_in_relative_files():
    text = r"""
[Doc](notes/foo\#bar.md)
[Section](notes/foo.md#intro)
"""

    links = extract_markdown_links(text)

    assert links == ["notes/foo#bar.md", "notes/foo.md"]


def test_extract_markdown_links_allows_angle_wrapped_destinations_with_titles():
    text = """
[Doc](<notes/foo bar.md> "title")
"""

    links = extract_markdown_links(text)

    assert links == ["notes/foo bar.md"]


def test_compile_fast_passes_clean_initialized_repo(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert run_cli("init", "pcie").exit_code == 0
    monkeypatch.chdir(tmp_path / "pcie")

    result = run_cli("compile", "--fast")

    assert result.exit_code == 0
    assert "Compile passed" in result.stdout
    state = json.loads((tmp_path / "pcie" / ".kb" / "compile_state.json").read_text())
    assert state["status"] == "passed"


def test_compile_fast_fails_missing_source_reference(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert run_cli("init", "pcie").exit_code == 0
    note = tmp_path / "pcie" / "notes" / "concepts" / "bar.md"
    note.write_text("[Missing](kb://source/missing_source#section=1)\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path / "pcie")

    result = run_cli("compile", "--fast")

    assert result.exit_code == 1
    assert "missing source reference" in result.stdout


def test_compile_fast_fails_broken_relative_markdown_link(
    tmp_path: Path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    assert run_cli("init", "pcie").exit_code == 0
    note = tmp_path / "pcie" / "notes" / "concepts" / "bar.md"
    note.write_text("[Broken](missing.md)\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path / "pcie")

    result = run_cli("compile", "--fast")

    assert result.exit_code == 1
    assert "broken markdown link" in result.stdout
