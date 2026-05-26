import json
from pathlib import Path

from kb_agent.compile import compile_fast
from kb_agent.markdown import extract_kb_source_refs, extract_markdown_links
from kb_agent.sources import SourceRecord, write_source_index
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


def test_extract_markdown_links_allows_unescaped_spaces_without_quoted_title():
    text = """
[Doc](PCI Express Base-assets/part_0001/images/packet.jpg)
"""

    links = extract_markdown_links(text)

    assert links == ["PCI Express Base-assets/part_0001/images/packet.jpg"]


def test_extract_markdown_links_ignores_printf_format_strings():
    text = r'''
printf(KERN_INFOPREFIX"%s[%s](%04x:%02x)\n", name, bid, segment, bus);
'''

    links = extract_markdown_links(text)

    assert links == []


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


def test_compile_fast_fails_indexed_source_path_outside_kb(
    tmp_path: Path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    assert run_cli("init", "pcie").exit_code == 0
    root = tmp_path / "pcie"
    external = tmp_path / "external.md"
    external.write_text("# External\n", encoding="utf-8")
    write_source_index(
        root,
        [
            SourceRecord(
                source_id="external",
                type="manual",
                title="External",
                path="../external.md",
                original_path=str(external),
                hash="sha256:test",
            )
        ],
    )
    monkeypatch.chdir(root)

    result = run_cli("compile", "--fast")

    assert result.exit_code == 1
    assert "source path escapes knowledge base" in result.stdout


def test_compile_fast_fails_absolute_indexed_source_path_outside_kb(
    tmp_path: Path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    assert run_cli("init", "pcie").exit_code == 0
    root = tmp_path / "pcie"
    external = tmp_path / "external.md"
    external.write_text("# External\n", encoding="utf-8")
    write_source_index(
        root,
        [
            SourceRecord(
                source_id="external",
                type="manual",
                title="External",
                path=str(external),
                original_path=str(external),
                hash="sha256:test",
            )
        ],
    )
    monkeypatch.chdir(root)

    result = run_cli("compile", "--fast")

    assert result.exit_code == 1
    assert "source path must be relative to knowledge base" in result.stdout


def test_compile_fast_fails_absolute_indexed_source_path_inside_kb(
    tmp_path: Path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    assert run_cli("init", "pcie").exit_code == 0
    root = tmp_path / "pcie"
    source = root / "sources" / "manuals" / "inside.md"
    source.write_text("# Inside\n", encoding="utf-8")
    write_source_index(
        root,
        [
            SourceRecord(
                source_id="inside",
                type="manual",
                title="Inside",
                path=str(source),
                original_path=str(source),
                hash="sha256:test",
            )
        ],
    )
    monkeypatch.chdir(root)

    result = run_cli("compile", "--fast")

    assert result.exit_code == 1
    assert "source path must be relative to knowledge base" in result.stdout


def test_compile_fast_fails_markdown_link_outside_kb_even_if_target_exists(
    tmp_path: Path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    assert run_cli("init", "pcie").exit_code == 0
    root = tmp_path / "pcie"
    external = tmp_path / "external.md"
    external.write_text("# External\n", encoding="utf-8")
    note = root / "notes" / "concepts" / "bar.md"
    note.write_text("[External](../../../external.md)\n", encoding="utf-8")
    monkeypatch.chdir(root)

    result = run_cli("compile", "--fast")

    assert result.exit_code == 1
    assert "markdown link escapes knowledge base" in result.stdout


def test_compile_fast_fails_missing_required_file(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert run_cli("init", "pcie").exit_code == 0
    root = tmp_path / "pcie"
    (root / "README.md").unlink()
    monkeypatch.chdir(root)

    result = run_cli("compile", "--fast")

    assert result.exit_code == 1
    assert "missing_required_file" in result.stdout
    assert "README.md" in result.stdout


def test_compile_fast_fails_missing_canonical_directory(
    tmp_path: Path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    assert run_cli("init", "pcie").exit_code == 0
    root = tmp_path / "pcie"
    (root / "notes" / "concepts").rmdir()
    monkeypatch.chdir(root)

    result = run_cli("compile", "--fast")

    assert result.exit_code == 1
    assert "missing_canonical_dir" in result.stdout
    assert "notes/concepts" in result.stdout


def test_compile_fast_fails_indexed_source_file_drift(
    tmp_path: Path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    assert run_cli("init", "pcie").exit_code == 0
    root = tmp_path / "pcie"
    write_source_index(
        root,
        [
            SourceRecord(
                source_id="missing",
                type="manual",
                title="Missing",
                path="sources/manuals/missing.md",
                original_path="/tmp/missing.md",
                hash="sha256:test",
            )
        ],
    )
    monkeypatch.chdir(root)

    result = run_cli("compile", "--fast")

    assert result.exit_code == 1
    assert "indexed source file does not exist" in result.stdout


def test_compile_fast_writes_failed_state_for_missing_required_file(
    tmp_path: Path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    assert run_cli("init", "pcie").exit_code == 0
    root = tmp_path / "pcie"
    (root / "README.md").unlink()

    result = compile_fast(root)

    assert not result.passed
    state = json.loads((root / ".kb" / "compile_state.json").read_text())
    assert state["status"] == "failed"
    assert state["findings"][0]["code"] == "missing_required_file"


def test_compile_fast_fails_missing_package_asset(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert run_cli("init", "pcie").exit_code == 0
    package = tmp_path / "package"
    assets = package / "pcie_book.assets"
    assets.mkdir(parents=True)
    (package / "pcie_book.md").write_text(
        "# PCIe Book\n\n![LTSSM](pcie_book.assets/ltssm.png)\n",
        encoding="utf-8",
    )
    (assets / "ltssm.png").write_bytes(b"png bytes")
    root = tmp_path / "pcie"
    monkeypatch.chdir(root)
    assert run_cli("ingest", str(package)).exit_code == 0
    (root / "sources" / "manuals" / "pcie_book" / "pcie_book.assets" / "ltssm.png").unlink()

    result = run_cli("compile", "--fast")

    assert result.exit_code == 1
    assert "missing package asset" in result.stdout


def test_compile_fast_fails_package_markdown_link_outside_package(
    tmp_path: Path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    assert run_cli("init", "pcie").exit_code == 0
    package = tmp_path / "package"
    assets = package / "pcie_book.assets"
    assets.mkdir(parents=True)
    (package / "pcie_book.md").write_text(
        "# PCIe Book\n\n[Escape](../outside.md)\n",
        encoding="utf-8",
    )
    (assets / "ltssm.png").write_bytes(b"png bytes")
    root = tmp_path / "pcie"
    monkeypatch.chdir(root)
    assert run_cli("ingest", str(package)).exit_code == 0

    result = run_cli("compile", "--fast")

    assert result.exit_code == 1
    assert "package markdown link escapes package" in result.stdout


def test_compile_fast_passes_valid_markdown_package(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert run_cli("init", "pcie").exit_code == 0
    package = tmp_path / "package"
    assets = package / "pcie_book.assets"
    assets.mkdir(parents=True)
    (package / "pcie_book.md").write_text(
        "# PCIe Book\n\n![LTSSM](pcie_book.assets/ltssm.png)\n",
        encoding="utf-8",
    )
    (assets / "ltssm.png").write_bytes(b"png bytes")
    root = tmp_path / "pcie"
    monkeypatch.chdir(root)
    assert run_cli("ingest", str(package)).exit_code == 0

    result = run_cli("compile", "--fast")

    assert result.exit_code == 0
    assert "Compile passed" in result.stdout
