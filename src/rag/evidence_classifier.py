from __future__ import annotations

import json
import os
from typing import Any, Dict, List

from .models import Evidence
from .ollama_io import ollama_chat
from .source_policy import classify_evidence_tiers


_ALLOWED_LABELS = {"core", "context", "exclude"}
_ALLOWED_CONFIDENCE = {"high", "medium", "low"}


class _PlanShim:
    def __init__(self, data: Dict[str, Any]):
        self.question_type = data.get("question_type")
        self.target_standards = data.get("target_standards") or []
        self.source_preference = data.get("source_preference")
        self.needs_change_tracking = bool(data.get("needs_change_tracking"))
        self.needs_transition_focus = bool(data.get("needs_transition_focus"))
        self.needs_disclosure_focus = bool(data.get("needs_disclosure_focus"))
        self.needs_numeric_reasoning = bool(data.get("needs_numeric_reasoning"))
        self.needs_consolidated_priority = bool(data.get("needs_consolidated_priority"))
        self.needs_modifying_act_priority = bool(data.get("needs_modifying_act_priority"))


def evidence_classifier_mode() -> str:
    return (os.getenv("EVIDENCE_CLASSIFIER_MODE") or "off").strip().lower()


def evidence_classifier_model(default_chat_model: str) -> str:
    return (os.getenv("EVIDENCE_CLASSIFIER_MODEL") or default_chat_model).strip()


def _build_prompt(query: str, plan: Dict[str, Any], evidences: List[Evidence], answer_language: str) -> str:
    plan_json = json.dumps(plan, ensure_ascii=False)
    items = []
    plan_shim = _PlanShim(plan)

    for i, e in enumerate(evidences, start=1):
        tiers = classify_evidence_tiers(plan_shim, e)
        items.append(
            {
                "idx": i,
                "point_id": e.point_id,
                "cite_key": e.cite_key,
                "standard_id": e.standard_id,
                "para_key": e.para_key,
                "section_path": e.section_path,
                "source": e.source,
                "score": e.score,
                "legal_tier": tiers.get("legal_tier"),
                "semantic_tier": tiers.get("semantic_tier"),
                "is_target": tiers.get("is_target"),
                "is_measurement_context": tiers.get("is_measurement_context"),
                "mentions_intangible_context": tiers.get("mentions_intangible_context"),
                "text_preview": (e.text or "")[:1800],
            }
        )
    items_json = json.dumps(items, ensure_ascii=False, indent=2)

    return f"""
You are a local evidence classifier for an IAS/IFRS grounded retrieval system.

Task:
Classify each evidence item for the user query into exactly one label:
- core
- context
- exclude

Definitions:
- core: directly decisive to answer the query
- context: useful to clarify, distinguish concepts, or support interpretation
- exclude: not useful enough or likely distracting for the final answer

Important constraints:
- Prefer target standards over adjacent standards.
- Use legal_tier and semantic_tier as meaningful signals.
- For change-analysis queries, prefer modifying-act evidence and directly affected standards.
- For rule-interpretation queries, keep the target standard as core and adjacent standards usually as context.
- For numeric or measurement-oriented queries, evidence flagged as measurement context is usually relevant at least as context.
- Do not invent information beyond the provided items.
- Return ONLY valid JSON.

User query:
{query}

Query plan:
{plan_json}

Evidence items:
{items_json}

Return JSON with this shape:
{{
  "items": [
    {{
      "point_id": "...",
      "label": "core|context|exclude",
      "confidence": "high|medium|low",
      "reason_code": "short_snake_case_code",
      "notes": "brief explanation"
    }}
  ]
}}
""".strip()


def _extract_first_json_object(raw: str) -> str:
    raw = (raw or "").strip()
    if not raw:
        return ""

    start = raw.find("{")
    if start < 0:
        return ""

    depth = 0
    in_str = False
    escape = False

    for i in range(start, len(raw)):
        ch = raw[i]

        if in_str:
            if escape:
                escape = False
            elif ch == "\\":  # escaped char inside string
                escape = True
            elif ch == '"':
                in_str = False
            continue

        if ch == '"':
            in_str = True
            continue

        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return raw[start:i + 1]

    return raw[start:]


def _try_close_json(candidate: str) -> str:
    s = (candidate or "").strip()
    if not s:
        return s

    open_curly = s.count("{")
    close_curly = s.count("}")
    open_square = s.count("[")
    close_square = s.count("]")

    if close_square < open_square:
        s += "]" * (open_square - close_square)
    if close_curly < open_curly:
        s += "}" * (open_curly - close_curly)
    return s


