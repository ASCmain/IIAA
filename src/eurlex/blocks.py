from __future__ import annotations

import re
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from bs4 import BeautifulSoup, Tag
from bs4 import XMLParsedAsHTMLWarning

from src.text_normalize import normalize_text


@dataclass(frozen=True)
class HtmlBlock:
    heading_path: list[str]
    kind: str  # heading | paragraph | li | td | th
    text: str


_RX_TITLE_GR_LEVEL = re.compile(r"\btitle-gr-seq-level-(\d)\b", re.IGNORECASE)
_RX_TITLE_DOC = re.compile(r"\btitle-doc-(first|last|oj-reference)\b", re.IGNORECASE)
_RX_TITLE_ARTICLE = re.compile(r"\btitle-article-norm\b", re.IGNORECASE)
_RX_TITLE_ANNEX = re.compile(r"\btitle-annex-\d+\b", re.IGNORECASE)
_RX_TITLE_GENERIC = re.compile(r"\btitle-[a-z0-9_-]+\b", re.IGNORECASE)


def _get_class_string(el: Tag) -> str:
    cls_list = el.get("class", [])
    return " ".join(cls_list) if cls_list else ""


def _eurlex_heading_level(el: Tag, text: str) -> int | None:
    cls = _get_class_string(el)
    if not cls:
        return None

    m = _RX_TITLE_GR_LEVEL.search(cls)
    if m:
        lvl = int(m.group(1))
        return max(1, min(6, lvl))

    if _RX_TITLE_DOC.search(cls):
        return 1

    if _RX_TITLE_ANNEX.search(cls):
        return 2

    if _RX_TITLE_ARTICLE.search(cls):
        return 2

    if _RX_TITLE_GENERIC.search(cls):
        return 3

    return None


def _is_heading(el: Tag, text: str) -> tuple[bool, int]:
    name = el.name.lower()

    if name in {"h1", "h2", "h3", "h4", "h5", "h6"}:
        return True, int(name[1])

    role = (el.get("role") or "").lower()
    aria_level = el.get("aria-level")
    if role == "heading":
        if aria_level and str(aria_level).isdigit():
            return True, int(aria_level)
        return True, 2

    eurlex_lvl = _eurlex_heading_level(el, text)
    if eurlex_lvl is not None:
        return True, eurlex_lvl

    txt = text.strip()
    if name == "p" and txt:
        upper_txt = txt.upper()
        if upper_txt.startswith("ALLEGATO") or upper_txt.startswith("ANNEX"):
            return True, 2
        if upper_txt.startswith("ARTICOLO ") or upper_txt.startswith("ARTICLE "):
            return True, 2

    return False, 0


def _iter_relevant_elements(soup: BeautifulSoup) -> Iterator[Tag]:
    for el in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "td", "th"]):
        yield el


def extract_blocks(html: str) -> list[HtmlBlock]:
    warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)
    soup = BeautifulSoup(html, "lxml")

    blocks: list[HtmlBlock] = []
    heading_stack: list[str] = []

    for el in _iter_relevant_elements(soup):
        txt = normalize_text(el.get_text(" ", strip=True))
        if not txt:
            continue

        is_heading, level = _is_heading(el, txt)
        if is_heading:
            while len(heading_stack) >= level:
                heading_stack.pop()
            heading_stack.append(txt)
            blocks.append(HtmlBlock(heading_path=heading_stack.copy(), kind="heading", text=txt))
            continue

        kind = el.name.lower()
        blocks.append(HtmlBlock(heading_path=heading_stack.copy(), kind=kind, text=txt))

    return blocks


def extract_blocks_from_file(path: Path) -> list[HtmlBlock]:
    html = Path(path).read_text(encoding="utf-8", errors="replace")
    return extract_blocks(html)


__all__ = [
    "HtmlBlock",
    "extract_blocks",
    "extract_blocks_from_file",
]
