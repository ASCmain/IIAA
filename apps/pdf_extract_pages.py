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
import re
import time
from datetime import datetime, timezone
from typing import Dict, List, Tuple, Any

import pdfplumber

from src.telemetry import TelemetryRecorder


RX_TOKEN_INTERNATIONAL = re.compile(r"\bINTERNATIONAL\b", re.I)
RX_TOKEN_STANDARD = re.compile(r"\bSTANDARD\b", re.I)
RX_TOKEN_IFRS = re.compile(r"\bIFRS\b", re.I)
RX_TOKEN_IAS = re.compile(r"\bIAS\b", re.I)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def utc_now_z() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def pct(values: List[int], p: float) -> int:
    if not values:
        return 0
    values = sorted(values)
    k = int(round((len(values) - 1) * p))
    return values[max(0, min(k, len(values) - 1))]


def extract_text_mode(page, *, two_col: bool, layout: bool, x_tol: float, y_tol: float) -> str:
    """
    pdfminer text extraction. Useful as fallback, but can fail on complex layouts.
    """
    if not two_col:
        try:
            t = page.extract_text(layout=layout, x_tolerance=x_tol, y_tolerance=y_tol)  # type: ignore
        except TypeError:
            # older pdfplumber versions may not support these kwargs the same way
            t = page.extract_text()  # type: ignore
        return (t or "").strip()

    w = float(page.width)
    h = float(page.height)
    mid = w / 2.0
    left = page.within_bbox((0, 0, mid, h))
    right = page.within_bbox((mid, 0, w, h))
    try:
        tl = left.extract_text(layout=layout, x_tolerance=x_tol, y_tolerance=y_tol)  # type: ignore
        tr = right.extract_text(layout=layout, x_tolerance=x_tol, y_tolerance=y_tol)  # type: ignore
    except TypeError:
        tl = left.extract_text()  # type: ignore
        tr = right.extract_text()  # type: ignore
    return ((tl or "").strip() + "\n" + (tr or "").strip()).strip()


def words_to_lines(words: List[Dict[str, Any]], *, y_tol: float) -> List[List[Dict[str, Any]]]:
    """
    Group words into lines using their 'top' coordinate.
    """
    if not words:
        return []

    words_sorted = sorted(words, key=lambda w: (float(w.get("top", 0.0)), float(w.get("x0", 0.0))))
    lines: List[List[Dict[str, Any]]] = []
    current: List[Dict[str, Any]] = []
    current_top: float | None = None

    for w in words_sorted:
        top = float(w.get("top", 0.0))
        if current_top is None:
            current_top = top
            current = [w]
            continue

        if abs(top - current_top) <= y_tol:
            current.append(w)
        else:
            lines.append(current)
            current_top = top
            current = [w]

    if current:
        lines.append(current)

    # sort words in each line by x0
    for ln in lines:
        ln.sort(key=lambda w: float(w.get("x0", 0.0)))
    return lines


def render_lines(lines: List[List[Dict[str, Any]]], *, x_join_tol: float = 1.0) -> str:
    """
    Render grouped word lines into text. Adds a space when words are separated on x-axis.
    """
    out_lines: List[str] = []
    for ln in lines:
        parts: List[str] = []
        prev_x1: float | None = None
        for w in ln:
            txt = (w.get("text") or "").strip()
            if not txt:
                continue
            x0 = float(w.get("x0", 0.0))
            x1 = float(w.get("x1", 0.0))
            if prev_x1 is not None and (x0 - prev_x1) > x_join_tol:
                parts.append(" ")
            parts.append(txt)
            prev_x1 = x1
        line_text = "".join(parts).strip()
        if line_text:
            out_lines.append(line_text)
    return "\n".join(out_lines).strip()