def _normalize_classifier_items(items: Any) -> Dict[str, Any]:
    if not isinstance(items, list):
        return {"items": []}

    clean_items = []
    for obj in items:
        if not isinstance(obj, dict):
            continue

        point_id = str(obj.get("point_id") or "").strip()
        label = str(obj.get("label") or "").strip().lower()
        confidence = str(obj.get("confidence") or "").strip().lower()
        reason_code = str(obj.get("reason_code") or "").strip()
        notes = str(obj.get("notes") or "").strip()

        if not point_id:
            continue
        if label not in _ALLOWED_LABELS:
            label = "exclude"
        if confidence not in _ALLOWED_CONFIDENCE:
            confidence = "low"

        clean_items.append(
            {
                "point_id": point_id,
                "label": label,
                "confidence": confidence,
                "reason_code": reason_code,
                "notes": notes,
            }
        )

    return {"items": clean_items}



def _extract_items_list_candidate(raw: str) -> str:
    raw = (raw or "").strip()
    marker = '"items"'
    i = raw.find(marker)
    if i < 0:
        return ""

    j = raw.find("[", i)
    if j < 0:
        return ""

    tail = raw[j:].strip()

    # elimina l'eventuale graffa finale dell'oggetto root
    if tail.endswith("}"):
        tail = tail[:-1].rstrip()

    # se manca la chiusura dell'array, aggiungila
    if "]" not in tail:
        tail = tail + "]"

    # prendiamo fino all'ultima ]
    last_sq = tail.rfind("]")
    if last_sq >= 0:
        tail = tail[: last_sq + 1]

    # se mancano graffe di oggetti interni, inseriscile prima della ]
    open_curly = tail.count("{")
    close_curly = tail.count("}")
    if open_curly > close_curly and last_sq >= 0:
        missing = open_curly - close_curly
        tail = tail[:last_sq] + ("}" * missing) + tail[last_sq:]

    return tail.strip()

def _safe_parse_classifier_output(raw: str) -> Dict[str, Any]:
    raw = (raw or "").strip()
    if not raw:
        return {"items": [], "parse_error": "empty_raw"}

    candidates = []

    # 1) direct parse
    candidates.append(raw)

    # 2) first plausible JSON object
    extracted = _extract_first_json_object(raw)
    if extracted and extracted != raw:
        candidates.append(extracted)

    # 3) assistive closure for incomplete JSON object
    if extracted:
        closed = _try_close_json(extracted)
        if closed not in candidates:
            candidates.append(closed)

    # 4) assistive closure on raw
    closed_raw = _try_close_json(raw)
    if closed_raw not in candidates:
        candidates.append(closed_raw)

    last_error = ""
    for cand in candidates:
        try:
            data = json.loads(cand)
            if not isinstance(data, dict):
                last_error = "root_not_dict"
                continue
            normalized = _normalize_classifier_items(data.get("items"))
            normalized["parse_error"] = ""
            return normalized
        except Exception as e:
            last_error = repr(e)

    # 5) recovery path: parse only the items list
    try:
        items_candidate = _extract_items_list_candidate(raw)
        if items_candidate:
            items = json.loads(items_candidate)
            normalized = _normalize_classifier_items(items)
            normalized["parse_error"] = ""
            return normalized
    except Exception as e:
        last_error = repr(e)

    # 6) stronger recovery path for truncated object:
    # if raw looks like {"items": [ ... }  -> rebuild list by removing final stray "}"
    try:
        marker = '"items"'
        i = raw.find(marker)
        if i >= 0:
            j = raw.find("[", i)
            if j >= 0:
                tail = raw[j:].strip()
                if tail.endswith("}"):
                    tail = tail[:-1].rstrip()
                if not tail.endswith("]"):
                    tail = tail + "]"
                items = json.loads(tail)
                normalized = _normalize_classifier_items(items)
                normalized["parse_error"] = ""
                return normalized
    except Exception as e:
        last_error = repr(e)

    return {"items": [], "parse_error": last_error}


def classify_evidences_with_llm(
    *,
    query: str,
    plan: Dict[str, Any],
    evidences: List[Evidence],
    ollama_base_url: str,
    classifier_model: str,
    answer_language: str,
) -> Dict[str, Any]:
    if not evidences:
        return {"items": [], "raw_response": "", "model": classifier_model, "parse_error": ""}

    prompt = _build_prompt(
        query=query,
        plan=plan,
        evidences=evidences,
        answer_language=answer_language,
    )
    raw = ollama_chat(ollama_base_url, classifier_model, prompt, temperature=0.0)
    parsed = _safe_parse_classifier_output(raw)
    parsed["raw_response"] = raw
    parsed["model"] = classifier_model
    return parsed
