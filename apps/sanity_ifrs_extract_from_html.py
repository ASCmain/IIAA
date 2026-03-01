#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Dict, List, Optional, Tuple

# --- repo-root bootstrap (MUST be before importing `src.*`) ---
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.telemetry import TelemetryRecorder
from src.parse.eurlex_html import TextBlock
from src.parse.ifrs_extract import extract_standard_paragraphs


DEFAULT_TARGETS = ["IAS 36", "IFRS 1", "IFRS 7", "IFRS 9", "IFRS 13"]


def utc_now_z() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Sanity: extract IFRS/IAS paragraphs from normalized EUR-Lex HTML blocks JSONL."
    )
    p.add_argument("--in", dest="inp", required=True, help="Input normalized blocks JSONL")
    p.add_argument("--out", required=True, help="Output report JSON")
    p.add_argument("--telemetry-out", default="telemetry", help="Telemetry base directory (default: telemetry)")
    p.add_argument("--targets", default=",".join(DEFAULT_TARGETS), help="Comma-separated targets")
    p.add_argument("--progress-every", type=int, default=2000, help="Print progress every N input lines (0=off)")
    p.add_argument("--max-lines", type=int, default=0, help="0=all; for quick debug")
    return p.parse_args()


def _map_kind(kind: str) -> str:
    k = (kind or "").strip().lower()
    if k in ("heading", "h1", "h2", "h3", "h4"):
        return "heading"
    return "p"


def load_blocks(path: Path, progress_every: int = 0, max_lines: int = 0) -> Tuple[List[TextBlock], Dict[str, object]]:
    meta: Dict[str, object] = {
        "doc_id": None,
        "language": None,
        "celex": None,
        "source_url": None,
        "lines_read": 0,
        "blocks_kept": 0,
        "kinds": {},
    }

    kinds = Counter()
    blocks: List[TextBlock] = []

    with path.open("r", encoding="utf-8") as f:
        for i, line in enumerate(f, start=1):
            if max_lines and i > max_lines:
                break
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)

            if meta["doc_id"] is None:
                meta["doc_id"] = row.get("doc_id")
                meta["language"] = row.get("language")
                meta["celex"] = row.get("celex")
                meta["source_url"] = row.get("source_url")

            txt = (row.get("text") or "").strip()
            if not txt:
                continue

            kind = _map_kind(row.get("kind") or "")
            kinds[kind] += 1
            blocks.append(TextBlock(kind=kind, text=txt, amendment_marker=None))

            if progress_every and (i % progress_every == 0):
                print(f"[{i}] lines scanned (blocks_kept={len(blocks)})")

            meta["lines_read"] = i

    meta["blocks_kept"] = len(blocks)
    meta["kinds"] = dict(kinds)
    return blocks, meta


def compute_stats(extracted: Dict[str, list], targets: List[str]) -> Dict[str, object]:
    std_counts = {k: len(v) for k, v in extracted.items()}
    all_paras = []
    dup_keys_by_std = {}
    key_shape_counts = Counter()

    for std, paras in extracted.items():
        keys = [p.key for p in paras]
        c = Counter(keys)
        dups = {k: n for k, n in c.items() if n > 1}
        if dups:
            dup_keys_by_std[std] = list(sorted(dups.items(), key=lambda x: (-x[1], x[0]))[:10])

        for p in paras:
            all_paras.append((std, p))
            k = p.key
            if k.startswith("B"):
                key_shape_counts["appendix_B"] += 1
            elif k.startswith("IE"):
                key_shape_counts["appendix_IE"] += 1
            elif k.startswith("BC"):
                key_shape_counts["appendix_BC"] += 1
            elif "." in k:
                key_shape_counts["dotted"] += 1
            else:
                key_shape_counts["integer"] += 1

    lengths = [len(p.text) for _, p in all_paras]
    sections = [p.section_path for _, p in all_paras if getattr(p, "section_path", None)]

    def pct(xs: List[int], q: float) -> Optional[int]:
        if not xs:
            return None
        xs2 = sorted(xs)
        idx = int(round((len(xs2) - 1) * q))
        return xs2[idx]

    target_counts = {t: std_counts.get(t, 0) for t in targets}

    return {
        "standards_total": len(std_counts),
        "paragraphs_total": len(all_paras),
        "targets": target_counts,
        "length_chars": {
            "min": min(lengths) if lengths else None,
            "avg": round(mean(lengths), 2) if lengths else None,
            "max": max(lengths) if lengths else None,
            "p50": pct(lengths, 0.50),
            "p90": pct(lengths, 0.90),
            "p99": pct(lengths, 0.99),
        },
        "section_paths_total": len(sections),
        "paragraph_key_shapes": dict(key_shape_counts),
        "duplicate_keys_sample": dup_keys_by_std,
    }


def main() -> int:
    args = parse_args()
    inp = Path(args.inp)
    outp = Path(args.out)
    outp.parent.mkdir(parents=True, exist_ok=True)

    targets = [t.strip() for t in args.targets.split(",") if t.strip()]

    rec = TelemetryRecorder(step="m2_sanity_ifrs_extract_from_html", out_dir=Path(args.telemetry_out))
    rec.start(inputs={"in": str(inp), "out": str(outp), "targets": targets}, extra={})

    try:
        with rec.span("load_blocks"):
            blocks, meta = load_blocks(inp, progress_every=args.progress_every, max_lines=args.max_lines)

        with rec.span("extract_standard_paragraphs", blocks=len(blocks)):
            extracted = extract_standard_paragraphs(blocks)

        with rec.span("compute_stats"):
            stats = compute_stats(extracted, targets)

        samples = {}
        for t in targets:
            paras = extracted.get(t, [])
            keys = [p.key for p in paras]
            section_paths = []
            for p in paras:
                sp = getattr(p, "section_path", None)
                if sp and sp not in section_paths:
                    section_paths.append(sp)
                if len(section_paths) >= 6:
                    break

            samples[t] = {
                "paragraphs": len(paras),
                "first_keys": keys[:8],
                "last_keys": keys[-8:] if keys else [],
                "example_section_paths": section_paths,
            }

        report = {
            "input": str(inp),
            "meta": meta,
            "stats": stats,
            "samples": samples,
            "generated_at_utc": utc_now_z(),
        }

        outp.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        rec.finalize(outputs={"report": str(outp), "paragraphs_total": stats["paragraphs_total"]})

        print(json.dumps(samples, indent=2, ensure_ascii=False))
        print(f"Wrote: {outp}")
        return 0

    except Exception as e:
        rec.event("error", error_type=type(e).__name__, message=str(e))
        rec.finalize(outputs={"error": str(e)})
        raise


if __name__ == "__main__":
    raise SystemExit(main())
