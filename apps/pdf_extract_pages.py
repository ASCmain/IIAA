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
from datetime import datetime, timezone

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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--two-col", action="store_true")
    ap.add_argument("--max-pages", type=int, default=0, help="0=all")
    args = ap.parse_args()

    pdf_path = Path(args.pdf)
    outp = Path(args.out)
    outp.parent.mkdir(parents=True, exist_ok=True)

    step = "m2_pdf_extract_pages"
    rec = TelemetryRecorder(step=step)
    rec.start(
        inputs={"pdf": str(pdf_path), "out": str(outp), "two_col": args.two_col, "max_pages": args.max_pages},
        extra={},
    )

    file_sha = sha256_file(pdf_path)

    with pdfplumber.open(str(pdf_path)) as pdf:
        n_pages = len(pdf.pages)
        limit = args.max_pages if args.max_pages else n_pages

        with rec.span("extract", pages=limit):
            with outp.open("w", encoding="utf-8") as f:
                for i in range(min(limit, n_pages)):
                    page = pdf.pages[i]
                    text = extract_page_text(page, two_col=args.two_col)
                    row = {
                        "source_pdf": str(pdf_path),
                        "source_sha256": file_sha,
                        "page": i + 1,
                        "layout_hint": "two_col" if args.two_col else "one_col",
                        "text_raw": text,
                        "extracted_at_utc": utc_now_z(),
                    }
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")

    rec.finalize(outputs={"out": str(outp), "pages_written": min(limit, n_pages)})
    print(json.dumps({"out": str(outp), "pages_written": min(limit, n_pages)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
