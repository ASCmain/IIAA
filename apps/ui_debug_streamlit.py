from __future__ import annotations

import json
import os
import sys
from datetime import datetime, UTC
from pathlib import Path
from typing import Any, Dict

import requests
import streamlit as st
from dotenv import load_dotenv
from qdrant_client import QdrantClient

# Ensure project root is importable when running "streamlit run apps/..."
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.query_routing import route_and_retrieve
from src.telemetry import TelemetryRecorder


def _now_tag() -> str:
    return datetime.now(UTC).strftime("%Y%m%d_%H%M%S")


def _safe_int(v: Any, default: int) -> int:
    try:
        return int(v)
    except Exception:
        return default


def _safe_float(v: Any, default: float) -> float:
    try:
        return float(v)
    except Exception:
        return default


def _ollama_tags(base_url: str) -> Dict[str, Any]:
    r = requests.get(f"{base_url}/api/tags", timeout=10)
    r.raise_for_status()
    return r.json()


def _qdrant_collections(qdrant_url: str) -> Dict[str, Any]:
    r = requests.get(f"{qdrant_url}/collections", timeout=10)
    r.raise_for_status()
    return r.json()


def _write_debug_dump(debug_dir: Path, payload: Dict[str, Any]) -> Path:
    debug_dir.mkdir(parents=True, exist_ok=True)
    out = debug_dir / f"ui_run_{_now_tag()}.json"
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def main() -> None:
    st.set_page_config(page_title="IIAA — Debug UI (M1.5)", layout="wide")

    load_dotenv(dotenv_path=Path(".env"))

    qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333")
    collection = os.getenv("QDRANT_COLLECTION", "tesi_mvp_ifrs_v01")

    ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    embed_model = os.getenv("OLLAMA_EMBED_MODEL", "mxbai-embed-large")
    chat_model = os.getenv("OLLAMA_CHAT_MODEL", "")

    default_top_k = _safe_int(os.getenv("RETRIEVAL_TOP_K", os.getenv("TOP_K", "6")), 6)
    default_threshold = _safe_float(os.getenv("RETRIEVAL_SCORE_THRESHOLD", os.getenv("SCORE_THRESHOLD", "0.0")), 0.0)

    debug_dump_dir = Path(os.getenv("DEBUG_DUMP_DIR", "debug_dump"))

    st.sidebar.header("Runtime controls")
    top_k = st.sidebar.number_input("top_k", min_value=1, max_value=50, value=default_top_k, step=1)
    score_threshold = st.sidebar.number_input(
        "score_threshold",
        min_value=0.0,
        max_value=1.0,
        value=float(default_threshold),
        step=0.01,
        help="Filtra evidenze sotto soglia. Imposta 0 per vedere tutto.",
    )
    mode = st.sidebar.selectbox(
        "routing mode",
        options=["auto", "vector_only"],
        index=0,
        help="auto usa il routing esistente; vector_only forza retrieval su Qdrant.",
    )

    qc = QdrantClient(url=qdrant_url)

    tab_ask, tab_debug, tab_system = st.tabs(["Ask", "Debug", "System"])

    # State
    if "last_payload" not in st.session_state:
        st.session_state["last_payload"] = None
    if "last_dump_path" not in st.session_state:
        st.session_state["last_dump_path"] = None
    if "last_telemetry_path" not in st.session_state:
        st.session_state["last_telemetry_path"] = None
    if "last_telemetry_summary" not in st.session_state:
        st.session_state["last_telemetry_summary"] = None

    with tab_system:
        st.subheader("System status")
        col1, col2 = st.columns(2)

        with col1:
            st.markdown("Qdrant")
            try:
                cols = _qdrant_collections(qdrant_url)
                st.success(f"OK — {qdrant_url}")
                st.json(cols)
                st.info(f"Collection (env): {collection}")
            except Exception as e:
                st.error(f"Qdrant non raggiungibile: {e}")

        with col2:
            st.markdown("Ollama")
            try:
                tags = _ollama_tags(ollama_base_url)
                st.success(f"OK — {ollama_base_url}")
                st.json(tags)
                st.info(f"Embed model (env): {embed_model}")
                if chat_model:
                    st.info(f"Chat model (env): {chat_model}")
            except Exception as e:
                st.error(f"Ollama non raggiungibile: {e}")

    with tab_ask:
        st.subheader("Query")
        query = st.text_area(
            "Inserisci una domanda IAS/IFRS",
            height=120,
            placeholder="Esempio: In IAS 36, quando si rileva una perdita per impairment e come si misura?",
        )

        colA, colB = st.columns([1, 1])
        run_btn = colA.button("Run", type="primary", use_container_width=True)
        export_btn = colB.button("Export last run (JSON)", use_container_width=True)

        if run_btn:
            if not query.strip():
                st.warning("Inserisci una query.")
            else:
                tm = TelemetryRecorder(step="ui_query")
                tm.start(
                    inputs={
                        "query_chars": len(query),
                        "top_k": int(top_k),
                        "score_threshold": float(score_threshold),
                        "mode": mode,
                        "collection": collection,
                        "qdrant_url": qdrant_url,
                        "embed_model": embed_model,
                        "chat_model": chat_model,
                    }
                )

                try:
                    with st.spinner("Eseguo retrieval / routing..."):
                        with tm.span("route_and_retrieve"):
                            payload = route_and_retrieve(
                                query=query,
                                qdrant_client=qc,
                                collection=collection,
                                top_k=int(top_k),
                                score_threshold=float(score_threshold),
                                mode=mode,
                            )

                    if not isinstance(payload, dict):
                        payload = {"result": payload}

                    payload["_ui_meta"] = {
                        "ts_utc": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                        "qdrant_url": qdrant_url,
                        "collection": collection,
                        "ollama_base_url": ollama_base_url,
                        "embed_model": embed_model,
                        "chat_model": chat_model,
                        "top_k": int(top_k),
                        "score_threshold": float(score_threshold),
                        "mode": mode,
                    }

                    answer = payload.get("answer") or payload.get("final_answer") or payload.get("response")
                    citations = payload.get("citations") or payload.get("sources") or []
                    evidences = payload.get("evidences") or payload.get("matches") or payload.get("chunks") or []

                    dump_path = _write_debug_dump(debug_dump_dir, payload)

                    # --- Deterministic abstain gate (professional rigor)
                    best_score = 0.0
                    try:
                        best_score = max((e.get("score") or 0.0) for e in evidences) if evidences else 0.0
                    except Exception:
                        best_score = 0.0

                    decision = "answered"
                    reason = None
                    if float(score_threshold) > 0 and (not evidences or best_score < float(score_threshold)):
                        decision = "abstained"
                        reason = "insufficient_evidence_after_threshold"
                        answer = (
                            "Non posso rispondere con rigore: non ho evidenze sufficienti nel corpus indicizzato "
                            f"(score_threshold={float(score_threshold):.2f}, top_k={int(top_k)}). "
                            "Suggerimento: indicizza lo standard pertinente o fornisci input/dati aggiuntivi."
                        )
                        citations = []

                    compact_hits = [
                        {
                            "chunk_id": e.get("chunk_id"),
                            "score": e.get("score"),
                            "doc_id": (e.get("meta") or {}).get("doc_id"),
                            "page": (e.get("meta") or {}).get("page"),
                            "source_path": (e.get("meta") or {}).get("source_path"),
                        }
                        for e in (evidences or [])[: int(top_k)]
                    ]

                    telemetry_path = tm.finalize(
                        outputs={
                            "has_answer": bool(answer),
                            "citations_count": len(citations) if isinstance(citations, list) else None,
                            "evidences_count": len(evidences) if isinstance(evidences, list) else None,
                        },
                        extra={
                            "top_k": int(top_k),
                            "score_threshold": float(score_threshold),
                            "best_score": float(best_score),
                            "decision": decision,
                            "reason": reason,
                            "retrieval": compact_hits,
                        },
                    )

                    # Read summary back from telemetry JSON (quick UX)
                    telemetry_summary = None
                    if telemetry_path:
                        try:
                            d = json.loads(Path(telemetry_path).read_text(encoding="utf-8"))
                            rss_peak = d.get("resources", {}).get("rss_peak_bytes")
                            duration_s = d.get("duration_s")
                            telemetry_summary = {
                                "duration_s": duration_s,
                                "rss_peak_mb": (rss_peak / (1024 * 1024)) if isinstance(rss_peak, (int, float)) else None,
                                "telemetry_file": str(telemetry_path),
                            }
                        except Exception:
                            pass

                    st.session_state["last_payload"] = payload
                    st.session_state["last_dump_path"] = str(dump_path)
                    st.session_state["last_telemetry_path"] = str(telemetry_path) if telemetry_path else None
                    st.session_state["last_telemetry_summary"] = telemetry_summary

                    st.markdown("Risposta")
                    if answer:
                        st.write(answer)
                    else:
                        st.warning("Nessuna risposta estratta (verifica il payload in Debug).")

                    st.markdown("Citazioni / Fonti")
                    if citations:
                        st.json(citations)
                    else:
                        st.info("Nessuna citazione nel payload (o guardrail attivo).")

                    st.markdown("Evidenze (retrieval)")
                    if evidences:
                        st.json(evidences)
                    else:
                        st.info("Nessuna evidenza nel payload (o nome campo diverso).")

                    st.caption(f"Debug dump salvato: {dump_path}")
                    if telemetry_summary:
                        st.caption(
                            f"Telemetry: {telemetry_summary['telemetry_file']} | "
                            f"duration={telemetry_summary['duration_s']:.3f}s | "
                            f"rss_peak≈{telemetry_summary['rss_peak_mb']:.1f} MB"
                        )
                    elif telemetry_path:
                        st.caption(f"Telemetry salvata: {telemetry_path}")

                except Exception as e:
                    tm.finalize(outputs={"error": repr(e)})
                    st.error(f"Errore durante l'esecuzione: {e}")
                    raise

        if export_btn:
            payload = st.session_state.get("last_payload")
            if not payload:
                st.warning("Nessun run da esportare.")
            else:
                data = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
                st.download_button(
                    label="Download last_payload.json",
                    data=data,
                    file_name="last_payload.json",
                    mime="application/json",
                    use_container_width=True,
                )

    with tab_debug:
        st.subheader("Raw payload & artifacts")
        payload = st.session_state.get("last_payload")
        dump_path = st.session_state.get("last_dump_path")
        telemetry_path = st.session_state.get("last_telemetry_path")
        telemetry_summary = st.session_state.get("last_telemetry_summary")

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("Payload (raw)")
            if payload:
                st.json(payload)
            else:
                st.info("Esegui una query nel tab Ask per vedere il payload.")

        with col2:
            st.markdown("Ultimi artefatti")
            if dump_path:
                st.code(f"debug_dump: {dump_path}")
            if telemetry_path:
                if telemetry_summary:
                    st.json(telemetry_summary)
                st.code(f"telemetry: {telemetry_path}")
            if not dump_path and not telemetry_path:
                st.info("Nessun artefatto disponibile.")

    st.caption("IIAA — Mini UI tecnica (M1.5). Locale-only.")


if __name__ == "__main__":
    main()
