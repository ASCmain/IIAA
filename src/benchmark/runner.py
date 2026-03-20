from __future__ import annotations

import time
from typing import Any, Callable, Dict, Iterable, List
import traceback

from qdrant_client import QdrantClient

from src.PW_query_routing import run_query
from .models import BenchmarkCase, BenchmarkRunResult

ProgressCallback = Callable[[Dict[str, Any]], None]


def run_benchmark_cases(
    *,
    cases: Iterable[BenchmarkCase],
    qdrant_client: QdrantClient,
    collection_it: str,
    collection_en: str,
    ollama_base_url: str,
    embed_model: str,
    chat_model: str,
    progress_cb: ProgressCallback | None = None,
    selected_case_ids: set[str] | None = None,
    fail_fast: bool = True,
) -> List[BenchmarkRunResult]:
    case_list = list(cases)
    if selected_case_ids:
        case_list = [c for c in case_list if c.case_id in selected_case_ids]
    out: List[BenchmarkRunResult] = []
    total = len(case_list)

    for idx, case in enumerate(case_list, start=1):
        if progress_cb is not None:
            progress_cb(
                {
                    "event": "case_start",
                    "idx": idx,
                    "total": total,
                    "case_id": case.case_id,
                    "label": case.label,
                    "lang_mode": case.lang_mode,
                    "top_k": case.top_k,
                }
            )

        t0 = time.perf_counter()
        try:
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
            case_duration_ms = int((time.perf_counter() - t0) * 1000)

            result = BenchmarkRunResult(
                case_id=case.case_id,
                label=case.label,
                query=case.query,
                status="ok",
                error="",
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
            used_citations=payload.get("used_citations") or [],
            used_citations_count=payload.get("used_citations_count") or 0,
            citation_candidates_count=payload.get("citation_candidates_count") or 0,
            telemetry_timing_ms={
                **(payload.get("telemetry_timing_ms") or {}),
                "case_total_ms": case_duration_ms,
            },
            citations=payload.get("citations") or [],
            evidences=payload.get("evidences") or [],
        )

            out.append(result)

            if progress_cb is not None:
                progress_cb(
                    {
                        "event": "case_done",
                    "idx": idx,
                    "total": total,
                    "case_id": result.case_id,
                    "label": result.label,
                    "lang": result.lang,
                    "collection": result.collection,
                    "question_type": (result.query_plan or {}).get("question_type"),
                    "source_preference": (result.query_plan or {}).get("source_preference"),
                    "target_standards": (result.query_plan or {}).get("target_standards") or [],
                    "analysis_pool_count": result.analysis_pool_count,
                    "analysis_pool_target": result.analysis_pool_target,
                    "threshold_effective": result.threshold_effective,
                    "core_evidences_count": (result.query_plan or {}).get("core_evidences_count"),
                    "context_evidences_count": (result.query_plan or {}).get("context_evidences_count"),
                    "citations_count": len(result.citations or []),
                    "evidences_count": len(result.evidences or []),
                    "classifier_items_count": result.classifier_items_count,
                    "used_citations_count": result.used_citations_count,
                    "citation_candidates_count": result.citation_candidates_count,
                    "answer_len": len(result.answer or ""),
                    "case_total_ms": case_duration_ms,
                    "telemetry_timing_ms": result.telemetry_timing_ms,
                }
                )
        except Exception as e:
            case_duration_ms = int((time.perf_counter() - t0) * 1000)
            err = f"{type(e).__name__}: {e}"
            result = BenchmarkRunResult(
                case_id=case.case_id,
                label=case.label,
                query=case.query,
                status="error",
                error=err,
                answer="",
                lang=case.lang_mode,
                collection=collection_it if case.lang_mode == "IT" else collection_en,
                query_plan={},
                retrieval_raw_count=0,
                retrieval_above_initial_threshold_count=0,
                analysis_pool_count=0,
                analysis_pool_target=0,
                min_candidate_floor=0,
                threshold_initial=None,
                threshold_effective=None,
                coverage_warning_low_candidate_count=False,
                classifier_mode="",
                classifier_model="",
                classifier_items=[],
                classifier_items_count=0,
                classifier_raw_response="",
                used_citations=[],
                used_citations_count=0,
                citation_candidates_count=0,
                telemetry_timing_ms={"case_total_ms": case_duration_ms},
                citations=[],
                evidences=[],
            )
            out.append(result)

            if progress_cb is not None:
                progress_cb(
                    {
                        "event": "case_error",
                        "idx": idx,
                        "total": total,
                        "case_id": case.case_id,
                        "label": case.label,
                        "error": err,
                        "case_total_ms": case_duration_ms,
                        "traceback_tail": traceback.format_exc()[-1200:],
                    }
                )

            if fail_fast:
                raise

    return out
