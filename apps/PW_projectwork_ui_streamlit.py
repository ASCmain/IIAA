from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import streamlit as st
from qdrant_client import QdrantClient

# Ensure project root importable when running "streamlit run apps/..."
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.PW_query_routing import run_query


def utc_now_z() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def dump_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def format_citation(meta: dict, chunk_id: str | None = None) -> str:
    std = (meta or {}).get("standard_id") or ""
    para = (meta or {}).get("para_key") or ""
    cite_key = (meta or {}).get("cite_key") or ""
    if std and para:
        return f"{std} para {para}"
    if cite_key:
        return cite_key
    return chunk_id or ""

def main() -> None:
    st.set_page_config(page_title="IIAA — Project Work UI", layout="wide")
    st.title("IIAA — Project Work UI (EUR-Lex consolidated)")

    # Runtime env
    qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333")
    ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

    collection_it = os.getenv("QDRANT_COLLECTION_IT", os.getenv("QDRANT_COLLECTION", "iiaa_eurlex_02023R1803_it"))
    collection_en = os.getenv("QDRANT_COLLECTION_EN", os.getenv("QDRANT_COLLECTION", "iiaa_eurlex_02023R1803_en"))

    embed_model = os.getenv("OLLAMA_EMBED_MODEL", "mxbai-embed-large")
    chat_model = os.getenv("OLLAMA_CHAT_MODEL", os.getenv("OLLAMA_MODEL", "mistral"))

    st.sidebar.header("Runtime controls")

    lang_mode = st.sidebar.selectbox("Language", ["AUTO", "IT", "EN"], index=0, help="AUTO uses a deterministic 80/20 heuristic.")
    top_k = st.sidebar.number_input("top_k", min_value=1, max_value=50, value=8, step=1)
    score_threshold = st.sidebar.number_input("score_threshold", min_value=0.0, max_value=1.0, value=0.0, step=0.01, format="%.2f")
    temperature = st.sidebar.number_input("temperature", min_value=0.0, max_value=1.5, value=0.1, step=0.05, format="%.2f")

    embed_max_chars = st.sidebar.number_input("embed_max_chars", min_value=200, max_value=12000, value=6000, step=100)

    st.sidebar.markdown("---")
    st.sidebar.caption("Collections")
    st.sidebar.code(f"IT: {collection_it}\nEN: {collection_en}")

    st.sidebar.caption("Models")
    st.sidebar.code(f"embed: {embed_model}\nchat:  {chat_model}")

    qc = QdrantClient(url=qdrant_url)

    tab_ask, tab_debug, tab_system = st.tabs(["Ask", "Debug", "System"])

    with tab_system:
        st.subheader("System status")
        col1, col2 = st.columns(2)

        with col1:
            st.markdown("Qdrant")
            try:
                cols = qc.get_collections()
                st.success(f"OK — {qdrant_url}")
                st.json(cols.model_dump() if hasattr(cols, "model_dump") else cols)
            except Exception as e:
                st.error(f"Qdrant non raggiungibile: {e}")

        with col2:
            st.markdown("Environment")
            st.json(
                {
                    "QDRANT_URL": qdrant_url,
                    "QDRANT_COLLECTION_IT": collection_it,
                    "QDRANT_COLLECTION_EN": collection_en,
                    "OLLAMA_BASE_URL": ollama_base_url,
                    "OLLAMA_EMBED_MODEL": embed_model,
                    "OLLAMA_CHAT_MODEL": chat_model,
                }
            )

    with tab_ask:
        st.subheader("Query")
        query = st.text_area(
            "Inserisci la domanda (IAS/IFRS).",
            height=140,
            placeholder="Es: Qual è la definizione di valore recuperabile in IAS 36?",
        )

        colA, colB = st.columns([1, 1])
        with colA:
            run_btn = st.button("Run", type="primary")
        with colB:
            export_btn = st.button("Export last run")

        if "last_payload" not in st.session_state:
            st.session_state["last_payload"] = None
        if "last_dump_path" not in st.session_state:
            st.session_state["last_dump_path"] = None

        if run_btn:
            q = (query or "").strip()
            if not q:
                st.warning("Inserisci una query.")
            else:
                with st.spinner("Eseguo retrieval + risposta grounded..."):
                    payload = run_query(
                        q,
                        qdrant_client=qc,
                        collection_it=collection_it,
                        collection_en=collection_en,
                        ollama_base_url=ollama_base_url,
                        embed_model=embed_model,
                        chat_model=chat_model,
                        lang_mode=lang_mode,
                        top_k=int(top_k),
                        score_threshold=float(score_threshold),
                        embed_max_chars=int(embed_max_chars),
                        temperature=float(temperature),
                    )

                st.session_state["last_payload"] = payload

                dump_path = Path("debug_dump") / f"pw_ui_run_{utc_now_z().replace(':','').replace('-','')}.json"
                dump_json(dump_path, payload)
                st.session_state["last_dump_path"] = str(dump_path)

                st.markdown("Risposta")
                st.write(payload.get("answer") or "")

                st.markdown("Citations (readable)")
                cits = payload.get("citations") or []
                # Show only cite_key + locator + score
                st.json(
                    [
                        {
                            "cite_key": c.get("cite_key"),
                            "loc": f"{c.get('standard_id') or ''} {c.get('para_key') or ''}".strip() or None,
                            "section_path": c.get("section_path"),
                            "score": c.get("score"),
                            "source": c.get("source"),
                            "pdf_reference_path": c.get("pdf_reference_path"),
                        }
                        for c in cits
                    ]
                )

                if cits:
                    st.markdown("Riferimenti fonte")
                    for i, c in enumerate(cits, 1):
                        cite_key = c.get("cite_key") or "(no cite_key)"
                        source = c.get("source") or ""
                        pdf_ref = c.get("pdf_reference_path") or ""

                        st.markdown(f"**[{i}] {cite_key}**")
                        if source:
                            st.code(f"Fonte ufficiale: {source}")
                        if pdf_ref:
                            st.code(f"Riferimento locale PDF: {pdf_ref}")

                st.markdown("Retrieval evidences (raw)")
                st.json(payload.get("evidences") or [])

                st.caption(f"Debug dump salvato: {dump_path}")

        if export_btn:
            payload = st.session_state.get("last_payload")
            if not payload:
                st.warning("Nessun run da esportare.")
            else:
                st.download_button(
                    "Download last run (json)",
                    data=json.dumps(payload, ensure_ascii=False, indent=2),
                    file_name="pw_ui_last_run.json",
                    mime="application/json",
                )

    with tab_debug:
        st.subheader("Last payload & artifacts")
        payload = st.session_state.get("last_payload")
        dump_path = st.session_state.get("last_dump_path")

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("Payload (raw)")
            if payload:
                st.json(payload)
            else:
                st.info("Esegui una query nel tab Ask per vedere il payload.")
        with col2:
            st.markdown("Artifacts")
            if dump_path:
                st.code(f"debug_dump: {dump_path}")
            else:
                st.info("Nessun artefatto disponibile.")

    st.caption("IIAA — Project Work UI. Locale-only. Citazioni in formato leggibile (cite_key).")


if __name__ == "__main__":
    main()
