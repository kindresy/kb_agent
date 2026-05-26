from __future__ import annotations

import re

KB_SOURCE_RE = re.compile(r"kb://source/([^#)\s]+)")
URI_SCHEME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")


def extract_kb_source_refs(text: str) -> list[str]:
    refs: list[str] = []
    for match in KB_SOURCE_RE.finditer(text):
        refs.append(match.group(1))
    return refs


def extract_markdown_links(text: str) -> list[str]:
    links: list[str] = []
    for raw_target in _iter_markdown_link_targets(text):
        target = _normalize_markdown_link_target(raw_target)
        if _is_relative_file_link(target):
            links.append(target)
    return links


def _iter_markdown_link_targets(text: str) -> list[str]:
    targets: list[str] = []
    index = 0
    while index < len(text):
        label_start = text.find("[", index)
        if label_start == -1:
            break

        label_end = text.find("](", label_start + 1)
        if label_end == -1:
            break

        target_start = label_end + 2
        target_end = _find_markdown_link_target_end(text, target_start)
        if target_end == -1:
            index = target_start
            continue

        targets.append(text[target_start:target_end])
        index = target_end + 1
    return targets


def _find_markdown_link_target_end(text: str, start: int) -> int:
    depth = 0
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if char == "(":
            depth += 1
            continue
        if char == ")":
            if depth == 0:
                return index
            depth -= 1
    return -1


def _normalize_markdown_link_target(raw_target: str) -> str:
    target = raw_target.strip()
    if target.startswith("<"):
        close_angle = target.find(">", 1)
        if close_angle != -1:
            target = target[1:close_angle]
    else:
        target = _strip_markdown_link_title(target)
    target = _strip_markdown_link_fragment(target)
    target = _unescape_markdown_link_target(target)
    return target


def _strip_markdown_link_title(target: str) -> str:
    escaped = False
    depth = 0
    for index, char in enumerate(target):
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if char == "(":
            depth += 1
            continue
        if char == ")" and depth > 0:
            depth -= 1
            continue
        if char.isspace() and depth == 0:
            return target[:index]
    return target


def _unescape_markdown_link_target(target: str) -> str:
    chars: list[str] = []
    escaped = False
    for char in target:
        if escaped:
            chars.append(char)
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        chars.append(char)
    if escaped:
        chars.append("\\")
    return "".join(chars)


def _strip_markdown_link_fragment(target: str) -> str:
    escaped = False
    for index, char in enumerate(target):
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if char == "#":
            return target[:index]
    return target


def _is_relative_file_link(target: str) -> bool:
    if not target:
        return False
    if target.startswith(("#", "/", "//")):
        return False
    return URI_SCHEME_RE.match(target) is None
