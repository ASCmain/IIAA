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
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Dict, List, Tuple

from src.telemetry import TelemetryRecorder
from src.text_normalize import normalize_text


RX_MARKER = re.compile(r"(►\s*[A-Z]\d+|►\s*B|▼\s*B|◄|►)")
RX_WS = re.compile(r"\s+")


def utc_now_z() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def split_lines(text: str) -> List[str]:
    return [normalize_text(x) for x in (text or "").splitlines() if normalize_text(x)]


def extract_markers(lines: List[str]) -> Tuple[List[str], List[str]]:
    markers: List[str] = []
    cleaned: List[str] = []
    for ln in lines:
        ms = RX_MARKER.findall(ln)
        if ms:
            markers.extend([m.replace(" ", "") for m in ms])
            ln2 = RX_MARKER.sub("", ln).strip()
            if ln2:
                cleaned.append(ln2)
        else:
            cleaned.append(ln)
    return markers, cleaned


def build_line_blacklist(pages: List[dict], sample_pages: int, min_ratio: float) -> Dict[str, float]:
    """
    Count lines across sample_pages and return lines that appear in >= min_ratio of pages.
    """
    n = min(sample_pages, len(pages))
    per_page_sets: List[set] = []
    for i in range(n):
        lines = split_lines(pages[i].get("text_raw", ""))
        per_page_sets.append(set(lines))

    freq = Counter()
    for s in per_page_sets:
        for ln in s:
            freq[ln] += 1

    blacklist: Dict[str, float] = {}
    for ln, c in freq.items():
        ratio = c / max(1, n)
        if ratio >= min_ratio and len(ln) >= 6:
            blacklist[ln] = ratio
    return blacklist


def join_lines(lines: List[str]) -> str:
    return "\n".join(lines).strip()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True, help="Input pages.jsonl")
    ap.add_argument("--out", required=True, help="Output clean.jsonl")
    ap.add_argument("--report", required=True, help="Output report.json")
    ap.add_argument("--sample-pages", type=int, default=50)
    ap.add_argument("--min-ratio", type=float, default=0.6)
    args = ap.parse_args()

    inp = Path(args.inp)
    outp = Path(args.out)
    rep = Path(args.report)

    pages: List[dict] = []
    with inp.open("r", encoding="utf-8") as f:
        for line in f:
            pages.append(json.loads(line))

    step = "m2_pdf_clean_pages"
    rec = TelemetryRecorder(step=step)
    rec.start(
        inputs={"in": str(inp), "out": str(outp), "report": str(rep)},
        extra={"sample_pages": args.sample_pages, "min_ratio": args.min_ratio, "n_pages": len(pages)},
    )

    blacklist = build_line_blacklist(pages, args.sample_pages, args.min_ratio)

    dropped_counts = Counter()
    marker_counts = Counter()

    outp.parent.mkdir(parents=True, exist_ok=True)
    rep.parent.mkdir(parents=True, exist_ok=True)

    with rec.span("clean", n_pages=len(pages), blacklist=len(blacklist)):
        with outp.open("w", encoding="utf-8") as out:
            for row in pages:
                raw = row.get("text_raw", "")
                lines = split_lines(raw)

                # drop repeated header/footer lines
                kept = []
                for ln in lines:
                    if ln in blacklist:
                        dropped_counts[ln] += 1
                        continue
                    kept.append(ln)

                markers, kept2 = extract_markers(kept)
                for m in markers:
                    marker_counts[m] += 1

                cleaned_text = join_lines(kept2)

                out_row = {
                    "source_pdf": row.get("source_pdf"),
                    "source_sha256": row.get("source_sha256"),
                    "page": row.get("page"),
                    "layout_hint": row.get("layout_hint"),
                    "markers": markers,
                    "text_clean": cleaned_text,
                    "cleaned_at_utc": utc_now_z(),
                }
                out.write(json.dumps(out_row, ensure_ascii=False) + "\n")

    report = {
        "input": str(inp),
        "output": str(outp),
        "generated_at_utc": utc_now_z(),
        "sample_pages": args.sample_pages,
        "min_ratio": args.min_ratio,
        "blacklist_count": len(blacklist),
        "blacklist_top": sorted(blacklist.items(), key=lambda x: (-x[1], x[0]))[:50],
        "markers_top": marker_counts.most_common(50),
    }
    rep.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    rec.finalize(outputs={"out": str(outp), "report": str(rep), "blacklist_count": len(blacklist)})
    print(json.dumps({"out": str(outp), "report": str(rep), "blacklist_count": len(blacklist)}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())