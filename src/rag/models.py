from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class Evidence:
    point_id: str
    score: float
    text: str
    source: str
    cite_key: Optional[str] = None
    standard_id: Optional[str] = None
    para_key: Optional[str] = None
    section_path: Optional[str] = None
    pdf_reference_path: Optional[str] = None
