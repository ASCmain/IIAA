#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import argparse
import json
import re
import time
from collections import Counter
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from src.telemetry import TelemetryRecorder
from src.text_normalize import normalize_text


# Strong headings (avoid citations inside paragraphs by anchoring at line start)
RX_IAS_EN = re.compile(r"^INTERNATIONAL\s+ACCOUNTING\s+STANDARD\s+(\d+)\b", re.I)
RX_IAS_IT = re.compile(r"^PRINCIPIO\s+CONTABILE\s+INTERNAZIONALE\s+IAS\s+(\d+)\b", re.I)
RX_IFRS_EN = re.compile(r"^INTERNATIONAL\s+FINANCIAL\s+REPORTING\s+STANDARD\s+(\d+)\b", re.I)
RX_IFRS_IT = re.compile(r"^INTERNATIONAL\s+FINANCIAL\s+REPORTING\s+STANDARD\s+(\d+)\b", re.I)  # often not translated
RX_IFRIC_EN = re.compile(r"^IFRIC\s+(\d+)\b", re.I)
RX_IFRIC_IT = re.compile(r"^INTERPRETAZIONE\s+IFRIC\s+(\d+)\b", re.I)
RX_SIC_EN = re.compile(r"^SIC\s+(\d+)\b", re.I)
RX_SIC_IT = re.compile(r"^INTERPRETAZIONE\s+SIC\s+(\d+)\b", re.I)

# Short-form heading lines sometimes appear (e.g., "IAS 36", "IFRS 9") — allow only in ANNEX zone.
RX_STD_SHORT = re.compile(r"^(IAS|IFRS|IFRIC|SIC)\s+(\d+)\b", re.I)

# Annex anchors
RX_ANNEX_IT = re.compile(r"^ALLEGATO\b", re.I)
RX_ANNEX_EN = re.compile(r"^ANNEX\b", re.I)
RX_INTL_STDS_IT = re.compile(r"^PRINCIPI\s+CONTABILI\s+INTERNAZIONALI\b", re.I)
RX_INTL_STDS_EN = re.compile(r"^INTERNATIONAL\s+(ACCOUNTING\s+STANDARDS|FINANCIAL\s+REPORTING\s+STANDARDS)\b", re.I)


def utc_now_z() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def pct(values: List[int], p: float) -> int:
    if not values:
        return 0
    values = sorted(values)
    k = int(round((len(values) - 1) * p))
    return values[max(0, min(k, len(values) - 1))]


def iter_pages(clean_jsonl: Path):
    with clean_jsonl.open("r", encoding="utf-8") as f:
        for line in f:
            yield json.loads(line)


def split_lines(text: str) -> List[str]:
    return [normalize_text(x) for x in (text or "").splitlines() if normalize_text(x)]


