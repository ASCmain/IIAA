from __future__ import annotations

import os
import sys
from datetime import datetime, UTC
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from qdrant_client import QdrantClient

from src.benchmark import BenchmarkCase, run_benchmark_cases, write_json, write_jsonl


def main() -> int:
    qdrant_url = os.environ["QDRANT_URL"]
    ollama_base = os.environ["OLLAMA_BASE_URL"]
    collection_it = os.environ["QDRANT_COLLECTION_IT"]
    collection_en = os.environ["QDRANT_COLLECTION_EN"]

    embed_model = os.environ.get("BENCHMARK_EMBED_MODEL", "mxbai-embed-large:latest")
    chat_model = os.environ.get("BENCHMARK_CHAT_MODEL", "mistral:latest")

    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out_dir = Path("debug_dump/benchmark_runs") / f"smoke_{run_id}"
    out_dir.mkdir(parents=True, exist_ok=True)

    cases = [
        BenchmarkCase(
            case_id="pw_ifrs9_7_reg_2025_1266_main_changes",
            label="UE 2025/1266 - modifiche principali IFRS 9/7",
            query="Quali sono le modifiche principali del regolamento UE 2025/1266 relative a IFRS 9 e IFRS 7?",
            lang_mode="IT",
            top_k=5,
            temperature=0.0,
        ),
        BenchmarkCase(
            case_id="pw_ifrs7_reg_2025_1266_disclosure_transition",
            label="UE 2025/1266 - disclosure/transizione IFRS 7",
            query="Il regolamento UE 2025/1266 introduce cambiamenti rilevanti per disclosure o transizione di IFRS 7? Rispondi in modo prudente e indica le fonti.",
            lang_mode="IT",
            top_k=5,
            temperature=0.0,
        ),
        BenchmarkCase(
            case_id="pw_ias36_mvp_smoke",
            label="IAS 36 - smoke continuity",
            query="Ai sensi dello IAS 36, come si determina in sintesi il valore recuperabile di una CGU e quando si rileva una perdita di valore?",
            lang_mode="IT",
            top_k=5,
            temperature=0.0,
        ),
    ]

    client = QdrantClient(url=qdrant_url)
    results = run_benchmark_cases(
        cases=cases,
        qdrant_client=client,
        collection_it=collection_it,
        collection_en=collection_en,
        ollama_base_url=ollama_base,
        embed_model=embed_model,
        chat_model=chat_model,
    )

    def assess_result(r):
        answer = r.answer or ""
        labels = [c.get("cite_key") for c in (r.citations or []) if c.get("cite_key")]
        return {
            "case_id": r.case_id,
            "citations_count": len(r.citations or []),
            "evidences_count": len(r.evidences or []),
            "has_celex_32025R1266": "CELEX:32025R1266" in labels or "CELEX:32025R1266" in answer,
            "has_ias36_label": any(lbl and "IAS36:" in lbl for lbl in labels),
            "answer_len": len(answer),
        }

    summary = {
        "run_id": run_id,
        "qdrant_url": qdrant_url,
        "collection_it": collection_it,
        "collection_en": collection_en,
        "embed_model": embed_model,
        "chat_model": chat_model,
        "cases_count": len(cases),
        "cases": [c.to_dict() for c in cases],
        "quick_checks": [assess_result(r) for r in results],
    }

    write_json(out_dir / "summary.json", summary)
    write_jsonl(out_dir / "results.jsonl", [r.to_dict() for r in results])

    for r in results:
        print(f"\n=== {r.case_id} ===")
        print("label:", r.label)
        print("lang:", r.lang)
        print("collection:", r.collection)
        print("citations_count:", len(r.citations or []))
        ans = (r.answer or "").replace("\n", " ")
        print("answer_preview:", ans[:1500])

    print(f"\nOUTPUT_DIR={out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
