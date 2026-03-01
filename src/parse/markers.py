from __future__ import annotations

import re

_RX_MARKERS = re.compile(r"[►▼]\s*[A-Z]\d*|[◄►▼]")

def strip_celex_markers(s: str) -> str:
    """
    Remove EUR-Lex consolidation/rectification markers from text.
    Keep the semantic content; normalize whitespace lightly.
    """
    if not s:
        return ""
    s = s.replace("\u00a0", " ")
    s = _RX_MARKERS.sub("", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()
