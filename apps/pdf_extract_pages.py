#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import argparse
import hashlib
import json
import time
from datetime import datetime, timezone
from typing import Dict, List

import pdfplumber

from src.telemetry import TelemetryRecorder


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def utc_now_z() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def extract_page_text(page, two_col: bool) -> str:
    if not two_col:
        return (page.extract_text() or "").strip()

    w = float(page.width)
    h = float(page.height)
    mid = w / 2.0
    left = page.within_bbox((0, 0, mid, h)).extract_text() or ""
    right = page.within_bbox((mid, 0, w, h)).extract_text() or ""
    return (left.strip() + "\n" + right.strip()).strip()


def pct(values: List[int], p: float) -> int:
    if not values:
        return 0
    values = sorted(values)
    k = int(round((len(values) - 1) * p))
    return values[max(0, min(k, len(values) - 1))]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--stats", default="", help="Optional stats JSON output (default: <out>.stats.json)")
    ap.add_argument("--two-col", action="store_true")
    ap.add_argument("--max-pages", type=int, default=0, help="0=all")
    ap.add_argument("--progress-every", type=int, default=25)
    ap.add_argument("--heartbeat-seconds", type=int, default=10)
    args = ap.parse_args()

    pdf_path = Path(args.pdf)
    outp = Path(args.out)
    outp.parent.mkdir(parents=True, exist_ok=True)

    statsp = Path(args.stats) if args.stats else Path(str(outp) + ".stats.json")
    statsp.parent.mkdir(parents=True, exist_ok=True)

    step = "m2_pdf_extract_pages"
    rec = TelemetryRecorder(step=step)
    rec.start(
        inputs={
            "pdf": str(pdf_path),
            "out": str(outp),
            "stats": str(statsp),
            "two_col": args.two_col,
            "max_pages": args.max_pages,
        },
        extra={"progress_every": args.progress_every, "heartbeat_seconds": args.heartbeat_seconds},
    )

    file_sha = sha256_file(pdf_path)

    lengths: List[int] = []
    empty_pages = 0
    started = time.time()
    last_heartbeat = started

    with pdfplumber.open(str(pdf_path)) as pdf:
        n_pages = len(pdf.pages)
        limit = args.max_pages if args.max_pages else n_pages
        limit = min(limit, n_pages)

        with rec.span("extract", pages=limit):
            with outp.open("w", encoding="utf-8") as f:
                for i in range(limit):
                    page = pdf.pages[i]
                    text = extract_page_text(page, two_col=args.two_col)
                    L = len(text)
                    lengths.append(L)
                    if L == 0:
                        empty_pages += 1

                    row = {
                        "source_pdf": str(pdf_path),
                        "source_sha256": file_sha,
                        "page": i + 1,
                        "layout_hint": "two_col" if args.two_col else "one_col",
                        "text_raw": text,
                        "extracted_at_utc": utc_now_z(),
                    }
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")

                    # progress
                    if args.progress_every > 0 and (i + 1) % args.progress_every == 0:
                        elapsed = time.time() - started
                        print(f"[{i+1:>4}/{limit}] extracted pages (elapsed {elapsed:.1f}s)")

                    # heartbeat
                    now = time.time()
                    if now - last_heartbeat >= args.heartbeat_seconds:
                        print(f"[{i+1:>4}/{limit}] heartbeat")
                        last_heartbeat = now

    stats: Dict = {
        "pdf": str(pdf_path),
        "sha256": file_sha,
        "out": str(outp),
        "pages_written": limit,
        "empty_pages": empty_pages,
        "len_chars_min": min(lengths) if lengths else 0,
        "len_chars_mean": (sum(lengths) / len(lengths)) if lengths else 0,
        "len_chars_p95": pct(lengths, 0.95),
        "len_chars_max": max(lengths) if lengths else 0,
        "generated_at_utc": utc_now_z(),
    }
    statsp.write_text(json.dumps(stats, indent=2, ensure_ascii=False), encoding="utf-8")

    rec.finalize(outputs={"out": str(outp), "stats": str(statsp), "pages_written": limit, "empty_pages": empty_pages})
    print(json.dumps({"out": str(outp), "stats": str(statsp), "pages_written": limit}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
