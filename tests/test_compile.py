from kb_agent.markdown import extract_kb_source_refs, extract_markdown_links


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
