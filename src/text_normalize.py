# src/text_normalize.py
from __future__ import annotations

import re
import unicodedata

# Common invisible/problematic chars seen in extracted texts
_SOFT_HYPHEN = "\u00ad"
_ZERO_WIDTH = re.compile(r"[\u200b\u200c\u200d\ufeff]")

# Sequences like: "I n t e r n a t i o n a l" (letters spaced out)
_SPACED_LETTERS = re.compile(
    r"\b(?:[A-Za-zÀ-ÖØ-öø-ÿ]\s){5,}[A-Za-zÀ-ÖØ-öø-ÿ]\b"
)

_VOWELS = set("aeiouàèìòùAEIOUÀÈÌÒÙ")


def _collapse_whitespace(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def _join_spaced_letters_if_probable(s: str) -> str:
    """
    Conservative heuristic:
    - Only joins sequences of single letters separated by single spaces
      with length >= 6 letters (pattern uses >= 6 by requiring 5 repeats + last).
    - Joins only if merged token contains at least 2 vowels OR length is large (>= 10).
    This avoids accidental joins for short acronyms or enumerations.
    """

    def repl(m: re.Match) -> str:
        token = m.group(0)
        merged = token.replace(" ", "")
        vcount = sum(1 for ch in merged if ch in _VOWELS)
        if vcount >= 2 or len(merged) >= 10:
            return merged
        return token  # keep original if not confident

    return _SPACED_LETTERS.sub(repl, s)


def normalize_text(s: str) -> str:
    """
    Conservative normalization suitable for legal/accounting text:
    - Unicode NFKC
    - Remove soft-hyphen and zero-width chars
    - Collapse whitespace
    - Join spaced letters only when highly probable
    """
    if s is None:
        return ""
    s = unicodedata.normalize("NFKC", s)
    s = s.replace(_SOFT_HYPHEN, "")
    s = _ZERO_WIDTH.sub("", s)
    s = _collapse_whitespace(s)
    s = _join_spaced_letters_if_probable(s)
    s = _collapse_whitespace(s)
    return s