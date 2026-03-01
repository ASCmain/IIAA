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
from typing import List, Optional

from src.telemetry import TelemetryRecorder
from src.text_normalize import normalize_text


# strong headings (single-line)
RX_IAS_EN = re.compile(r"^INTERNATIONAL\s+ACCOUNTING\s+STANDARD\s+(\d+)\b", re.I)
RX_IFRS_EN = re.compile(r"^INTERNATIONAL\s+FINANCIAL\s+REPORTING\s+STANDARD\s+(\d+)\b", re.I)

RX_IAS_IT_LONG = re.compile(r"^PRINCIPIO\s+CONTABILE\s+INTERNAZIONALE\s+IAS\s+(\d+)\b", re.I)
RX_IAS_IT_ALT = re.compile(r"^PRINCIPIO\s+CONTABILE\s+INTERNAZIONALE\s+(\d+)\b", re.I)

RX_IFRIC_EN = re.compile(r"^IFRIC\s+(\d+)\b", re.I)
RX_SIC_EN = re.compile(r"^SIC\s+(\d+)\b", re.I)
RX_IFRIC_IT = re.compile(r"^INTERPRETAZIONE\s+IFRIC\s+(\d+)\b", re.I)
RX_SIC_IT = re.compile(r"^INTERPRETAZIONE\s+SIC\s+(\d+)\b", re.I)

# short forms (single-line), also allow no-space IAS36 / IFRS9
RX_SHORT = re.compile(r"^(IAS|IFRS|IFRIC|SIC)\s*\.?\s*(\d+)\b(.*)$", re.I)
RX_NOSPACE = re.compile(r"^(IAS|IFRS|IFRIC|SIC)(\d+)\b(.*)$", re.I)

# multi-line building blocks
RX_CODE_ONLY = re.compile(r"^(IAS|IFRS|IFRIC|SIC)\b$", re.I)
RX_NUM_ONLY = re.compile(r"^(\d{1,3})\b$", re.I)
RX_HAS_LETTERS = re.compile(r"[A-Za-zÀ-ÿ]")

# annex anchors
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


def detect_strong_heading_single(line: str, lang: str) -> Optional[str]:
    if lang == "IT":
        m = RX_IAS_IT_LONG.match(line)
        if m: return f"IAS {m.group(1)}"
        m = RX_IAS_IT_ALT.match(line)
        if m: return f"IAS {m.group(1)}"
        m = RX_IFRIC_IT.match(line)
        if m: return f"IFRIC {m.group(1)}"
        m = RX_SIC_IT.match(line)
        if m: return f"SIC {m.group(1)}"
        m = RX_IFRS_EN.match(line)  # often in EN in IT pdf
        if m: return f"IFRS {m.group(1)}"
        m = RX_IAS_EN.match(line)
        if m: return f"IAS {m.group(1)}"
        return None

    m = RX_IAS_EN.match(line)
    if m: return f"IAS {m.group(1)}"
    m = RX_IFRS_EN.match(line)
    if m: return f"IFRS {m.group(1)}"
    m = RX_IFRIC_EN.match(line)
    if m: return f"IFRIC {m.group(1)}"
    m = RX_SIC_EN.match(line)
    if m: return f"SIC {m.group(1)}"
    return None


def title_confirmed(tail: str, next_line: str) -> bool:
    tail = (tail or "").strip()
    if tail and len(tail) >= 10 and RX_HAS_LETTERS.search(tail):
        return True
    if next_line and len(next_line) >= 10 and RX_HAS_LETTERS.search(next_line):
        return True
    return False


