from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, List


@dataclass
class BenchmarkCase:
    case_id: str
    label: str
    query: str
    lang_mode: str = "IT"
    top_k: int = 5
    score_threshold: float = 0.0
    embed_max_chars: int = 6000
    temperature: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class BenchmarkRunResult:
    case_id: str
    label: str
    query: str
    answer: str
    lang: str
    collection: str
    citations: List[Dict[str, Any]]
    evidences: List[Dict[str, Any]]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
