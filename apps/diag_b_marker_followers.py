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
from typing import List, Dict, Any

from src.telemetry import TelemetryRecorder
from src.text_normalize import normalize_text


RX_IAS_LINE = re.compile(r"\bINTERNATIONAL\s+ACCOUNTING\s+STANDARD\b", re.I)
RX_IFRS_LINE = re.compile(r"\bINTERNATIONAL\s+FINANCIAL\s+REPORTING\s+STANDARD\b", re.I)
RX_STD_NUM = re.compile(r"\b(STANDARD)\s+(\d{1,3})\b", re.I)
RX_STD_SHORT = re.compile(r"\b(IAS|IFRS|IFRIC|SIC)\s*(\d{1,3})\b", re.I)


def utc_now_z() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def split_lines(text: str) -> List[str]:
    return [normalize_text(x) for x in (text or "").splitlines() if normalize_text(x)]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True, help="debug_dump/pdf_clean/<...>.clean.jsonl")
    ap.add_argument("--out", required=True, help="debug_dump/.../diag_b_marker.json")
    ap.add_argument("--progress-every", type=int, default=200)
    ap.add_argument("--heartbeat-seconds", type=int, default=10)
    ap.add_argument("--max-pages", type=int, default=0)
    args = ap.parse_args()

    inp = Path(args.inp)
    outp = Path(args.out)
    outp.parent.mkdir(parents=True, exist_ok=True)

    pages = []
    with inp.open("r", encoding="utf-8") as f:
        for line in f:
            pages.append(json.loads(line))

    n_pages = len(pages)
    limit = args.max_pages if args.max_pages else n_pages
    limit = min(limit, n_pages)

    step = "m2_diag_b_marker_followers"
    rec = TelemetryRecorder(step=step)
    rec.start(inputs={"in": str(inp), "out": str(outp)}, extra={"pages": limit})

    started = time.time()
    last_heartbeat = started

    stats = Counter()
    follower_patterns = Counter()
    examples: List[Dict[str, Any]] = []

    with rec.span("scan", pages=limit):
        for i in range(limit):
            row = pages[i]
            page_no = int(row.get("page", i + 1))
            text = row.get("text_clean", "") or ""
            lines = split_lines(text)

            # find first occurrence of ▼B anywhere
            b_idx = None
            for idx, ln in enumerate(lines):
                if "▼B" in ln:
                    b_idx = idx
                    break

            if b_idx is None:
                continue

            stats["pages_with_B"] += 1

            window = lines[b_idx : min(b_idx + 12, len(lines))]
            win_text = "\n".join(window)

            # classify what follows
            has_ifrs = bool(RX_IFRS_LINE.search(win_text))
            has_ias = bool(RX_IAS_LINE.search(win_text))
            has_std_num = bool(RX_STD_NUM.search(win_text))
            has_short = bool(RX_STD_SHORT.search(win_text))

            key = f"ifrs={int(has_ifrs)}_ias={int(has_ias)}_stdnum={int(has_std_num)}_short={int(has_short)}"
            follower_patterns[key] += 1

            # store a few examples for the most common cases
            if len(examples) < 30:
                examples.append(
                    {
                        "page": page_no,
                        "b_line": lines[b_idx],
                        "window": window,
                        "pattern_key": key,
                    }
                )

            if args.progress_every > 0 and (i + 1) % args.progress_every == 0:
                elapsed = time.time() - started
                print(f"[{i+1:>4}/{limit}] scanned (elapsed {elapsed:.1f}s)")

            now = time.time()
            if now - last_heartbeat >= args.heartbeat_seconds:
                print(f"[{i+1:>4}/{limit}] heartbeat")
                last_heartbeat = now

    report = {
        "input": str(inp),
        "pages_scanned": limit,
        "generated_at_utc": utc_now_z(),
        "counts": dict(stats),
        "follower_patterns_top": follower_patterns.most_common(20),
        "examples_first_30": examples,
    }
    outp.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    rec.finalize(outputs={"out": str(outp), "pages_with_B": stats["pages_with_B"]})
    print(json.dumps({"out": str(outp), "pages_with_B": stats["pages_with_B"]}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())