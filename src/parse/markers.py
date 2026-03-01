from __future__ import annotations

import re
from typing import Optional, Tuple

# Matches EUR-Lex consolidation markers like ►B, ▼B, ►M1, ►C1, ◄ etc.
_RX_MARKERS = re.compile(r"([►▼]\s*[A-Z]\d*|[◄►▼])")

def strip_celex_markers(s: str) -> Tuple[str, Optional[str]]:
    """
    Remove EUR-Lex consolidation/rectification markers from text.

    Returns:
      (clean_text, last_marker_found_or_None)

    Notes:
    - We keep the *last* marker (if any) so callers can optionally store it
      as amendment_marker in TextBlock metadata.
    - Normalizes whitespace.
    """
    if not s:
        return "", None

    s = s.replace("\u00a0", " ")

    markers = _RX_MARKERS.findall(s)
    last_marker = None
    if markers:
        # normalize marker formatting (remove internal spaces)
        last_marker = markers[-1].replace(" ", "")

    s2 = _RX_MARKERS.sub("", s)
    s2 = re.sub(r"\s+", " ", s2).strip()
    return s2, last_marker