def detect_strong_standard_heading(line: str, lang_hint: str) -> Optional[str]:
    """
    Return standard_id like 'IAS 36', 'IFRS 9', 'IFRIC 23', 'SIC 12' only for strong headings.
    """
    if lang_hint.upper() == "IT":
        m = RX_IAS_IT.match(line)
        if m: return f"IAS {m.group(1)}"
        m = RX_IFRIC_IT.match(line)
        if m: return f"IFRIC {m.group(1)}"
        m = RX_SIC_IT.match(line)
        if m: return f"SIC {m.group(1)}"
        # IFRS headings often appear in EN even in IT documents
        m = RX_IFRS_IT.match(line)
        if m: return f"IFRS {m.group(1)}"
        return None

    # EN
    m = RX_IAS_EN.match(line)
    if m: return f"IAS {m.group(1)}"
    m = RX_IFRS_EN.match(line)
    if m: return f"IFRS {m.group(1)}"
    m = RX_IFRIC_EN.match(line)
    if m: return f"IFRIC {m.group(1)}"
    m = RX_SIC_EN.match(line)
    if m: return f"SIC {m.group(1)}"
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True, help="Input clean.jsonl")
    ap.add_argument("--out", required=True, help="Output segments.jsonl")
    ap.add_argument("--stats", required=True, help="Output stats.json")
    ap.add_argument("--lang", required=True, choices=["IT", "EN"])
    ap.add_argument("--progress-every", type=int, default=50)
    ap.add_argument("--heartbeat-seconds", type=int, default=10)
    ap.add_argument("--max-pages", type=int, default=0, help="0=all")
    args = ap.parse_args()

    inp = Path(args.inp)
    outp = Path(args.out)
    statsp = Path(args.stats)
    outp.parent.mkdir(parents=True, exist_ok=True)
    statsp.parent.mkdir(parents=True, exist_ok=True)

    pages = list(iter_pages(inp))
    n_pages = len(pages)
    limit = args.max_pages if args.max_pages else n_pages
    limit = min(limit, n_pages)

    step = "m2_pdf_segment_consolidated"
    rec = TelemetryRecorder(step=step)
    rec.start(
        inputs={"in": str(inp), "out": str(outp), "stats": str(statsp), "lang": args.lang},
        extra={"pages": limit, "progress_every": args.progress_every, "heartbeat_seconds": args.heartbeat_seconds},
    )

    # State
    in_annex = False
    current_segment_type = "regulation"  # until annex
    current_standard: Optional[str] = None
    seg_start_page = 1
    seg_text_parts: List[str] = []

    # Stats
    seg_counts = Counter()
    heading_hits = Counter()
    para_lens = []  # crude proxy: line lengths; refined paragraph stats will come in next script

    started = time.time()
    last_heartbeat = started

    def flush_segment(end_page: int):
        nonlocal seg_start_page, seg_text_parts, current_segment_type, current_standard
        text = "\n".join([t for t in seg_text_parts if t]).strip()
        if not text:
            seg_text_parts = []
            seg_start_page = end_page + 1
            return

        segment_id = current_segment_type if current_standard is None else f"standard::{current_standard}"
        row = {
            "segment_id": segment_id,
            "segment_type": current_segment_type,
            "standard_id": current_standard,
            "page_start": seg_start_page,
            "page_end": end_page,
            "lang": args.lang,
            "text": text,
            "generated_at_utc": utc_now_z(),
        }
        with outp.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

        seg_counts[segment_id] += 1
        seg_text_parts = []
        seg_start_page = end_page + 1

    # Ensure out file empty
    if outp.exists():
        outp.unlink()

    with rec.span("segment", pages=limit):
        for i in range(limit):
            page_no = pages[i].get("page", i + 1)
            text = pages[i].get("text_clean", "")
            lines = split_lines(text)

            # quick stats proxy
            for ln in lines[:200]:
                para_lens.append(len(ln))

            # Annex detection
            if not in_annex:
                for ln in lines[:40]:
                    if (args.lang == "IT" and RX_ANNEX_IT.match(ln)) or (args.lang == "EN" and RX_ANNEX_EN.match(ln)):
                        in_annex = True
                        # close regulation segment up to previous page
                        flush_segment(page_no - 1)
                        current_segment_type = "annex"
                        current_standard = None
                        seg_start_page = page_no
                        break

            # Standard detection (only when in annex zone)
            if in_annex:
                std_found = None
                for ln in lines[:80]:
                    std_found = detect_strong_standard_heading(ln, args.lang)
                    if std_found:
                        break
                # allow short-form only if line is very "heading-like" and we are in annex
                if not std_found:
                    for ln in lines[:50]:
                        m = RX_STD_SHORT.match(ln)
                        if m and len(ln) <= 18:
                            std_found = f"{m.group(1).upper()} {m.group(2)}"
                            break

                if std_found and std_found != current_standard:
                    heading_hits[std_found] += 1
                    # flush previous segment up to prev page
                    flush_segment(page_no - 1)
                    current_segment_type = "standard"
                    current_standard = std_found
                    seg_start_page = page_no

            # accumulate current page text
            if text:
                seg_text_parts.append(text)

            # progress
            if args.progress_every > 0 and (i + 1) % args.progress_every == 0:
                elapsed = time.time() - started
                print(f"[{i+1:>4}/{limit}] segmented pages (elapsed {elapsed:.1f}s)")

            now = time.time()
            if now - last_heartbeat >= args.heartbeat_seconds:
                print(f"[{i+1:>4}/{limit}] heartbeat")
                last_heartbeat = now

    # flush tail
    flush_segment(pages[limit - 1].get("page", limit))

    stats = {
        "input": str(inp),
        "output": str(outp),
        "lang": args.lang,
        "pages": limit,
        "segments_written": sum(seg_counts.values()),
        "segment_ids": seg_counts.most_common(50),
        "standard_heading_hits_top": heading_hits.most_common(50),
        "line_len_min": min(para_lens) if para_lens else 0,
        "line_len_mean": (sum(para_lens) / len(para_lens)) if para_lens else 0,
        "line_len_p95": pct(para_lens, 0.95),
        "line_len_max": max(para_lens) if para_lens else 0,
        "generated_at_utc": utc_now_z(),
    }
    statsp.write_text(json.dumps(stats, indent=2, ensure_ascii=False), encoding="utf-8")

    rec.finalize(outputs={"segments": str(outp), "stats": str(statsp), "segments_written": sum(seg_counts.values())})
    print(json.dumps({"segments": str(outp), "stats": str(statsp)}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())