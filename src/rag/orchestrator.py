from __future__ import annotations

from typing import Any, Dict

from qdrant_client import QdrantClient

from .language import detect_language_80_20
from .ollama_io import ollama_chat, ollama_embed
from .prompting import build_grounded_prompt, citation_label
from .retrieval import retrieve
from .query_planning import build_query_plan
from .source_policy import filter_evidences_for_plan, rerank_evidences_for_plan, split_core_and_context_for_plan

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

    plan = build_query_plan(q)
    retrieval_pool_k = max(int(top_k), int(plan.suggested_top_k), 12)

    vec = ollama_embed(ollama_base_url, embed_model, q, max_chars=embed_max_chars)
    evidences = retrieve(
        qdrant_client,
        collection,
        vec,
        top_k=retrieval_pool_k,
        score_threshold=score_threshold,
    )
    evidences = filter_evidences_for_plan(plan, evidences, requested_top_k=int(top_k))
    evidences = rerank_evidences_for_plan(plan, evidences)
    evidences = evidences[: max(int(top_k), 8)]

    core_evidences, context_evidences = split_core_and_context_for_plan(plan, evidences)

    max_core = 4 if plan.question_type in {"change_analysis", "transition_disclosure"} else 5
    max_context = 2 if plan.question_type in {"change_analysis", "transition_disclosure"} else 4

    core_evidences = core_evidences[:max_core]
    context_evidences = context_evidences[:max_context]

    prompt = build_grounded_prompt(
        q,
        core_evidences=core_evidences,
        context_evidences=context_evidences,
        answer_language=lang,
    )
    answer = ollama_chat(ollama_base_url, chat_model, prompt, temperature=temperature)

    core_ids = {getattr(e, "point_id", None) for e in core_evidences}
    final_evidences = list(core_evidences) + [e for e in context_evidences if getattr(e, "point_id", None) not in core_ids]

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

    return {
        "answer": answer,
        "lang": lang,
        "collection": collection,
        "query_plan": plan.to_dict(),
        "core_evidences_count": len(core_evidences),
        "context_evidences_count": len(context_evidences),
        "citations": citations,
        "evidences": [e.__dict__ for e in final_evidences],
    }
