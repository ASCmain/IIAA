from __future__ import annotations

import re
from typing import List

from .models import Evidence


def citation_label(e: Evidence) -> str:
    if e.cite_key:
        return str(e.cite_key)

    src = str(e.source or "")
    m = re.search(r"CELEX:([0-9A-Z]+)", src, flags=re.IGNORECASE)
    if m:
        return f"CELEX:{m.group(1).upper()}"

    if "2025/1266" in src or "32025R1266" in src:
        return "CELEX:32025R1266"

    return "SOURCE"


def format_evidence(e: Evidence, i: int) -> str:
    label = citation_label(e)
    loc = f"{e.standard_id or ''} {e.para_key or ''}".strip()

    head = f"{label}".strip()
    if loc and e.cite_key and loc.replace(" ", "") != e.cite_key.replace(" ", ""):
        head = f"{head} ({loc})"
    elif loc and not e.cite_key:
        head = f"{head} ({loc})"

    return (
        f"{head}\n"
        f"Source: {e.source}\n"
        f"Section: {e.section_path or ''}\n"
        f"Text: {e.text}\n"
    ).strip()


def build_grounded_prompt(
    query: str,
    core_evidences: List[Evidence],
    context_evidences: List[Evidence],
    answer_language: str,
    focus_summary: str = "",
) -> str:
    lang_note = "Italiano" if answer_language.upper() == "IT" else "English"
    core_cites = "\n\n".join(format_evidence(e, i + 1) for i, e in enumerate(core_evidences))
    context_cites = "\n\n".join(format_evidence(e, i + 1) for i, e in enumerate(context_evidences))

    focus_block = ""
    if str(focus_summary or "").strip():
        focus_block = (
            f"\nDetected domain focus: {focus_summary}\n"
            "Use this focus conservatively: privilege evidence aligned with the detected standards/topics "
            "and avoid grounding the answer on lateral standards unless strictly necessary.\n"
        )

    return f"""
You are an IAS/IFRS assistant. Answer in {lang_note}.{focus_block}

Rules:
- Use ONLY the provided evidence texts. If evidence is insufficient, say what is missing and stop.
- Use inline citations in square brackets, but ONLY with labels that appear in the evidence bundle.
- NEVER use numeric citations like [1], [2], [3].
- If an item has no paragraph cite_key, use the fallback label exactly as shown in the evidence bundle, for example [CELEX:32025R1266].
- Do NOT invent citations.
- If you use multiple evidences, cite each relevant statement with the appropriate label.
- Treat CORE evidences as primary authority.
- If CORE evidences aligned with the primary standard/topic are available, do NOT base the answer on CONTEXT evidences.
- Use CONTEXT evidences only to clarify, distinguish concepts, or add limited cross-reference without overriding CORE evidences.

User question:
{query}

CORE evidences:
{core_cites}

CONTEXT evidences:
{context_cites}

Now produce:
1) A concise answer (2–10 paragraphs), in {lang_note}.
2) A short bullet list "Citations used:" containing ONLY the labels you actually referenced.
""".strip()
