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
                citations=payload.get("citations") or [],
                evidences=payload.get("evidences") or [],
            )
        )

    return out
