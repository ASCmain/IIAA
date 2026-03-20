from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .ollama_io import ollama_chat


_ALLOWED_CONFIDENCE = {"high", "medium", "low"}


def focus_detection_mode() -> str:
    return (os.getenv("FOCUS_DETECTION_MODE") or "off").strip().lower()


def focus_detection_model(default_chat_model: str) -> str:
    return (os.getenv("FOCUS_DETECTION_MODEL") or default_chat_model).strip()


def focus_catalog_path() -> str:
    return (os.getenv("FOCUS_CATALOG_PATH") or "config/focus_catalog_ifrs.json").strip()


def load_focus_catalog(path: str | Path | None = None) -> dict[str, Any]:
    p = Path(path or focus_catalog_path())
    data = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return {"catalog_version": "", "standards": [], "intent_axes": [], "confidence_levels": []}
    return data


def _safe_json_parse(raw: str) -> dict[str, Any]:
    raw = (raw or "").strip()
    if not raw:
        return {"parse_error": "empty_raw"}

    try:
        obj = json.loads(raw)
        if isinstance(obj, dict):
            return obj
    except Exception as e:
        return {"parse_error": repr(e)}

    return {"parse_error": "root_not_dict"}


def _normalize_list(xs: Any, allowed: set[str] | None = None) -> list[str]:
    if not isinstance(xs, list):
        return []
    out: list[str] = []
    seen = set()
    for x in xs:
        s = str(x or "").strip()
        if not s:
            continue
        if allowed is not None and s not in allowed:
            continue
        if s in seen:
            continue
        seen.add(s)
        out.append(s)
    return out


def _normalize_focus_output(data: dict[str, Any], catalog: dict[str, Any]) -> dict[str, Any]:
    standards = catalog.get("standards") or []
    standard_ids = {str(s.get("id") or "").strip() for s in standards if str(s.get("id") or "").strip()}
    intent_ids = {str(x).strip() for x in (catalog.get("intent_axes") or []) if str(x).strip()}

    topic_ids = set()
    for s in standards:
        for t in (s.get("topic_axes") or []):
            ts = str(t or "").strip()
            if ts:
                topic_ids.add(ts)

    confidence = str(data.get("confidence") or "").strip().lower()
    if confidence not in _ALLOWED_CONFIDENCE:
        confidence = "low"

    ambiguity_flags = _normalize_list(data.get("ambiguity_flags"))
    if not ambiguity_flags:
        ambiguity_flags = []

    return {
        "primary_standards": _normalize_list(data.get("primary_standards"), allowed=standard_ids),
        "secondary_standards": _normalize_list(data.get("secondary_standards"), allowed=standard_ids),
        "topic_axes": _normalize_list(data.get("topic_axes"), allowed=topic_ids),
        "intent_axes": _normalize_list(data.get("intent_axes"), allowed=intent_ids),
        "confidence": confidence,
        "ambiguity_flags": ambiguity_flags,
    }


def _build_focus_prompt(*, query: str, plan: dict[str, Any], catalog: dict[str, Any], answer_language: str) -> str:
    catalog_json = json.dumps(catalog, ensure_ascii=False, indent=2)
    plan_json = json.dumps(plan or {}, ensure_ascii=False, indent=2)

    return f"""You are a domain focus detector for IFRS/IAS questions.

Task:
Given the user query, the query plan, and the controlled domain catalog, identify:
- primary_standards
- secondary_standards
- topic_axes
- intent_axes
- confidence
- ambiguity_flags

Rules:
- You MUST only select values that exist in the provided catalog.
- Do NOT invent standards, topic axes, or intent axes.
- Return JSON only.
- Keep the output concise and structured.
- If uncertain, lower confidence and add ambiguity flags.
- Prefer precision over recall.

Answer language preference: {answer_language}

Query:
{query}

Query plan:
{plan_json}

Controlled domain catalog:
{catalog_json}

Return exactly this JSON shape:
{{
  "primary_standards": [],
  "secondary_standards": [],
  "topic_axes": [],
  "intent_axes": [],
  "confidence": "high",
  "ambiguity_flags": []
}}
"""


def detect_focus_with_llm(
    *,
    query: str,
    plan: dict[str, Any],
    ollama_base_url: str,
    classifier_model: str,
    answer_language: str,
    catalog_path: str | None = None,
) -> dict[str, Any]:
    catalog = load_focus_catalog(catalog_path)
    prompt = _build_focus_prompt(
        query=query,
        plan=plan,
        catalog=catalog,
        answer_language=answer_language,
    )
    raw = ollama_chat(ollama_base_url, classifier_model, prompt, temperature=0.0)
    parsed = _safe_json_parse(raw)

    if parsed.get("parse_error"):
        return {
            "catalog_version": catalog.get("catalog_version") or "",
            "primary_standards": [],
            "secondary_standards": [],
            "topic_axes": [],
            "intent_axes": [],
            "confidence": "low",
            "ambiguity_flags": ["parse_error"],
            "parse_error": parsed.get("parse_error") or "",
            "raw_response": raw,
            "model": classifier_model,
        }

    normalized = _normalize_focus_output(parsed, catalog)
    normalized["catalog_version"] = catalog.get("catalog_version") or ""
    normalized["parse_error"] = ""
    normalized["raw_response"] = raw
    normalized["model"] = classifier_model
    return normalized
