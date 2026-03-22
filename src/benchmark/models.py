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
    status: str
    error: str
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
    max_core: int
    max_context: int
    policy_trace: Dict[str, Any]
    core_cite_keys: List[str]
    context_cite_keys: List[str]
    semantic_route: Dict[str, Any]
    focus_detection_mode: str
    focus_detection_model: str
    focus_catalog_version: str
    focus_detection_result: Dict[str, Any]
    focus_summary: str
    query_len_original: int | None
    query_len_embedded: int | None
    query_was_truncated: bool | None
    retrieval_query_strategy: str
    embedding_query_preview: str
    retrieval_query_preview: str
    classifier_mode: str
    classifier_model: str
    classifier_items: List[Dict[str, Any]]
    classifier_items_count: int
    classifier_raw_response: str
    used_citations: List[Dict[str, Any]]
    used_citations_count: int
    citation_candidates_count: int
    telemetry_timing_ms: Dict[str, Any]
    citations: List[Dict[str, Any]]
    evidences: List[Dict[str, Any]]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
