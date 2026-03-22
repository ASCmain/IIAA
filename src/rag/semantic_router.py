from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

from .ollama_io import ollama_embed


@dataclass
class SemanticRoute:
    catalog_version: str
    top_intent_id: str
    top_label: str
    top_question_type_hint: str
    top_score: float
    second_intent_id: str
    second_score: float
    ambiguity_gap: float
    ambiguous: bool
    candidates: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def semantic_router_catalog_path() -> str:
    return (os.getenv("SEMANTIC_ROUTER_CATALOG_PATH") or "config/semantic_intent_catalog.json").strip()


def semantic_router_enabled() -> bool:
    raw = (os.getenv("SEMANTIC_ROUTER_ENABLED") or "true").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


def _load_catalog(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    return json.loads(p.read_text(encoding="utf-8"))


def _item_text(item: dict[str, Any]) -> str:
    parts: list[str] = []
    parts.append(str(item.get("label") or ""))
    parts.append(str(item.get("description") or ""))

    for key in ("positive_examples", "negative_examples", "keywords"):
        vals = item.get(key) or []
        if isinstance(vals, list):
            parts.extend(str(x) for x in vals)

    return "\n".join(x for x in parts if x.strip())


def route_query_semantically(
    *,
    query: str,
    ollama_base_url: str,
    embed_model: str,
    catalog_path: str | Path | None = None,
) -> SemanticRoute:
    path = str(catalog_path or semantic_router_catalog_path())
    catalog = _load_catalog(path)
    catalog_version = str(catalog.get("catalog_version") or "")
    items = catalog.get("items") or []

    query_vec = ollama_embed(ollama_base_url, embed_model, query, max_chars=4000)

    ranked: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        text = _item_text(item)
        item_vec = ollama_embed(ollama_base_url, embed_model, text, max_chars=4000)
        score = _cosine(query_vec, item_vec)
        ranked.append(
            {
                "intent_id": str(item.get("intent_id") or ""),
                "label": str(item.get("label") or ""),
                "question_type_hint": str(item.get("question_type_hint") or ""),
                "score": float(score),
            }
        )

    ranked.sort(key=lambda x: x["score"], reverse=True)

    top = ranked[0] if ranked else {"intent_id": "", "label": "", "question_type_hint": "", "score": 0.0}
    second = ranked[1] if len(ranked) > 1 else {"intent_id": "", "score": 0.0}
    gap = float(top.get("score", 0.0)) - float(second.get("score", 0.0))
    ambiguous = gap < 0.03

    return SemanticRoute(
        catalog_version=catalog_version,
        top_intent_id=str(top.get("intent_id") or ""),
        top_label=str(top.get("label") or ""),
        top_question_type_hint=str(top.get("question_type_hint") or ""),
        top_score=float(top.get("score") or 0.0),
        second_intent_id=str(second.get("intent_id") or ""),
        second_score=float(second.get("score") or 0.0),
        ambiguity_gap=gap,
        ambiguous=ambiguous,
        candidates=ranked[:5],
    )