def detect_heading_top(lines: List[str], lang: str) -> Optional[str]:
    """
    Detect standard only using very top-of-page lines to avoid false positives.
    Handles:
    - strong single-line headings
    - short forms: IAS 36 / IAS36 / IFRS 9 / IFRS9 + title confirmation
    - split: IAS (line) + 36 (next line) + title (next)
    - split: INTERNATIONAL ACCOUNTING STANDARD (line) + 36 (next line)
    """
    top = [ln for ln in lines[:25] if ln]  # top-of-page window
    if not top:
        return None

    # 1) strong single-line anywhere in top window
    for ln in top[:12]:
        s = detect_strong_heading_single(ln, lang)
        if s:
            return s

    # 2) short single-line with/without spaces
    for i in range(min(6, len(top))):
        ln = top[i]
        m = RX_SHORT.match(ln) or RX_NOSPACE.match(ln)
        if not m:
            continue
        code = m.group(1).upper()
        num = m.group(2)
        tail = (m.group(3) or "")
        nxt = top[i + 1] if i + 1 < len(top) else ""
        if title_confirmed(tail, nxt):
            return f"{code} {num}"

    # 3) split code + number on next line
    for i in range(min(6, len(top) - 1)):
        if RX_CODE_ONLY.match(top[i]) and RX_NUM_ONLY.match(top[i + 1]):
            code = RX_CODE_ONLY.match(top[i]).group(1).upper()
            num = RX_NUM_ONLY.match(top[i + 1]).group(1)
            nxt = top[i + 2] if i + 2 < len(top) else ""
            if title_confirmed("", nxt):
                return f"{code} {num}"

    # 4) split EN long heading + number
    for i in range(min(6, len(top) - 1)):
        if top[i].upper().strip() in ("INTERNATIONAL ACCOUNTING STANDARD", "INTERNATIONAL FINANCIAL REPORTING STANDARD"):
            if RX_NUM_ONLY.match(top[i + 1]):
                num = RX_NUM_ONLY.match(top[i + 1]).group(1)
                if top[i].upper().startswith("INTERNATIONAL ACCOUNTING"):
                    return f"IAS {num}"
                else:
                    return f"IFRS {num}"

    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--stats", required=True)
    ap.add_argument("--lang", required=True, choices=["IT", "EN"])
    ap.add_argument("--progress-every", type=int, default=50)
    ap.add_argument("--heartbeat-seconds", type=int, default=10)
    ap.add_argument("--max-pages", type=int, default=0)
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

    if outp.exists():
        outp.unlink()

    in_annex = False
    seen_first_standard = False

    current_segment_type = "regulation"
    current_standard: Optional[str] = None
    seg_start_page = 1
    seg_text_parts: List[str] = []

    seg_counts = Counter()
    heading_hits = Counter()
    line_lens = []

    started = time.time()
    last_heartbeat = started

    def flush_segment(end_page: int):
        nonlocal seg_start_page, seg_text_parts, current_segment_type, current_standard
        if end_page < seg_start_page:
            return
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

    with rec.span("segment", pages=limit):
        for i in range(limit):
            page_no = pages[i].get("page", i + 1)
            text = pages[i].get("text_clean", "")
            lines = split_lines(text)

            for ln in lines[:200]:
                line_lens.append(len(ln))

            # Annex detection
            if not in_annex:
                for ln in lines[:80]:
                    if args.lang == "IT":
                        if RX_ANNEX_IT.match(ln) or RX_INTL_STDS_IT.match(ln):
                            in_annex = True
                            flush_segment(page_no - 1)
                            current_segment_type = "annex"
                            current_standard = None
                            seg_start_page = page_no
                            break
                    else:
                        if RX_ANNEX_EN.match(ln) or RX_INTL_STDS_EN.match(ln):
                            in_annex = True
                            flush_segment(page_no - 1)
                            current_segment_type = "annex"
                            current_standard = None
                            seg_start_page = page_no
                            break

            std_found = detect_heading_top(lines, args.lang) if in_annex else None
            if std_found:
                heading_hits[std_found] += 1
                if not seen_first_standard:
                    seen_first_standard = True
                    flush_segment(page_no - 1)  # annex up to previous page
                    current_segment_type = "standard"
                    current_standard = std_found
                    seg_start_page = page_no
                else:
                    if std_found != current_standard:
                        flush_segment(page_no - 1)
                        current_segment_type = "standard"
                        current_standard = std_found
                        seg_start_page = page_no

            if text:
                seg_text_parts.append(text)

            if args.progress_every > 0 and (i + 1) % args.progress_every == 0:
                elapsed = time.time() - started
                print(f"[{i+1:>4}/{limit}] segmented pages (elapsed {elapsed:.1f}s)")

            now = time.time()
            if now - last_heartbeat >= args.heartbeat_seconds:
                print(f"[{i+1:>4}/{limit}] heartbeat")
                last_heartbeat = now

    flush_segment(pages[limit - 1].get("page", limit))

    stats = {
        "input": str(inp),
        "output": str(outp),
        "lang": args.lang,
        "pages": limit,
        "segments_written": sum(seg_counts.values()),
        "segment_ids_top": seg_counts.most_common(80),
        "standard_heading_hits_top": heading_hits.most_common(80),
        "unique_standards": len([k for k in heading_hits.keys()]),
        "line_len_min": min(line_lens) if line_lens else 0,
        "line_len_mean": (sum(line_lens) / len(line_lens)) if line_lens else 0,
        "line_len_p95": pct(line_lens, 0.95),
        "line_len_max": max(line_lens) if line_lens else 0,
        "generated_at_utc": utc_now_z(),
    }
    statsp.write_text(json.dumps(stats, indent=2, ensure_ascii=False), encoding="utf-8")

    rec.finalize(outputs={"segments": str(outp), "stats": str(statsp), "segments_written": sum(seg_counts.values())})
    print(json.dumps({"segments": str(outp), "stats": str(statsp)}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
