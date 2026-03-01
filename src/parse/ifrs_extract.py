from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from src.parse.eurlex_html import TextBlock


# Standard boundaries
STD_IAS = re.compile(r"^INTERNATIONAL\s+ACCOUNTING\s+STANDARD\s+(\d+)\b", re.I)
STD_IFRS = re.compile(r"^INTERNATIONAL\s+FINANCIAL\s+REPORTING\s+STANDARD\s+(\d+)\b", re.I)
STD_IFRIC = re.compile(r"^IFRIC\s+(\d+)\b", re.I)
STD_SIC = re.compile(r"^SIC\s+(\d+)\b", re.I)
STD_FALLBACK = re.compile(r"\b(IAS|IFRS|IFRIC|SIC)\s*(\d+)\b", re.I)

# Paragraph starts
PARA_INT = re.compile(r"^(\d{1,3})\s+(.+)$")
PARA_DOTTED = re.compile(r"^(\d+(?:\.\d+){1,4})\s+(.+)$")
PARA_APP_B = re.compile(r"^(B\d+)\s+(.+)$")
PARA_APP_IE = re.compile(r"^(IE\d+)\s+(.+)$")
PARA_APP_BC = re.compile(r"^(BC\d+)\s+(.+)$")

HEADING_EN = re.compile(r"^(OBJECTIVE|SCOPE|DEFINITIONS|RECOGNITION|MEASUREMENT|DISCLOSURE|EFFECTIVE\s+DATE|TRANSITION)\b", re.I)


@dataclass
class Paragraph:
    key: str
    text: str
    section_path: Optional[str] = None


def detect_standard_id(text: str) -> Optional[str]:
    m = STD_IAS.match(text)
    if m: return f"IAS {m.group(1)}"
    m = STD_IFRS.match(text)
    if m: return f"IFRS {m.group(1)}"
    m = STD_IFRIC.match(text)
    if m: return f"IFRIC {m.group(1)}"
    m = STD_SIC.match(text)
    if m: return f"SIC {m.group(1)}"
    return None


def paragraph_start(text: str) -> Optional[Tuple[str, str]]:
    for rx in (PARA_DOTTED, PARA_INT, PARA_APP_B, PARA_APP_IE, PARA_APP_BC):
        m = rx.match(text)
        if m:
            return m.group(1), m.group(2)
    return None


def extract_standard_paragraphs(blocks: List[TextBlock]) -> Dict[str, List[Paragraph]]:
    """
    Returns: {standard_id: [Paragraph, ...]}
    Strategy:
    - scan blocks; when standard boundary found, set current standard
    - parse paragraph starts; accumulate until next paragraph start or next standard
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
                Paragraph(key=cur_para_key, text=" ".join(cur_para_lines).strip(), section_path=cur_para_section)
            )
        cur_para_key = None
        cur_para_lines = []
        cur_para_section = None

    for b in blocks:
        std = detect_standard_id(b.text)
        if std:
            flush_para()
            cur_std = std
            cur_section = [std]
            continue

        # track headings as section path hints
        if b.kind == "heading" and HEADING_EN.match(b.text):
            # keep within current standard context if any
            if cur_std:
                # normalize capitalization
                cur_section = [cur_std, b.text.title()]
            continue

        if not cur_std:
            continue

        ps = paragraph_start(b.text)
        if ps:
            flush_para()
            cur_para_key = ps[0]
            cur_para_lines = [ps[1]]
            cur_para_section = " > ".join(cur_section) if cur_section else cur_std
        else:
            # continuation
            if cur_para_key:
                cur_para_lines.append(b.text)

    flush_para()
    return out
