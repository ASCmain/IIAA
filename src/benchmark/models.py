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
    query_plan: Dict[str, Any]
    retrieval_raw_count: int
    retrieval_above_initial_threshold_count: int
    analysis_pool_count: int
    analysis_pool_target: int
    min_candidate_floor: int
    threshold_initial: float | None
    threshold_effective: float | None
    coverage_warning_low_candidate_count: bool
    classifier_mode: str
    classifier_model: str
    classifier_items: List[Dict[str, Any]]
    classifier_items_count: int
    classifier_raw_response: str
    telemetry_timing_ms: Dict[str, Any]
    citations: List[Dict[str, Any]]
    evidences: List[Dict[str, Any]]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
