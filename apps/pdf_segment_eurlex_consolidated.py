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


# ---------- Annex anchors ----------
RX_ANNEX_IT = re.compile(r"^ALLEGATO\b", re.I)
RX_ANNEX_EN = re.compile(r"^ANNEX\b", re.I)
RX_INTL_STDS_IT = re.compile(r"^PRINCIPI\s+CONTABILI\s+INTERNAZIONALI\b", re.I)
RX_INTL_STDS_EN = re.compile(r"^INTERNATIONAL\s+ACCOUNTING\s+STANDARDS\b", re.I)

# ---------- Markers ----------
# In consolidated EUR-Lex PDFs, ▼B marks a main block boundary; standards typically start after ▼B
RX_MARK_B = re.compile(r"^▼B\b|^▼B$", re.I)

# ---------- Standard headings (EN form appears in both EN and IT PDFs) ----------
RX_IAS_EN = re.compile(r"^INTERNATIONAL\s+ACCOUNTING\s+STANDARD\s+(\d+)\b", re.I)
RX_IFRS_EN = re.compile(r"^INTERNATIONAL\s+FINANCIAL\s+REPORTING\s+STANDARD\s+(\d+)\b", re.I)
RX_IFRIC = re.compile(r"^IFRIC\s+(\d+)\b", re.I)
RX_SIC = re.compile(r"^SIC\s+(\d+)\b", re.I)

# ---------- Fallback short forms (only top-of-page, title-confirmed) ----------
RX_SHORT = re.compile(r"^(IAS|IFRS|IFRIC|SIC)\s*\.?\s*(\d{1,3})\b(.*)$", re.I)
RX_NOSPACE = re.compile(r"^(IAS|IFRS|IFRIC|SIC)(\d{1,3})\b(.*)$", re.I)
RX_HAS_LETTERS = re.compile(r"[A-Za-zÀ-ÿ]")


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
    # normalize_text should already collapse odd spaces/hyphenation reasonably
    return [normalize_text(x) for x in (text or "").splitlines() if normalize_text(x)]


def title_confirmed(tail: str, next_line: str) -> bool:
    tail = (tail or "").strip()
    if tail and len(tail) >= 10 and RX_HAS_LETTERS.search(tail):
        return True
    if next_line and len(next_line) >= 10 and RX_HAS_LETTERS.search(next_line):
        return True
    return False


def detect_standard_line(line: str) -> Optional[str]:
    """
    Detect standard_id from a single line (EN headings used also in IT PDFs).
    """
    m = RX_IAS_EN.match(line)
    if m:
        return f"IAS {m.group(1)}"
    m = RX_IFRS_EN.match(line)
    if m:
        return f"IFRS {m.group(1)}"
    m = RX_IFRIC.match(line)
    if m:
        return f"IFRIC {m.group(1)}"
    m = RX_SIC.match(line)
    if m:
        return f"SIC {m.group(1)}"
    return None


def detect_standard_after_mark_b(lines: List[str]) -> Optional[str]:
    """
    Primary rule:
    In annex zone, find ▼B within the top window; then look ahead a few lines for
    'INTERNATIONAL ... STANDARD <n>' or 'IFRIC <n>' / 'SIC <n>'.
    """
    top = [ln for ln in lines[:60] if ln]
    if not top:
        return None

    for i, ln in enumerate(top[:40]):
        # marker line may contain extra tokens; we accept any line starting with ▼B
        if not RX_MARK_B.match(ln):
            continue

        # sometimes marker and heading are on the same line: "▼B INTERNATIONAL FINANCIAL ..."
        same = ln
        same = same.lstrip("▼B").strip()
        if same:
            s = detect_standard_line(same)
            if s:
                return s

        # look ahead up to 6 non-empty lines
        for j in range(i + 1, min(i + 8, len(top))):
            s = detect_standard_line(top[j])
            if s:
                return s

        # if ▼B found but no standard heading follows soon, it's probably an internal block (e.g., "WITHDRAWAL ...")
        # do not treat it as a standard switch
        return None

    return None


def detect_fallback_short_heading(lines: List[str]) -> Optional[str]:
    """
    Last-resort fallback:
    Accept "IAS 36" / "IAS36" etc only if within the very top lines and title-confirmed.
    This avoids citations deep in the text.
    """
    top = [ln for ln in lines[:25] if ln]
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

    # segmentation state
    in_annex = False
    seen_first_standard = False

    current_segment_type = "regulation"  # regulation -> annex -> standard
    current_standard: Optional[str] = None
    seg_start_page = 1
    seg_text_parts: List[str] = []

    # stats
    seg_counts = Counter()
    heading_hits = Counter()
    line_lens = []
    annex_start_page: Optional[int] = None

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
            page_no = int(pages[i].get("page", i + 1))
            text = pages[i].get("text_clean", "")
            lines = split_lines(text)

            for ln in lines[:200]:
                line_lens.append(len(ln))

            # ---- Annex detection (enter annex once) ----
            if not in_annex:
                for ln in lines[:120]:
                    if args.lang == "IT":
                        if RX_ANNEX_IT.match(ln) or RX_INTL_STDS_IT.match(ln):
                            in_annex = True
                            annex_start_page = page_no
                            flush_segment(page_no - 1)  # close regulation
                            current_segment_type = "annex"
                            current_standard = None
                            seg_start_page = page_no
                            break
                    else:
                        if RX_ANNEX_EN.match(ln) or RX_INTL_STDS_EN.match(ln):
                            in_annex = True
                            annex_start_page = page_no
                            flush_segment(page_no - 1)
                            current_segment_type = "annex"
                            current_standard = None
                            seg_start_page = page_no
                            break

            # ---- Standard detection (only in annex) ----
            std_found = None
            if in_annex:
                # primary: ▼B + INTERNATIONAL ... STANDARD <n>
                std_found = detect_standard_after_mark_b(lines)
                # fallback: short heading, but conservative
                if not std_found:
                    std_found = detect_fallback_short_heading(lines)

            if std_found:
                heading_hits[std_found] += 1
                if not seen_first_standard:
                    # close annex up to previous page
                    seen_first_standard = True
                    flush_segment(page_no - 1)
                    current_segment_type = "standard"
                    current_standard = std_found
                    seg_start_page = page_no
                else:
                    # switch only if changed
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

    flush_segment(int(pages[limit - 1].get("page", limit)))

    stats = {
        "input": str(inp),
        "output": str(outp),
        "lang": args.lang,
        "pages": limit,
        "annex_start_page": annex_start_page,
        "segments_written": sum(seg_counts.values()),
        "segment_ids_top": seg_counts.most_common(120),
        "standard_heading_hits_top": heading_hits.most_common(120),
        "unique_standards": len(list(heading_hits.keys())),
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
