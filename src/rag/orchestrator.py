from __future__ import annotations

from typing import Any, Dict

from qdrant_client import QdrantClient

from .language import detect_language_80_20
from .ollama_io import ollama_chat, ollama_embed
from .prompting import build_grounded_prompt, citation_label
from .retrieval import retrieve


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

    vec = ollama_embed(ollama_base_url, embed_model, q, max_chars=embed_max_chars)
    evidences = retrieve(qdrant_client, collection, vec, top_k=top_k, score_threshold=score_threshold)

    prompt = build_grounded_prompt(q, evidences, answer_language=lang)
    answer = ollama_chat(ollama_base_url, chat_model, prompt, temperature=temperature)

    citations = []
    for e in evidences:
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
        "citations": citations,
        "evidences": [e.__dict__ for e in evidences],
    }
