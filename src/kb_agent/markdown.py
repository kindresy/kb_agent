from __future__ import annotations

import re

MARKDOWN_LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
KB_SOURCE_RE = re.compile(r"kb://source/([^#)\s]+)")
URI_SCHEME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")


def extract_kb_source_refs(text: str) -> list[str]:
    refs: list[str] = []
    for match in KB_SOURCE_RE.finditer(text):
        refs.append(match.group(1))
    return refs


def extract_markdown_links(text: str) -> list[str]:
    links: list[str] = []
    for match in MARKDOWN_LINK_RE.finditer(text):
        target = match.group(1).strip().split(maxsplit=1)[0]
        if not target:
            continue
        if target.startswith(("#", "/", "//")):
            continue
        if URI_SCHEME_RE.match(target):
            continue
        links.append(target)
    return links
