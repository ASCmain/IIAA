from __future__ import annotations

from pathlib import Path
from typing import Any

from pypdf import PdfReader

from .textnorm import normalize_text


def read_pdf_pages(path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    reader = PdfReader(str(path))
    pages: list[dict[str, Any]] = []
    empty_pages = 0

    for i, page in enumerate(reader.pages, start=1):
        raw = page.extract_text() or ""
        txt = normalize_text(raw)
        if not txt:
            empty_pages += 1
        pages.append({"page": i, "text": txt})

    stats = {
        "pages_total": len(reader.pages),
        "pages_empty": empty_pages,
    }
    return pages, stats
