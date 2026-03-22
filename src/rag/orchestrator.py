from __future__ import annotations

import re
import time

from typing import Any, Dict

from qdrant_client import QdrantClient

from .language import detect_language_80_20
from .ollama_io import ollama_chat, ollama_embed
from .prompting import build_grounded_prompt, citation_label
from .retrieval import retrieve
from .query_planning import build_query_plan
from .source_policy import filter_evidences_for_plan, rerank_evidences_for_plan, split_core_and_context_for_plan, prune_evidences_for_plan, effective_threshold_for_plan, select_analysis_pool_for_plan, apply_focus_enforcement, gate_primary_standard_candidates
from .evidence_classifier import classify_evidences_with_llm, evidence_classifier_mode, evidence_classifier_model
from .focus_detection import detect_focus_with_llm, focus_detection_mode, focus_detection_model, focus_catalog_path, summarize_focus
from .semantic_router import route_query_semantically, semantic_router_enabled, semantic_router_catalog_path



def _apply_classifier_assist(core_evidences, context_evidences, classifier_items, question_type=""):
    by_point = {}
    for item in classifier_items or []:
        pid = str(item.get("point_id") or "")
        if pid:
            by_point[pid] = item

    new_core = []
    new_context = []

    for e in core_evidences:
        pid = str(getattr(e, "point_id", None) or "")
        label = (by_point.get(pid, {}) or {}).get("label")

        if label == "exclude":
            continue
        if label == "context":
            new_context.append(e)
            continue

        # default conservative branch
        new_core.append(e)

    core_ids = {str(getattr(e, "point_id", None) or "") for e in new_core}
    context_ids = {str(getattr(e, "point_id", None) or "") for e in new_context}

    for e in context_evidences:
        pid = str(getattr(e, "point_id", None) or "")
        if pid in core_ids or pid in context_ids:
            continue

        label = (by_point.get(pid, {}) or {}).get("label")
        if label == "exclude":
            continue

        # even if classifier says "core", keep original context as context
        # to preserve conservative governance.
        new_context.append(e)

    # safeguard: in interpretive/disclosure cases, preserve at least one context
    # if the classifier produced any non-excluded context candidates.
    if question_type in {"transition_disclosure", "rule_interpretation", "disclosure_check", "numeric_calculation", "mixed_numeric_interpretive"}:
        classifier_context_ids = {
            str(item.get("point_id") or "")
            for item in (classifier_items or [])
            if (item.get("label") or "") == "context"
        }

        existing_ids = {str(getattr(e, "point_id", None) or "") for e in new_context}
        if not new_context and classifier_context_ids:
            for e in list(core_evidences) + list(context_evidences):
                pid = str(getattr(e, "point_id", None) or "")
                if pid in classifier_context_ids and pid not in existing_ids:
                    new_context.append(e)
                    break

    # dedup preserve order
    seen = set()
    dedup_core = []
    for e in new_core:
        pid = str(getattr(e, "point_id", None) or "")
        if pid in seen:
            continue
        seen.add(pid)
        dedup_core.append(e)

    seen_ctx = set()
    dedup_context = []
    core_final_ids = {str(getattr(e, "point_id", None) or "") for e in dedup_core}
    for e in new_context:
        pid = str(getattr(e, "point_id", None) or "")
        if pid in core_final_ids or pid in seen_ctx:
            continue
        seen_ctx.add(pid)
        dedup_context.append(e)

    return dedup_core, dedup_context


def _extract_used_citations(answer: str, citations: list[dict]) -> list[dict]:
    text = str(answer or "")
    if not text or not citations:
        return []

    stop_re = re.compile(
        r"(?im)^\s*(?:\d+\)|[-*]\s*)?\s*(citations used:|lista citazioni utilizzate:|citazioni utilizzate:)\s*$"
    )
    m = stop_re.search(text)
    body = text[:m.start()] if m else text

    by_key = {}
    ordered_keys = []
    for c in citations:
        key = str((c or {}).get("cite_key") or "").strip()
        if not key:
            continue
        if key not in by_key:
            by_key[key] = c
            ordered_keys.append(key)

    matches = []
    for key in ordered_keys:
        pos = body.find(f"[{key}]")
        if pos >= 0:
            matches.append((pos, key))
            continue

        # fallback: accept plain cite label only if it appears in body before the summary block
        pos = body.find(key)
        if pos >= 0:
            matches.append((pos, key))

    matches.sort(key=lambda x: x[0])
    return [by_key[key] for _, key in matches]