def extract_words_mode(page, *, two_col: bool, y_tol: float, x_join_tol: float) -> str:
    """
    Coordinate-based extraction: extract_words -> group into lines -> render.
    Much more robust for headings and mixed layouts.
    """
    def page_words(p) -> List[Dict[str, Any]]:
        # keep_blank_chars=False keeps output cleaner; use_text_flow=False reduces weird reordering
        try:
            return p.extract_words(keep_blank_chars=False, use_text_flow=False)  # type: ignore
        except TypeError:
            return p.extract_words()  # type: ignore

    if not two_col:
        words = page_words(page)
        lines = words_to_lines(words, y_tol=y_tol)
        return render_lines(lines, x_join_tol=x_join_tol)

    w = float(page.width)
    h = float(page.height)
    mid = w / 2.0
    left = page.within_bbox((0, 0, mid, h))
    right = page.within_bbox((mid, 0, w, h))

    wl = page_words(left)
    wr = page_words(right)

    ll = words_to_lines(wl, y_tol=y_tol)
    lr = words_to_lines(wr, y_tol=y_tol)

    tl = render_lines(ll, x_join_tol=x_join_tol)
    tr = render_lines(lr, x_join_tol=x_join_tol)
    return (tl + "\n" + tr).strip()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--stats", default="", help="Optional stats JSON output (default: <out>.stats.json)")

    ap.add_argument("--mode", choices=["words", "text"], default="words", help="Extraction mode (default: words)")
    ap.add_argument("--two-col", action="store_true")

    # text-mode tuning
    ap.add_argument("--layout", action="store_true", help="(text mode) request layout-aware extraction where supported")
    ap.add_argument("--x-tol", type=float, default=1.5, help="(text mode) x_tolerance, also reused by some pdfplumber versions")
    ap.add_argument("--y-tol", type=float, default=2.0, help="(words mode) y tolerance to group words into a line")
    ap.add_argument("--x-join-tol", type=float, default=1.0, help="(words mode) x gap that triggers inserting a space")

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
            "mode": args.mode,
            "two_col": args.two_col,
            "layout": args.layout,
            "x_tol": args.x_tol,
            "y_tol": args.y_tol,
            "x_join_tol": args.x_join_tol,
            "max_pages": args.max_pages,
        },
        extra={"progress_every": args.progress_every, "heartbeat_seconds": args.heartbeat_seconds},
    )

    file_sha = sha256_file(pdf_path)

    lengths: List[int] = []
    empty_pages = 0
    pages_with_international = 0
    pages_with_standard = 0
    pages_with_ifrs = 0
    pages_with_ias = 0

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
                    if args.mode == "words":
                        text = extract_words_mode(page, two_col=args.two_col, y_tol=args.y_tol, x_join_tol=args.x_join_tol)
                    else:
                        text = extract_text_mode(page, two_col=args.two_col, layout=args.layout, x_tol=args.x_tol, y_tol=args.y_tol)

                    text = (text or "").strip()
                    L = len(text)
                    lengths.append(L)
                    if L == 0:
                        empty_pages += 1

                    if RX_TOKEN_INTERNATIONAL.search(text):
                        pages_with_international += 1
                    if RX_TOKEN_STANDARD.search(text):
                        pages_with_standard += 1
                    if RX_TOKEN_IFRS.search(text):
                        pages_with_ifrs += 1
                    if RX_TOKEN_IAS.search(text):
                        pages_with_ias += 1

                    row = {
                        "source_pdf": str(pdf_path),
                        "source_sha256": file_sha,
                        "page": i + 1,
                        "layout_hint": "two_col" if args.two_col else "one_col",
                        "mode": args.mode,
                        "text_raw": text,
                        "extracted_at_utc": utc_now_z(),
                    }
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")

                    if args.progress_every > 0 and (i + 1) % args.progress_every == 0:
                        elapsed = time.time() - started
                        print(f"[{i+1:>4}/{limit}] extracted pages (elapsed {elapsed:.1f}s)")

                    now = time.time()
                    if now - last_heartbeat >= args.heartbeat_seconds:
                        print(f"[{i+1:>4}/{limit}] heartbeat")
                        last_heartbeat = now

    stats: Dict = {
        "pdf": str(pdf_path),
        "sha256": file_sha,
        "out": str(outp),
        "mode": args.mode,
        "two_col": args.two_col,
        "pages_written": limit,
        "empty_pages": empty_pages,
        "len_chars_min": min(lengths) if lengths else 0,
        "len_chars_mean": (sum(lengths) / len(lengths)) if lengths else 0,
        "len_chars_p95": pct(lengths, 0.95),
        "len_chars_max": max(lengths) if lengths else 0,
        "pages_with_INTERNATIONAL": pages_with_international,
        "pages_with_STANDARD": pages_with_standard,
        "pages_with_IFRS": pages_with_ifrs,
        "pages_with_IAS": pages_with_ias,
        "generated_at_utc": utc_now_z(),
    }
    statsp.write_text(json.dumps(stats, indent=2, ensure_ascii=False), encoding="utf-8")

    rec.finalize(
        outputs={
            "out": str(outp),
            "stats": str(statsp),
            "pages_written": limit,
            "empty_pages": empty_pages,
            "pages_with_INTERNATIONAL": pages_with_international,
            "pages_with_STANDARD": pages_with_standard,
        }
    )
    print(json.dumps({"out": str(outp), "stats": str(statsp), "pages_written": limit}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
