from __future__ import annotations

from typing import Iterable, List

from qdrant_client import QdrantClient

from src.PW_query_routing import run_query
from .models import BenchmarkCase, BenchmarkRunResult


def run_benchmark_cases(
    *,
    cases: Iterable[BenchmarkCase],
    qdrant_client: QdrantClient,
    collection_it: str,
    collection_en: str,
    ollama_base_url: str,
    embed_model: str,
    chat_model: str,
) -> List[BenchmarkRunResult]:
    out: List[BenchmarkRunResult] = []

    for case in cases:
        payload = run_query(
            case.query,
            qdrant_client=qdrant_client,
            collection_it=collection_it,
            collection_en=collection_en,
            ollama_base_url=ollama_base_url,
            embed_model=embed_model,
            chat_model=chat_model,
            lang_mode=case.lang_mode,
            top_k=case.top_k,
            score_threshold=case.score_threshold,
            embed_max_chars=case.embed_max_chars,
            temperature=case.temperature,
        )

        out.append(
            BenchmarkRunResult(
                case_id=case.case_id,
                label=case.label,
                query=case.query,
                answer=payload.get("answer") or "",
                lang=payload.get("lang") or "",
                collection=payload.get("collection") or "",
                query_plan={
                    **(payload.get("query_plan") or {}),
                    "core_evidences_count": payload.get("core_evidences_count"),
                    "context_evidences_count": payload.get("context_evidences_count"),
                },
                retrieval_raw_count=payload.get("retrieval_raw_count") or 0,
                retrieval_above_initial_threshold_count=payload.get("retrieval_above_initial_threshold_count") or 0,
                analysis_pool_count=payload.get("analysis_pool_count") or 0,
                analysis_pool_target=payload.get("analysis_pool_target") or 0,
                min_candidate_floor=payload.get("min_candidate_floor") or 0,
                threshold_initial=payload.get("threshold_initial"),
                threshold_effective=payload.get("threshold_effective"),
                coverage_warning_low_candidate_count=bool(payload.get("coverage_warning_low_candidate_count")),
                classifier_mode=payload.get("classifier_mode") or "",
                classifier_model=payload.get("classifier_model") or "",
                classifier_items=payload.get("classifier_items") or [],
                classifier_items_count=payload.get("classifier_items_count") or 0,
                classifier_raw_response=payload.get("classifier_raw_response") or "",
                telemetry_timing_ms=payload.get("telemetry_timing_ms") or {},
                citations=payload.get("citations") or [],
                evidences=payload.get("evidences") or [],
            )
        )

    return out
