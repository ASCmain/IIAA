from __future__ import annotations

from typing import List, Optional

from qdrant_client import QdrantClient
from qdrant_client.http import models

from .models import Evidence


def retrieve(
    qdrant_client: QdrantClient,
    collection: str,
    query_vector: List[float],
    top_k: int,
    score_threshold: float,
    query_filter: Optional[models.Filter] = None,
) -> List[Evidence]:
    resp = qdrant_client.query_points(
        collection_name=collection,
        query=query_vector,
        limit=int(top_k),
        with_payload=True,
        with_vectors=False,
        score_threshold=float(score_threshold) if score_threshold is not None else None,
        query_filter=query_filter,
    )

    points = getattr(resp, "points", resp)

    evidences: List[Evidence] = []
    for p in points:
        payload = getattr(p, "payload", None) or {}
        evidences.append(
            Evidence(
                point_id=str(getattr(p, "id", "")),
                score=float(getattr(p, "score", 0.0)),
                text=str(payload.get("text") or ""),
                source=str(
                    payload.get("source")
                    or payload.get("source_url")
                    or payload.get("source_path")
                    or payload.get("doc_id")
                    or ""
                ),
                cite_key=payload.get("cite_key"),
                standard_id=payload.get("standard_id"),
                para_key=payload.get("para_key"),
                section_path=payload.get("section_path"),
                pdf_reference_path=payload.get("pdf_reference_path"),
            )
        )
    return evidences
