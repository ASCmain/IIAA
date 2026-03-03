from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import requests
from qdrant_client import QdrantClient


# ----------------------------
# Data structures
# ----------------------------
@dataclass
class Evidence:
    point_id: str
    score: float
    text: str
    source: str
    cite_key: Optional[str] = None        # e.g., "IAS36:18", "IFRS9:6.5.13"
    standard_id: Optional[str] = None     # e.g., "IAS 36"
    para_key: Optional[str] = None        # e.g., "18", "6.5.13", "141#2"
    section_path: Optional[str] = None    # e.g., "IAS 36 > DEFINITIONS"


# ----------------------------
# Ollama helpers
# ----------------------------
def _ollama_chat(base_url: str, model: str, prompt: str, temperature: float = 0.1) -> str:
    r = requests.post(
        f"{base_url}/api/generate",
        json={"model": model, "prompt": prompt, "stream": False, "options": {"temperature": temperature}},
        timeout=300,
    )
    r.raise_for_status()
    data = r.json()
    return (data.get("response") or "").strip()


def _ollama_embed(base_url: str, model: str, text: str, max_chars: int = 6000) -> List[float]:
    text = (text or "").replace("\x00", " ")
    prompt = text[: max(1, int(max_chars))]
    r = requests.post(
        f"{base_url}/api/embeddings",
        json={"model": model, "prompt": prompt},
        timeout=180,
    )
    r.raise_for_status()
    data = r.json()
    return data["embedding"]


# ----------------------------
# Language routing
# ----------------------------
_IT_HINTS = {
    "il","lo","la","i","gli","le","un","una","uno","del","della","dello","dei","delle",
    "che","per","con","come","anche","quale","quali","quando","dove","perché","poiché",
    "entità","bilancio","valore","riduzione","perdita","informativa","paragrafo","appendice"
}
_EN_HINTS = {
    "the","a","an","and","or","of","to","in","for","with","as","which","when","where",
    "entity","financial","statements","recoverable","impairment","paragraph","appendix"
}

def detect_language_80_20(text: str) -> str:
    """
    Heuristic, deterministic language guess between IT and EN.
    Returns "IT" or "EN".
    """
    t = re.sub(r"[^a-zA-ZàèéìòùÀÈÉÌÒÙ\s]", " ", (text or "")).lower()
    tokens = [w for w in t.split() if len(w) > 1][:200]
    if not tokens:
        return "IT"
    it = sum(1 for w in tokens if w in _IT_HINTS)
    en = sum(1 for w in tokens if w in _EN_HINTS)
    # 80/20-like bias: if one side is clearly stronger, pick it; else default IT (project context).
    if en >= max(2, int((it + en) * 0.55)):
        return "EN"
    return "IT"


# ----------------------------
# Prompting
# ----------------------------
def _format_evidence(e: Evidence, i: int) -> str:
    cite = e.cite_key or ""
    loc = f"{e.standard_id or ''} {e.para_key or ''}".strip()
    head = f"[{i}] {cite}".strip()
    if loc and cite and loc.replace(" ", "") != cite.replace(" ", ""):
        head = f"{head} ({loc})"
    elif loc and not cite:
        head = f"[{i}] {loc}"
    return (
        f"{head}\n"
        f"Source: {e.source}\n"
        f"Section: {e.section_path or ''}\n"
        f"Text: {e.text}\n"
    ).strip()


def build_grounded_prompt(query: str, evidences: List[Evidence], answer_language: str) -> str:
    """
    Enforces readable citations using cite_key, not chunk_id.
    The model must cite as [IAS36:18] / [IFRS9:6.5.13] / [IFRIC16:3] etc.
    """
    lang_note = "Italiano" if answer_language.upper() == "IT" else "English"
    cites = "\n\n".join(_format_evidence(e, i + 1) for i, e in enumerate(evidences))

    return f"""
You are an IAS/IFRS assistant. Answer in {lang_note}.
Rules:
- Use ONLY the provided evidence texts. If evidence is insufficient, say what is missing and stop.
- Do NOT cite chunk_id. Cite ONLY using cite_key in square brackets, e.g. [IAS36:18], [IFRS9:6.5.13], [IFRIC16:3].
- If you use multiple evidences, cite each relevant statement with the appropriate cite_key.

User question:
{query}

Evidence bundle (each item has cite_key + text):
{cites}

Now produce:
1) A concise answer (2–10 paragraphs), in {lang_note}.
2) A short bullet list "Citations used:" containing ONLY cite_keys you actually referenced.
""".strip()


# ----------------------------
# Retrieval + orchestration
# ----------------------------
def retrieve(
    qdrant_client: QdrantClient,
    collection: str,
    embed_vector: List[float],
    top_k: int = 8,
    score_threshold: float = 0.0,
) -> List[Evidence]:
    hits = qdrant_client.search(
        collection_name=collection,
        query_vector=embed_vector,
        limit=int(top_k),
        score_threshold=float(score_threshold) if score_threshold else None,
        with_payload=True,
    )

    out: List[Evidence] = []
    for h in hits:
        payload = h.payload or {}
        text = (payload.get("text") or "").strip()
        if not text:
            continue

        out.append(
            Evidence(
                point_id=str(h.id),
                score=float(h.score),
                text=text,
                source=str(payload.get("source") or payload.get("source_url") or payload.get("doc_id") or ""),
                cite_key=(payload.get("cite_key") or payload.get("meta", {}).get("cite_key")),
                standard_id=(payload.get("standard_id") or payload.get("meta", {}).get("standard_id")),
                para_key=(payload.get("para_key") or payload.get("meta", {}).get("para_key")),
                section_path=(payload.get("section_path") or payload.get("meta", {}).get("section_path")),
            )
        )
    return out


def run_query(
    query: str,
    *,
    qdrant_client: QdrantClient,
    collection_it: str,
    collection_en: str,
    ollama_base_url: str,
    embed_model: str,
    chat_model: str,
    lang_mode: str = "AUTO",   # AUTO | IT | EN
    top_k: int = 8,
    score_threshold: float = 0.0,
    embed_max_chars: int = 6000,
    temperature: float = 0.1,
) -> Dict[str, Any]:
    """
    Returns a dict usable by Streamlit:
      {
        "answer": str,
        "lang": "IT"|"EN",
        "collection": str,
        "citations": [{"cite_key":..., "source":..., "score":...}, ...],
        "evidences": [{...}, ...],
      }
    """
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

    vec = _ollama_embed(ollama_base_url, embed_model, q, max_chars=embed_max_chars)
    evidences = retrieve(qdrant_client, collection, vec, top_k=top_k, score_threshold=score_threshold)

    prompt = build_grounded_prompt(q, evidences, answer_language=lang)
    answer = _ollama_chat(ollama_base_url, chat_model, prompt, temperature=temperature)

    citations = []
    for e in evidences:
        citations.append(
            {
                "cite_key": e.cite_key,
                "standard_id": e.standard_id,
                "para_key": e.para_key,
                "section_path": e.section_path,
                "source": e.source,
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
