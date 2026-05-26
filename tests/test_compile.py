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
[External](https://example.com)
[Source](kb://source/pcie_base_spec_5_0#section=7.5.1)
"""

    links = extract_markdown_links(text)

    assert links == ["../mechanisms/bar.md"]
