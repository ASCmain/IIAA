from __future__ import annotations

import re

_IT_HINTS = {
    "il","lo","la","i","gli","le","un","una","uno","del","della","dello","dei","delle",
    "che","per","con","come","anche","quale","quali","quando","dove","perché","poiché",
    "entità","bilancio","valore","riduzione","perdita","informativa","paragrafo","appendice"
}
_EN_HINTS = {
    "the","a","an","and","or","of","to","in","for","with","as","which","when","where",
    "entity","financial","statements","recoverable","impairment","paragraph","appendix"
}


def detect_language_80_20(text: str) -> str:
    t = re.sub(r"[^a-zA-ZàèéìòùÀÈÉÌÒÙ\s]", " ", (text or "")).lower()
    tokens = [w for w in t.split() if len(w) > 1][:200]
    if not tokens:
        return "IT"
    it = sum(1 for w in tokens if w in _IT_HINTS)
    en = sum(1 for w in tokens if w in _EN_HINTS)
    if en >= max(2, int((it + en) * 0.55)):
        return "EN"
    return "IT"
