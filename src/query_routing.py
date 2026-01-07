from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Tuple

import requests
from qdrant_client import QdrantClient
from qdrant_client.http.models import Filter


def ollama_embed(base_url: str, model: str, text: str) -> List[float]:
    r = requests.post(
        f"{base_url}/api/embeddings",
        json={"model": model, "prompt": text},
        timeout=120,
    )
    r.raise_for_status()
    return r.json()["embedding"]


def ollama_generate(base_url: str, model: str, prompt: str) -> str:
    # Non-streaming response
    r = requests.post(
        f"{base_url}/api/generate",
        json={"model": model, "prompt": prompt, "stream": False},
        timeout=300,
    )
    r.raise_for_status()
    data = r.json()
    return data.get("response", "").strip()


def _get_payload_text(payload: Any) -> str:
    # Supporta payload come dict o altri tipi
    if isinstance(payload, dict):
        for k in ("text", "chunk", "content", "page_content"):
            if k in payload and isinstance(payload[k], str):
                return payload[k]
        # fallback: prova a serializzare
        return str(payload)
    return str(payload)


def _build_grounded_prompt(query: str, evidences: List[Dict[str, Any]]) -> str:
    # Prompt “grounded”: rispondi SOLO con supporto dalle evidenze e cita gli id chunk.
    lines = []
    lines.append("Sei un assistente tecnico-contabile su IAS/IFRS.")
    lines.append("Rispondi in italiano, in modo discorsivo ma preciso.")
    lines.append(
        "Regola: usa SOLO le evidenze fornite. Se le evidenze non bastano, dì chiaramente che non è supportato e cosa manca."
    )
    lines.append("Includi citazioni nel testo nel formato [chunk_id].")
    lines.append("")
    lines.append(f"DOMANDA:\n{query}\n")
    lines.append("EVIDENZE:")
    for ev in evidences:
        cid = ev.get("chunk_id")
        score = ev.get("score")
        src = ev.get("source")
        text = ev.get("text", "")
        # tronca per non esplodere il prompt
        text_short = text if len(text) <= 1600 else (text[:1600] + " …")
        lines.append(
            f"\n- chunk_id: {cid} | score: {score} | source: {src}\n{text_short}"
        )
    lines.append("\nRISPOSTA:")
    return "\n".join(lines)


def qdrant_query_points(
    qdrant_client: QdrantClient,
    collection: str,
    query_vector: List[float],
    top_k: int,
    qdrant_filter: Optional[Filter] = None,
):
    res = qdrant_client.query_points(
        collection_name=collection,
        query=query_vector,
        query_filter=qdrant_filter,
        limit=int(top_k),
        with_payload=True,
        with_vectors=False,
    )
    # normalize
    return res.points if hasattr(res, "points") else res


def route_and_retrieve(
    query: str,
    qdrant_client: QdrantClient,
    collection: str,
    top_k: int = 6,
    score_threshold: float = 0.0,
    mode: str = "auto",
    qdrant_filter: Optional[Filter] = None,
) -> Dict[str, Any]:
    """
    MVP routing+retrieval:
    - embed query con Ollama
    - search su Qdrant
    - se OLLAMA_CHAT_MODEL è configurato: genera risposta grounded citando [chunk_id]
    - guardrail: se nessuna evidenza o best_score < score_threshold => no-answer (o answer conservativa)
    """
    ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    embed_model = os.getenv("OLLAMA_EMBED_MODEL", "mxbai-embed-large")
    chat_model = os.getenv("OLLAMA_CHAT_MODEL", "").strip()

    # Routing mode (MVP): auto e vector_only fanno la stessa cosa per ora
    routing = {"mode": mode, "selected": "vector"}

    # 1) Embed
    qvec = ollama_embed(ollama_base_url, embed_model, query)

    # 2) Search
    hits = qdrant_query_points(
        qdrant_client=qdrant_client,
        collection=collection,
        query_vector=qvec,
        top_k=int(top_k),
        qdrant_filter=qdrant_filter,
    )

    evidences: List[Dict[str, Any]] = []
    best_score = None

    for h in hits:
        payload = h.payload or {}
        text = _get_payload_text(payload)
        meta = payload.get("meta") if isinstance(payload, dict) else None

        ev = {
            "chunk_id": payload.get("chunk_id") if isinstance(payload, dict) else None,
            "id": getattr(h, "id", None),
            "score": float(getattr(h, "score", 0.0)),
            "source": payload.get("source") if isinstance(payload, dict) else None,
            "meta": meta,
            "text": text,
        }
        evidences.append(ev)

        if best_score is None or ev["score"] > best_score:
            best_score = ev["score"]

    # 3) Apply threshold filtering (per evidenze)
    if score_threshold and score_threshold > 0:
        evidences = [e for e in evidences if (e.get("score") or 0) >= score_threshold]

    citations = [
        {
            "chunk_id": e.get("chunk_id"),
            "source": e.get("source"),
            "score": e.get("score"),
        }
        for e in evidences
    ]

    # 4) Guardrail: se non abbiamo evidenze sufficienti
    guardrail = {
        "score_threshold": score_threshold,
        "best_score": best_score,
        "evidences_kept": len(evidences),
        "allowed_to_answer": bool(evidences),
    }

    answer: Optional[str] = None
    if evidences and chat_model:
        prompt = _build_grounded_prompt(query, evidences)
        answer = ollama_generate(ollama_base_url, chat_model, prompt)
    elif evidences and not chat_model:
        # MVP: se manca chat_model, restituiamo solo evidenze e un messaggio tecnico
        answer = (
            "Modello chat non configurato (OLLAMA_CHAT_MODEL). "
            "Mostro le evidenze recuperate; configura OLLAMA_CHAT_MODEL per generare una risposta grounded."
        )
    else:
        answer = (
            "Non ci sono evidenze sufficienti nel corpus indicizzato per rispondere in modo supportato. "
            "Riformula la domanda o amplia il corpus/indicizzazione."
        )

    return {
        "routing": routing,
        "query": query,
        "collection": collection,
        "top_k": top_k,
        "score_threshold": score_threshold,
        "answer": answer,
        "citations": citations,
        "evidences": evidences,
        "guardrail": guardrail,
        "models": {"embed_model": embed_model, "chat_model": chat_model or None},
        "ollama_base_url": ollama_base_url,
    }
