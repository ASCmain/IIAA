from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from src.parse.eurlex_html import TextBlock


# --- EUR-Lex markers (appear in PDFs and sometimes in HTML conversions) ---
MARKERS = re.compile(r"[►▼]\s*[A-Z]\d*|[◄►▼]")


def strip_markers(s: str) -> str:
    s = (s or "").replace("\u00a0", " ")
    s = MARKERS.sub("", s)
    return re.sub(r"\s+", " ", s).strip()


# --- Standard boundaries (STRICT) ---
# Long-form EN
STD_EN_IAS = re.compile(r"^INTERNATIONAL\s+ACCOUNTING\s+STANDARD\s+(\d+)\b", re.I)
STD_EN_IFRS = re.compile(r"^INTERNATIONAL\s+FINANCIAL\s+REPORTING\s+STANDARD\s+(\d+)\b", re.I)

# Long-form IT (IAS) – in EUR-Lex IT you can see both forms:
#   "PRINCIPIO CONTABILE INTERNAZIONALE 36"
#   "PRINCIPIO CONTABILE INTERNAZIONALE N. 36"
STD_IT_IAS = re.compile(
    r"^(PRINCIPIO\s+CONTABILE\s+INTERNAZIONALE|PRINCIPI?\s+CONTABILI?\s+INTERNAZIONALI?)\s+(?:N\.\s*)?(\d+)\b",
    re.I,
)

# Short-form line (TOC and many headers): MUST be alone (no trailing prose)
# Accept both "SIC 32" and "SIC-32" (same for IFRIC).
STD_SHORT_ONLY = re.compile(r"^(IAS|IFRS|IFRIC|SIC)[\s\-]+(\d+)\s*$", re.I)

# IFRIC and SIC short-form headings
STD_IFRIC = re.compile(r"^IFRIC[\s\-]+(\d+)\s*$", re.I)
STD_SIC = re.compile(r"^SIC[\s\-]+(\d+)\s*$", re.I)

# Long-form IT for interpretations (common in EUR-Lex IT): "INTERPRETAZIONE IFRIC 2", "INTERPRETAZIONE SIC-32"
STD_IT_IFRIC = re.compile(r"^INTERPRETAZIONE\s+IFRIC[\s\-]+(\d+)\s*$", re.I)
STD_IT_SIC = re.compile(r"^INTERPRETAZIONE\s+SIC[\s\-]+(\d+)\s*$", re.I)


def detect_standard_boundary(text: str) -> Optional[str]:
    """
    Returns a standard_id only for *boundary* lines.
    Important: avoids false positives like 'IFRS 9 permits ...' in body text.
    """
    t = strip_markers(text)

    m = STD_EN_IAS.match(t)
    if m:
        return f"IAS {m.group(1)}"

    m = STD_EN_IFRS.match(t)
    if m:
        return f"IFRS {m.group(1)}"

    m = STD_IT_IAS.match(t)
    if m:
        return f"IAS {m.group(2)}"

    m = STD_IFRIC.match(t)
    if m:
        return f"IFRIC {m.group(1)}"

    m = STD_SIC.match(t)
    if m:
        return f"SIC {m.group(1)}"

    # IT interpretations long-form
    m = STD_IT_IFRIC.match(t)
    if m:
        return f"IFRIC {m.group(1)}"

    m = STD_IT_SIC.match(t)
    if m:
        return f"SIC {m.group(1)}"

    # TOC-style short code must be the entire line
    m = STD_SHORT_ONLY.match(t)
    if m:
        return f"{m.group(1).upper()} {m.group(2)}"

    return None


# --- Paragraph starts ---
PARA_INT = re.compile(r"^(\d{1,3})\s+(.+)$")
PARA_DOTTED = re.compile(r"^(\d+(?:\.\d+){1,4})\s+(.+)$")
PARA_APP_B = re.compile(r"^(B\d+)\s+(.+)$")
PARA_APP_IE = re.compile(r"^(IE\d+)\s+(.+)$")
PARA_APP_BC = re.compile(r"^(BC\d+)\s+(.+)$")


def paragraph_start(text: str) -> Optional[Tuple[str, str]]:
    t = strip_markers(text)
    for rx in (PARA_DOTTED, PARA_INT, PARA_APP_B, PARA_APP_IE, PARA_APP_BC):
        m = rx.match(t)
        if m:
            return m.group(1), m.group(2)
    return None