def _normalize_query_text(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _build_retrieval_query(
    query: str,
    *,
    plan,
    focus_output: dict,
    semantic_route: dict,
    max_chars: int = 450,
) -> tuple[str, dict]:
    q_norm = _normalize_query_text(query)
    meta = {
        "query_len_original": len(q_norm),
        "query_len_embedded": len(q_norm),
        "query_was_truncated": False,
        "retrieval_query_strategy": "full_query",
    }

    if len(q_norm) <= max_chars:
        return q_norm, meta

    lines = [ln.strip() for ln in str(query or "").splitlines() if ln.strip()]
    title = lines[0] if lines else q_norm[:120]

    targets = [str(x).strip() for x in (getattr(plan, "target_standards", []) or []) if str(x).strip()]
    primary = [str(x).strip() for x in (focus_output.get("primary_standards") or []) if str(x).strip()]
    secondary = [str(x).strip() for x in (focus_output.get("secondary_standards") or []) if str(x).strip()]
    topics = [str(x).strip() for x in (focus_output.get("topic_axes") or []) if str(x).strip()]
    intents = [str(x).strip() for x in (focus_output.get("intent_axes") or []) if str(x).strip()]

    top_intent = str((semantic_route or {}).get("top_intent_id") or "").strip()
    if top_intent and top_intent not in intents:
        intents.append(top_intent)

    tail = _normalize_query_text(str(query or "")[-200:])

    parts = []
    if title:
        parts.append(title)
    if targets:
        parts.append("Standard target: " + ", ".join(targets[:3]))
    elif primary:
        parts.append("Standard focus: " + ", ".join(primary[:2]))
    if secondary:
        parts.append("Standard secondari: " + ", ".join(secondary[:2]))
    if topics:
        parts.append("Temi: " + ", ".join(topics[:3]))
    if intents:
        parts.append("Intento: " + ", ".join(intents[:1]))
    if tail:
        parts.append("Richiesta finale: " + tail)

    retrieval_query = _normalize_query_text(" | ".join(parts))

    if not retrieval_query:
        retrieval_query = q_norm[:max_chars]

    if len(retrieval_query) > max_chars:
        retrieval_query = retrieval_query[:max_chars].rsplit(" ", 1)[0].strip()

    if not retrieval_query:
        retrieval_query = q_norm[:max_chars].strip()

    meta.update(
        {
            "query_len_embedded": len(retrieval_query),
            "query_was_truncated": True,
            "retrieval_query_strategy": "semantic_compaction",
        }
    )
    return retrieval_query, meta

def run_query(
    query: str,
    *,
    qdrant_client: QdrantClient,
    collection_it: str,
    collection_en: str,
    ollama_base_url: str,
    embed_model: str,
    chat_model: str,
    lang_mode: str = "AUTO",
    top_k: int = 8,
    score_threshold: float = 0.0,
    embed_max_chars: int = 6000,
    temperature: float = 0.1,
) -> Dict[str, Any]:
    q = (query or "").strip()
    if not q:
        return {"answer": "", "lang": "IT", "collection": collection_it, "citations": [], "evidences": []}

    if lang_mode.upper() == "IT":
        lang = "IT"
    elif lang_mode.upper() == "EN":
        lang = "EN"
    else:
        lang = detect_language_80_20(q)

    collection = collection_it if lang == "IT" else collection_en

    semantic_router_query = _normalize_query_text(q)
    if len(semantic_router_query) > 450:
        semantic_router_query = semantic_router_query[:450].rsplit(" ", 1)[0].strip()

    semantic_route = {
        "catalog_version": "",
        "top_intent_id": "",
        "top_label": "",
        "top_question_type_hint": "",
        "top_score": 0.0,
        "second_intent_id": "",
        "second_score": 0.0,
        "ambiguity_gap": 0.0,
        "ambiguous": False,
        "candidates": [],
    }

    embedding_query_seed = _normalize_query_text(q)
    if len(embedding_query_seed) > 450:
        embedding_query_seed = embedding_query_seed[:450].rsplit(" ", 1)[0].strip()

    if semantic_router_enabled():
        semantic_route = route_query_semantically(
            query=embedding_query_seed,
            ollama_base_url=ollama_base_url,
            embed_model=embed_model,
            catalog_path=semantic_router_catalog_path(),
        ).to_dict()

    plan = build_query_plan(q, semantic_route=semantic_route)

    focus_mode = focus_detection_mode()
    focus_output = {
        "catalog_version": "",
        "primary_standards": [],
        "secondary_standards": [],
        "topic_axes": [],
        "intent_axes": [],
        "confidence": "low",
        "ambiguity_flags": [],
        "parse_error": "",
        "raw_response": "",
        "model": "",
    }
    if focus_mode in {"shadow", "assist"}:
        focus_output = detect_focus_with_llm(
            query=q,
            plan=plan.to_dict(),
            ollama_base_url=ollama_base_url,
            classifier_model=focus_detection_model(chat_model),
            answer_language=lang,
            catalog_path=focus_catalog_path(),
        )

    focus_summary = summarize_focus(focus_output)
    retrieval_pool_k = max(int(top_k), int(plan.suggested_top_k), int(plan.analysis_pool_target), 24)

    retrieval_embed_max_chars = min(int(embed_max_chars), 450)
    retrieval_query, retrieval_query_meta = _build_retrieval_query(
        q,
        plan=plan,
        focus_output=focus_output,
        semantic_route=semantic_route,
        max_chars=retrieval_embed_max_chars,
    )

    t_embed0 = time.perf_counter()
    vec = ollama_embed(
        ollama_base_url,
        embed_model,
        retrieval_query,
        max_chars=retrieval_embed_max_chars,
    )
    embed_ms = int((time.perf_counter() - t_embed0) * 1000)

    t_retrieve0 = time.perf_counter()
    retrieved = retrieve(
        qdrant_client,
        collection,
        vec,
        top_k=retrieval_pool_k,
        score_threshold=score_threshold,
    )
    retrieve_ms = int((time.perf_counter() - t_retrieve0) * 1000)

    retrieval_raw_count = len(retrieved)

    t_policy0 = time.perf_counter()
    filtered = filter_evidences_for_plan(plan, retrieved, requested_top_k=int(plan.analysis_pool_target))
    reranked = rerank_evidences_for_plan(plan, filtered)

    threshold_initial = effective_threshold_for_plan(plan)
    above_initial = [e for e in reranked if float(getattr(e, "score", 0.0) or 0.0) >= float(threshold_initial)]

    analysis_selection = select_analysis_pool_for_plan(plan, reranked)
    evidences = analysis_selection["analysis_pool"]

    if not evidences:
        evidences = reranked[: max(int(plan.analysis_pool_target), 12)]

    evidences = prune_evidences_for_plan(plan, evidences)
    evidences = gate_primary_standard_candidates(plan, evidences, focus_output=focus_output)
    policy_ms = int((time.perf_counter() - t_policy0) * 1000)

    core_evidences, context_evidences = split_core_and_context_for_plan(plan, evidences)

    if plan.question_type in {"change_analysis", "transition_disclosure"}:
        max_core = 4
        max_context = 4
    elif plan.question_type in {"rule_interpretation", "disclosure_check", "numeric_calculation", "mixed_numeric_interpretive"}:
        max_core = 5
        max_context = 8
    else:
        max_core = 4
        max_context = 6

    core_evidences = core_evidences[:max_core]
    context_evidences = context_evidences[:max_context]

    focus_enforced = False
    if focus_mode == "assist":
        new_core, new_context = apply_focus_enforcement(
            focus_output,
            core_evidences,
            context_evidences,
            question_type=plan.question_type,
        )
        if (
            len(new_core) != len(core_evidences)
            or len(new_context) != len(context_evidences)
            or [getattr(e, "point_id", None) for e in new_core] != [getattr(e, "point_id", None) for e in core_evidences]
        ):
            focus_enforced = True
        core_evidences, context_evidences = new_core[:max_core], new_context[:max_context]

    prompt = build_grounded_prompt(
        q,
        core_evidences=core_evidences,
        context_evidences=context_evidences,
        answer_language=lang,
        focus_summary=focus_summary,
    )
    t_prompt0 = time.perf_counter()
    answer = ollama_chat(ollama_base_url, chat_model, prompt, temperature=temperature)
    prompt_ms = int((time.perf_counter() - t_prompt0) * 1000)

    core_ids = {getattr(e, "point_id", None) for e in core_evidences}
    final_evidences = list(core_evidences) + [e for e in context_evidences if getattr(e, "point_id", None) not in core_ids]

    classifier_mode = evidence_classifier_mode()
    classifier_output = {"items": [], "raw_response": "", "model": ""}
    classifier_ms = 0
    if classifier_mode in {"shadow", "assist"}:
        t_classifier0 = time.perf_counter()
        classifier_output = classify_evidences_with_llm(
            query=q,
            plan=plan.to_dict(),
            evidences=final_evidences,
            ollama_base_url=ollama_base_url,
            classifier_model=evidence_classifier_model(chat_model),
            answer_language=lang,
        )
        classifier_ms = int((time.perf_counter() - t_classifier0) * 1000)

    if classifier_mode == "assist":
        core_evidences, context_evidences = _apply_classifier_assist(
            core_evidences,
            context_evidences,
            classifier_output.get("items") or [],
            question_type=plan.question_type,
        )
        core_ids = {getattr(e, "point_id", None) for e in core_evidences}
        final_evidences = list(core_evidences) + [
            e for e in context_evidences if getattr(e, "point_id", None) not in core_ids
        ]

    citations = []
    for e in final_evidences:
        citations.append(
            {
                "cite_key": citation_label(e),
                "standard_id": e.standard_id,
                "para_key": e.para_key,
                "section_path": e.section_path,
                "source": e.source,
                "pdf_reference_path": e.pdf_reference_path,
                "score": e.score,
            }
        )

    used_citations = _extract_used_citations(answer, citations)

    return {
        "answer": answer,
        "lang": lang,
        "collection": collection,
        "query_plan": plan.to_dict(),
        "semantic_route": semantic_route,
        "focus_detection_mode": focus_mode,
        "focus_detection_model": focus_output.get("model") or "",
        "focus_catalog_version": focus_output.get("catalog_version") or "",
        "focus_detection_result": {
            "primary_standards": focus_output.get("primary_standards") or [],
            "secondary_standards": focus_output.get("secondary_standards") or [],
            "topic_axes": focus_output.get("topic_axes") or [],
            "intent_axes": focus_output.get("intent_axes") or [],
            "confidence": focus_output.get("confidence") or "low",
            "ambiguity_flags": focus_output.get("ambiguity_flags") or [],
            "parse_error": focus_output.get("parse_error") or "",
        },
        "focus_summary": focus_summary,
        "retrieval_raw_count": retrieval_raw_count,
        "retrieval_above_initial_threshold_count": len(above_initial),
        "retrieval_query_preview": retrieval_query[:300],
        "query_len_original": retrieval_query_meta.get("query_len_original"),
        "query_len_embedded": retrieval_query_meta.get("query_len_embedded"),
        "query_was_truncated": retrieval_query_meta.get("query_was_truncated"),
        "retrieval_query_strategy": retrieval_query_meta.get("retrieval_query_strategy"),
        "analysis_pool_count": analysis_selection.get("analysis_pool_count"),
        "analysis_pool_target": analysis_selection.get("analysis_pool_target"),
        "min_candidate_floor": analysis_selection.get("min_candidate_floor"),
        "threshold_initial": threshold_initial,
        "threshold_effective": analysis_selection.get("threshold_used"),
        "coverage_warning_low_candidate_count": analysis_selection.get("coverage_warning_low_candidate_count"),
        "max_core": max_core,
        "max_context": max_context,
        "policy_trace": {
            "question_type_detected": plan.question_type,
            "source_preference": plan.source_preference,
            "target_standards": plan.target_standards or [],
            "semantic_route_top_intent": semantic_route.get("top_intent_id") or "",
            "semantic_route_hint": semantic_route.get("top_question_type_hint") or "",
            "semantic_route_ambiguous": bool(semantic_route.get("ambiguous")),
            "focus_primary_detected": focus_output.get("primary_standards") or [],
            "primary_candidate_gating": True,
            "focus_enforced": focus_enforced,
            "analysis_pool_target": int(plan.analysis_pool_target),
            "min_candidate_floor": int(plan.min_candidate_floor),
            "threshold_fallback_ladder": list(plan.threshold_fallback_ladder or []),
            "policy_notes": list(plan.notes or []),
        },
        "core_evidences_count": len(core_evidences),
        "context_evidences_count": len(context_evidences),
        "core_cite_keys": [
            str(getattr(e, "cite_key", "") or "")
            for e in core_evidences
            if str(getattr(e, "cite_key", "") or "").strip()
        ],
        "context_cite_keys": [
            str(getattr(e, "cite_key", "") or "")
            for e in context_evidences
            if str(getattr(e, "cite_key", "") or "").strip()
        ],
        "classifier_mode": classifier_mode,
        "classifier_model": classifier_output.get("model") or "",
        "classifier_items": classifier_output.get("items") or [],
        "classifier_items_count": len(classifier_output.get("items") or []),
        "classifier_raw_response": classifier_output.get("raw_response") or "",
        "used_citations": used_citations,
        "used_citations_count": len(used_citations),
        "citation_candidates_count": len(citations),
        "telemetry_timing_ms": {
            "embed_ms": embed_ms,
            "retrieve_ms": retrieve_ms,
            "policy_ms": policy_ms,
            "classifier_ms": classifier_ms,
            "prompt_ms": prompt_ms,
            "total_ms": embed_ms + retrieve_ms + policy_ms + classifier_ms + prompt_ms,
        },
        "citations": citations,
        "evidences": [e.__dict__ for e in final_evidences],
    }
