from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional

from bs4 import BeautifulSoup

from src.parse.markers import strip_celex_markers


@dataclass(frozen=True)
class TextBlock:
    kind: str  # heading|p|li|table
    text: str
    amendment_marker: Optional[str] = None


def _main_container(soup: BeautifulSoup):
    # EUR-Lex commonly uses these containers; we try in order then fallback to body
    for sel in ("#TexteOnly", "#TexteOnlyContent", "#TexteOnlyContent .texte", "article", "main"):
        el = soup.select_one(sel)
        if el:
            return el
    return soup.body or soup


def _clean_text(t: str) -> str:
    t = " ".join(t.split())
    return t.strip()


def html_to_blocks(raw_html: str) -> List[TextBlock]:
    soup = BeautifulSoup(raw_html, "lxml")
    root = _main_container(soup)

    blocks: List[TextBlock] = []

    # Extract in DOM order: headings + paragraphs + list items.
    # Keep it simple/deterministic; skip nav/footer by focusing on main container.
    for el in root.find_all(["h1", "h2", "h3", "h4", "p", "li"], recursive=True):
        txt = _clean_text(el.get_text(" ", strip=True))
        if not txt:
            continue

        # Drop trivial UI boilerplate fragments
        lower = txt.lower()
        if lower in ("back to top", "top"):
            continue

        kind = "heading" if el.name in ("h1", "h2", "h3", "h4") else ("li" if el.name == "li" else "p")

        # Strip CELEX markers but keep last marker in block
        txt2, marker = strip_celex_markers(txt)
        if not txt2:
            continue

        blocks.append(TextBlock(kind=kind, text=txt2, amendment_marker=marker))

    return blocks
