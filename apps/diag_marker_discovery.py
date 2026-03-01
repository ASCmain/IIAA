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


RX_IFRS_LINE = re.compile(r"\bINTERNATIONAL\s+FINANCIAL\s+REPORTING\s+STANDARD\b", re.I)
RX_IAS_LINE = re.compile(r"\bINTERNATIONAL\s+ACCOUNTING\s+STANDARD\b", re.I)
RX_IFRIC_LINE = re.compile(r"^IFRIC\s+\d+\b", re.I)
RX_SIC_LINE = re.compile(r"^SIC\s+\d+\b", re.I)

# Candidate marker tokens (various triangles/arrows, plus bare B patterns)
CANDIDATES = [
    "▼B", "►B", "▼", "►", "▾B", "▽B", "vB", "VB",
    "B", "B.", "(B)", "—B", "-B"
]


def utc_now_z() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def split_lines(text: str) -> List[str]:
    return [normalize_text(x) for x in (text or "").splitlines() if normalize_text(x)]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--progress-every", type=int, default=250)
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

    step = "m2_diag_marker_discovery"
    rec = TelemetryRecorder(step=step)
    rec.start(inputs={"in": str(inp), "out": str(outp)}, extra={"pages": limit})

    started = time.time()
    last_heartbeat = started

    counts = Counter()
    predecessor_counts = Counter()
    examples: List[Dict[str, Any]] = []

    with rec.span("scan", pages=limit):
        for i in range(limit):
            row = pages[i]
            page_no = int(row.get("page", i + 1))
            text = row.get("text_clean", "") or ""
            lines = split_lines(text)

            # Count candidate symbols in the whole page text
            joined = "\n".join(lines)
            for c in CANDIDATES:
                if c != "B":
                    if c in joined:
                        counts[f"contains:{c}"] += 1

            # Look for standard headings and capture preceding line
            for idx, ln in enumerate(lines):
                if RX_IFRS_LINE.search(ln) or RX_IAS_LINE.search(ln) or RX_IFRIC_LINE.match(ln) or RX_SIC_LINE.match(ln):
                    counts["pages_with_standard_heading_line"] += 1
                    prev = lines[idx - 1] if idx - 1 >= 0 else ""
                    prev2 = lines[idx - 2] if idx - 2 >= 0 else ""
                    predecessor_counts[f"prev:{prev}"] += 1
                    predecessor_counts[f"prev2:{prev2}"] += 1
                    if len(examples) < 30:
                        examples.append(
                            {
                                "page": page_no,
                                "prev2": prev2,
                                "prev": prev,
                                "heading": ln,
                                "next": lines[idx + 1] if idx + 1 < len(lines) else "",
                            }
                        )
                    break  # one example per page is enough

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
        "counts": dict(counts),
        "contains_candidates_top": [(k, v) for k, v in counts.most_common(30) if k.startswith("contains:")],
        "predecessor_top": predecessor_counts.most_common(30),
        "examples_first_30": examples,
    }
    outp.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    rec.finalize(outputs={"out": str(outp), "pages_with_heading": counts["pages_with_standard_heading_line"]})
    print(json.dumps({"out": str(outp), "pages_with_heading": counts["pages_with_standard_heading_line"]}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())