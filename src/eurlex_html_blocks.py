# src/eurlex_html_blocks.py
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from bs4 import BeautifulSoup, Tag

from src.text_normalize import normalize_text


@dataclass(frozen=True)
class HtmlBlock:
    heading_path: list[str]
    kind: str  # heading | paragraph | li | td | th
    text: str


# EUR-Lex "oracle" HTML frequently encodes headings as <p class="title-...">
_RX_TITLE_GR_LEVEL = re.compile(r"\btitle-gr-seq-level-(\d)\b", re.IGNORECASE)
_RX_TITLE_DOC = re.compile(r"\btitle-doc-(first|last|oj-reference)\b", re.IGNORECASE)
_RX_TITLE_ARTICLE = re.compile(r"\btitle-article-norm\b", re.IGNORECASE)
_RX_TITLE_ANNEX = re.compile(r"\btitle-annex-\d+\b", re.IGNORECASE)
_RX_TITLE_GENERIC = re.compile(r"\btitle-[a-z0-9_-]+\b", re.IGNORECASE)


def _get_class_string(el: Tag) -> str:
    cls_list = el.get("class", [])
    return " ".join(cls_list) if cls_list else ""


def _eurlex_heading_level(el: Tag, text: str) -> int | None:
    """
    Return a heading level (1..6) if the element looks like a EUR-Lex heading,
    otherwise None.

    We prioritize explicit EUR-Lex class conventions.
    """
    cls = _get_class_string(el)
    if not cls:
        return None

    m = _RX_TITLE_GR_LEVEL.search(cls)
    if m:
        # title-gr-seq-level-1..5 => map directly to 1..5
        lvl = int(m.group(1))
        return max(1, min(6, lvl))

    if _RX_TITLE_DOC.search(cls):
        return 1

    if _RX_TITLE_ANNEX.search(cls):
        return 2

    if _RX_TITLE_ARTICLE.search(cls):
        return 2

    # Generic title-* headings (conservative): treat as level 3
    if _RX_TITLE_GENERIC.search(cls):
        return 3

    return None


def _is_heading(el: Tag, text: str) -> tuple[bool, int]:
    name = el.name.lower()

    # Standard HTML headings
    if name in {"h1", "h2", "h3", "h4", "h5", "h6"}:
        return True, int(name[1])

    # ARIA headings
    role = (el.get("role") or "").lower()
    aria_level = el.get("aria-level")
    if role == "heading":
        if aria_level and str(aria_level).isdigit():
            return True, int(aria_level)
        return True, 3

    # EUR-Lex class-driven headings
    lvl = _eurlex_heading_level(el, text)
    if lvl is not None:
        # guard against very long "headings" (likely false positives)
        if len(text) > 240:
            return False, 0
        return True, lvl

    return False, 0


def _iter_content_nodes(root: Tag) -> Iterator[Tag]:
    """
    Yield nodes in document order. Include EUR-Lex relevant containers:
    headings in <p class="title-..."> and normal content in p/li/td/th.
    """
    for el in root.descendants:
        if not isinstance(el, Tag):
            continue
        name = el.name.lower()
        if name in {"h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "td", "th"}:
            yield el


def extract_blocks_from_html(html: str) -> list[HtmlBlock]:
    soup = BeautifulSoup(html, "lxml")
    body = soup.body or soup

    heading_stack: list[tuple[int, str]] = []  # (level, text)
    blocks: list[HtmlBlock] = []

    for el in _iter_content_nodes(body):
        name = el.name.lower()
        txt = normalize_text(el.get_text(" ", strip=True))
        if not txt:
            continue

        is_heading, level = _is_heading(el, txt)
        if is_heading:
            while heading_stack and heading_stack[-1][0] >= level:
                heading_stack.pop()
            heading_stack.append((level, txt))

            heading_path = [t for _, t in heading_stack]
            blocks.append(HtmlBlock(heading_path=heading_path, kind="heading", text=txt))
            continue

        heading_path = [t for _, t in heading_stack]

        kind = "paragraph"
        if name == "li":
            kind = "li"
        elif name == "td":
            kind = "td"
        elif name == "th":
            kind = "th"

        blocks.append(HtmlBlock(heading_path=heading_path, kind=kind, text=txt))

    return blocks


def extract_blocks_from_file(path: Path) -> list[HtmlBlock]:
    html = path.read_text(encoding="utf-8", errors="replace")
    return extract_blocks_from_html(html)
