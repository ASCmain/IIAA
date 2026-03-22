from __future__ import annotations

import json
import os
import sys
import subprocess
from datetime import datetime, UTC
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from qdrant_client import QdrantClient

from src.benchmark import BenchmarkCase, load_benchmark_cases, run_benchmark_cases, write_json, write_jsonl
from src.telemetry import TelemetryRecorder


def _git_commit() -> str:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=REPO_ROOT,
            text=True,
        ).strip()
        return out
    except Exception:
        return ""


def _print_progress(current: int, total: int, label: str) -> None:
    total = max(int(total), 1)
    current = max(0, min(int(current), total))
    width = 28
    filled = int(width * current / total)
    bar = "#" * filled + "-" * (width - filled)
    print(f"[{bar}] {current}/{total} {label}")



def _append_jsonl(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _make_progress_cb(telemetry):
    def _cb(info):
        event = info.get("event") or ""
        if event == "case_start":
            telemetry.event(
                "case_start",
                case_id=info.get("case_id"),
                idx=info.get("idx"),
                total=info.get("total"),
                label=info.get("label"),
                lang_mode=info.get("lang_mode"),
                top_k=info.get("top_k"),
            )
            _print_progress(
                int(info.get("idx") or 0) - 1,
                int(info.get("total") or 1),
                f"avvio case: {info.get('case_id')}",
            )
        elif event == "case_done":
            telemetry.event(
                "case_done",
                case_id=info.get("case_id"),
                idx=info.get("idx"),
                total=info.get("total"),
                citations_count=info.get("citations_count"),
                evidences_count=info.get("evidences_count"),
                classifier_items_count=info.get("classifier_items_count"),
                used_citations_count=info.get("used_citations_count"),
                citation_candidates_count=info.get("citation_candidates_count"),
                answer_len=info.get("answer_len"),
                case_total_ms=info.get("case_total_ms"),
            )
            _print_progress(
                int(info.get("idx") or 0),
                int(info.get("total") or 1),
                f"case completato: {info.get('case_id')} ({info.get('case_total_ms')} ms)",
            )
        elif event == "case_error":
            telemetry.event(
                "case_error",
                case_id=info.get("case_id"),
                idx=info.get("idx"),
                total=info.get("total"),
                error=info.get("error"),
                case_total_ms=info.get("case_total_ms"),
            )
            _print_progress(
                int(info.get("idx") or 0),
                int(info.get("total") or 1),
                f"case in errore: {info.get('case_id')} ({info.get('case_total_ms')} ms)",
            )
    return _cb


def main() -> int:
    qdrant_url = os.environ["QDRANT_URL"]
    ollama_base = os.environ["OLLAMA_BASE_URL"]
    collection_it = os.environ["QDRANT_COLLECTION_IT"]
    collection_en = os.environ["QDRANT_COLLECTION_EN"]

    embed_model = os.environ.get("BENCHMARK_EMBED_MODEL", "mxbai-embed-large:latest")
    chat_model = os.environ.get("BENCHMARK_CHAT_MODEL", "mistral:latest")
    classifier_mode = os.environ.get("EVIDENCE_CLASSIFIER_MODE", "off")
    classifier_model = os.environ.get("EVIDENCE_CLASSIFIER_MODEL", "")
    selected_case_ids_raw = os.environ.get("BENCHMARK_CASE_IDS", "").strip()
    selected_case_ids = {
        x.strip() for x in selected_case_ids_raw.split(",") if x.strip()
    } if selected_case_ids_raw else set()
    fail_fast = (os.environ.get("BENCHMARK_FAIL_FAST", "false").strip().lower() == "true")

    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out_dir = Path("debug_dump/benchmark_runs") / f"smoke_{run_id}"
    out_dir.mkdir(parents=True, exist_ok=True)

    cases_path = os.environ.get("BENCHMARK_CASES_FILE", "config/benchmark_cases_core.json")
    cases = load_benchmark_cases(cases_path)

    telemetry = TelemetryRecorder(step="benchmark_smoke")
    telemetry.start(
        inputs={
            "run_id": run_id,
            "cases_count": len(cases),
            "case_ids": [c.case_id for c in cases],
            "qdrant_url": qdrant_url,
            "collection_it": collection_it,
            "collection_en": collection_en,
            "embed_model": embed_model,
            "chat_model": chat_model,
            "classifier_mode": classifier_mode,
            "classifier_model": classifier_model,
            "selected_case_ids": sorted(selected_case_ids),
            "fail_fast": fail_fast,
        },
        extra={
            "app": "apps/run_benchmark_smoke.py",
            "out_dir": str(out_dir),
        },
    )

    total_phases = 4
    current_phase = 0

    telemetry.event("phase_start", phase="bootstrap")
    with telemetry.span("bootstrap"):
        client = QdrantClient(url=qdrant_url)
    current_phase += 1
    _print_progress(current_phase, total_phases, "bootstrap completato")
    telemetry.event("phase_done", phase="bootstrap")

    progress_cb = _make_progress_cb(telemetry)

    results_path_live = out_dir / "results.jsonl"

    telemetry.event("phase_start", phase="run_benchmark_cases")
    with telemetry.span("run_benchmark_cases", cases_count=len(cases)):
        results = run_benchmark_cases(
            cases=cases,
            qdrant_client=client,
            collection_it=collection_it,
            collection_en=collection_en,
            ollama_base_url=ollama_base,
            embed_model=embed_model,
            chat_model=chat_model,
            progress_cb=progress_cb,
            selected_case_ids=selected_case_ids,
            fail_fast=fail_fast,
        )

        for r in results:
            _append_jsonl(results_path_live, r.to_dict())
    current_phase += 1
    _print_progress(current_phase, total_phases, "benchmark completato")
    telemetry.event("phase_done", phase="run_benchmark_cases", results_count=len(results))

    def assess_result(r):
        answer = r.answer or ""
        labels = [c.get("cite_key") for c in (r.citations or []) if c.get("cite_key")]
        classifier_items = getattr(r, "classifier_items", []) or []
        label_counts = {}
        for item in classifier_items:
            label = item.get("label") or "unknown"
            label_counts[label] = label_counts.get(label, 0) + 1

        return {
            "case_id": r.case_id,
            "question_type": (r.query_plan or {}).get("question_type"),
            "source_preference": (r.query_plan or {}).get("source_preference"),
            "needs_numeric_reasoning": (r.query_plan or {}).get("needs_numeric_reasoning"),
            "target_standards": (r.query_plan or {}).get("target_standards"),
            "retrieval_raw_count": getattr(r, "retrieval_raw_count", 0),
            "retrieval_above_initial_threshold_count": getattr(r, "retrieval_above_initial_threshold_count", 0),
            "analysis_pool_count": getattr(r, "analysis_pool_count", 0),
            "analysis_pool_target": getattr(r, "analysis_pool_target", 0),
            "min_candidate_floor": getattr(r, "min_candidate_floor", 0),
            "threshold_initial": getattr(r, "threshold_initial", None),
            "threshold_effective": getattr(r, "threshold_effective", None),
            "coverage_warning_low_candidate_count": getattr(r, "coverage_warning_low_candidate_count", False),
            "max_core": getattr(r, "max_core", 0),
            "max_context": getattr(r, "max_context", 0),
            "policy_trace": getattr(r, "policy_trace", {}),
            "core_evidences_count": getattr(r, "core_evidences_count", (r.query_plan or {}).get("core_evidences_count")),
            "context_evidences_count": getattr(r, "context_evidences_count", (r.query_plan or {}).get("context_evidences_count")),
            "classifier_mode": getattr(r, "classifier_mode", ""),
            "classifier_model": getattr(r, "classifier_model", ""),
            "classifier_items_count": getattr(r, "classifier_items_count", 0),
            "classifier_label_counts": label_counts,
            "used_citations_count": getattr(r, "used_citations_count", 0),
            "citation_candidates_count": getattr(r, "citation_candidates_count", 0),
            "telemetry_timing_ms": getattr(r, "telemetry_timing_ms", {}),
            "citations_count": len(r.citations or []),
            "evidences_count": len(r.evidences or []),
            "has_celex_32025R1266": "CELEX:32025R1266" in labels or "CELEX:32025R1266" in answer,
            "has_ias36_label": any(lbl and "IAS36:" in lbl for lbl in labels),
            "answer_len": len(answer),
        }

    telemetry.event("phase_start", phase="build_summary")
    with telemetry.span("build_summary"):
        quick_checks = [assess_result(r) for r in results]
        summary = {
            "run_id": run_id,
            "qdrant_url": qdrant_url,
            "collection_it": collection_it,
            "collection_en": collection_en,
            "embed_model": embed_model,
            "chat_model": chat_model,
            "classifier_mode": classifier_mode,
            "classifier_model": classifier_model,
            "cases_count": len(cases),
            "selected_cases_count": len(results),
            "cases": [c.to_dict() for c in cases],
            "quick_checks": quick_checks,
        }
    current_phase += 1
    _print_progress(current_phase, total_phases, "summary costruito")
    telemetry.event("phase_done", phase="build_summary", quick_checks_count=len(quick_checks))

    telemetry.event("phase_start", phase="write_outputs")
    with telemetry.span("write_outputs"):
        write_json(out_dir / "summary.json", summary)
    current_phase += 1
    _print_progress(current_phase, total_phases, "file scritti")
    telemetry.event(
        "phase_done",
        phase="write_outputs",
        summary_path=str(out_dir / "summary.json"),
        results_path=str(out_dir / "results.jsonl"),
    )

    for idx, r in enumerate(results, start=1):
        telemetry.event(
            "case_result",
            case_id=r.case_id,
            idx=idx,
            total=len(results),
            citations_count=len(r.citations or []),
            evidences_count=len(r.evidences or []),
            answer_len=len(r.answer or ""),
            classifier_items_count=getattr(r, "classifier_items_count", 0),
            used_citations_count=getattr(r, "used_citations_count", 0),
            citation_candidates_count=getattr(r, "citation_candidates_count", 0),
        )

        print(f"\n=== {r.case_id} ===")
        print("label:", r.label)
        print("status:", getattr(r, "status", "ok"))
        if getattr(r, "error", ""):
            print("error:", r.error)
        print("lang:", r.lang)
        print("collection:", r.collection)
        print("citations_count:", len(r.citations or []))
        ans = (r.answer or "").replace("\n", " ")
        print("answer_preview:", ans[:1500])
        _print_progress(idx, len(results), f"risultato stampato: {r.case_id}")

    telemetry_path = telemetry.finalize(
        outputs={
            "run_id": run_id,
            "out_dir": str(out_dir),
            "summary_path": str(out_dir / "summary.json"),
            "results_path": str(out_dir / "results.jsonl"),
            "cases_count": len(cases),
        },
        extra={
            "quick_checks_count": len(quick_checks),
        },
        git_commit=_git_commit(),
    )

    if telemetry_path is not None:
        print(f"TELEMETRY_PATH={telemetry_path}")

    print(f"\nOUTPUT_DIR={out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