# --- Section headings (EN + IT) ---
HEADING_EN = re.compile(
    r"^(OBJECTIVE|SCOPE|DEFINITIONS|RECOGNITION|MEASUREMENT|DISCLOSURE|PRESENTATION|EFFECTIVE\s+DATE|TRANSITION|WITHDRAWAL)\b",
    re.I,
)

# Add interpretation-typical sections for IT too (RIFERIMENTI, PREMESSA, PROBLEMA, INTERPRETAZIONE)
HEADING_IT = re.compile(
    r"^(OBIETTIVO|AMBITO\s+DI\s+APPLICAZIONE|DEFINIZIONI|RILEVAZIONE|VALUTAZIONE|INFORMATIVA|PRESENTAZIONE|"
    r"DATA\s+DI\s+ENTRATA\s+IN\s+VIGORE|DISPOSIZIONI\s+TRANSITORIE|RITIRO|ELIMINAZIONE|"
    r"RIFERIMENTI|PREMESSA|PROBLEMA|INTERPRETAZIONE)\b",
    re.I,
)

# Also accept "Appendix A/B", "Appendice A/B", "Basis for Conclusions", etc.
HEADING_APPX = re.compile(
    r"^(APPENDIX|APPENDICE)\s+[A-Z]\b|^BASIS\s+FOR\s+CONCLUSIONS\b|^BASIS\s+OF\s+CONCLUSIONS\b|^GUIDANCE\s+ON\b",
    re.I,
)


@dataclass
class Paragraph:
    key: str
    text: str
    section_path: Optional[str] = None


def _normalize_heading(s: str) -> str:
    t = strip_markers(s)
    return t[:120].strip()


def extract_standard_paragraphs(blocks: List[TextBlock]) -> Dict[str, List[Paragraph]]:
    """
    Returns: {standard_id: [Paragraph, ...]}

    Strategy (robust, conservative):
    - Identify *standard boundaries* only via strict patterns:
        - "INTERNATIONAL ... STANDARD N" (EN)
        - "PRINCIPIO CONTABILE INTERNAZIONALE (N.) N" (IT)
        - Interpretation headers "INTERPRETAZIONE SIC-32", "INTERPRETAZIONE IFRIC 2" (IT)
        - TOC-style lines exactly "IFRS 9", "IAS 36", "SIC-32", etc.
      This avoids 'IFRS 9 permits ...' false positives.
    - Within a standard, capture section headings (EN/IT) to build section_path hints.
    - Paragraphs are extracted by detecting numeric/dotted/appendix keys at line start.
    """
    cur_std: Optional[str] = None
    cur_section: List[str] = []
    out: Dict[str, List[Paragraph]] = {}

    cur_para_key: Optional[str] = None
    cur_para_lines: List[str] = []
    cur_para_section: Optional[str] = None

    def flush_para():
        nonlocal cur_para_key, cur_para_lines, cur_para_section
        if cur_std and cur_para_key and cur_para_lines:
            out.setdefault(cur_std, []).append(
                Paragraph(
                    key=cur_para_key,
                    text=" ".join(cur_para_lines).strip(),
                    section_path=cur_para_section,
                )
            )
        cur_para_key = None
        cur_para_lines = []
        cur_para_section = None

    for b in blocks:
        raw = b.text or ""
        t = strip_markers(raw)
        if not t:
            continue

        std = detect_standard_boundary(t)
        if std:
            flush_para()
            cur_std = std
            cur_section = [std]
            continue

        if not cur_std:
            continue

        # headings (section_path hints)
        if b.kind == "heading" or HEADING_EN.match(t) or HEADING_IT.match(t) or HEADING_APPX.match(t):
            if HEADING_EN.match(t) or HEADING_IT.match(t) or HEADING_APPX.match(t):
                cur_section = [cur_std, _normalize_heading(t)]
            # do not continue: some conversions use headings that may also carry paragraph-like patterns

        ps = paragraph_start(t)
        if ps:
            flush_para()
            cur_para_key = ps[0]
            cur_para_lines = [ps[1]]
            cur_para_section = " > ".join(cur_section) if cur_section else cur_std
        else:
            if cur_para_key:
                cur_para_lines.append(t)

    flush_para()
    return out
