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
from datetime import datetime, timezone
from typing import Dict, List, Optional

import pdfplumber

from src.telemetry import TelemetryRecorder


RX_LANG = re.compile(r"_(IT|EN)_TXT\.pdf$", re.I)
RX_CELEX = re.compile(r"(CELEX_[0-9A-Z]+)", re.I)
RX_OJ = re.compile(r"(OJ_[A-Z]_[0-9A-Z_]+)", re.I)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def guess_language(name: str) -> Optional[str]:
    m = RX_LANG.search(name)
    if m:
        return m.group(1).upper()
    return None


def guess_doc_id(path: Path) -> str:
    name = path.name
    m = RX_CELEX.search(name)
    if m:
        return m.group(1)
    m = RX_OJ.search(name)
    if m:
        return m.group(1)
    return path.stem.replace(" ", "_")


def guess_doc_type(name: str) -> str:
    u = name.upper()
    if u.startswith("OJ_"):
        return "eu_oj_pdf"
    if u.startswith("CELEX_"):
        return "eu_celex_pdf"
    if "EFRAG" in u:
        return "efrag_report_pdf"
    return "pdf"


def two_col_heuristic(pdf: pdfplumber.PDF, max_pages: int = 3) -> bool:
    """
    Cheap heuristic: if extracted text lines are very short on average and
    there are many line breaks, it often indicates multi-column or table-like layout.
    """
    lens: List[int] = []
    lines: List[int] = []
    n = min(len(pdf.pages), max_pages)
    for i in range(n):
        t = (pdf.pages[i].extract_text() or "").strip()
        if not t:
            continue
        ls = [x.strip() for x in t.splitlines() if x.strip()]
        if not ls:
            continue
        lines.append(len(ls))
        lens.extend([len(x) for x in ls[:200]])
    if not lens:
        return False
    avg_len = sum(lens) / len(lens)
    avg_lines = (sum(lines) / len(lines)) if lines else 0.0
    return (avg_len < 45 and avg_lines > 35)


def utc_now_z() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in-dir", required=True, help="Directory containing PDFs")
    ap.add_argument("--out", required=True, help="Output manifest JSON")
    ap.add_argument("--limit", type=int, default=0, help="Limit number of files (0=all)")
    args = ap.parse_args()

    in_dir = Path(args.in_dir)
    outp = Path(args.out)

    pdfs = sorted([p for p in in_dir.glob("*.pdf") if p.is_file()])
    if args.limit:
        pdfs = pdfs[: args.limit]

    step = "m2_pdf_inventory"
    rec = TelemetryRecorder(step=step)
    rec.start(inputs={"in_dir": str(in_dir), "out": str(outp), "n_files": len(pdfs)}, extra={})

    outp.parent.mkdir(parents=True, exist_ok=True)

    items: List[Dict] = []
    with rec.span("scan", n_files=len(pdfs)):
        for p in pdfs:
            # IMPORTANT: do not use meta key "name" (collides with span(name=...))
            with rec.span("file", file_name=p.name):
                doc_id = guess_doc_id(p)
                lang = guess_language(p.name)
                doc_type = guess_doc_type(p.name)
                size_bytes = p.stat().st_size
                h = sha256_file(p)
                pages = 0
                two_col = False
                try:
                    with pdfplumber.open(str(p)) as pdf:
                        pages = len(pdf.pages)
                        two_col = two_col_heuristic(pdf)
                except Exception as e:
                    pages = -1
                    two_col = False
                    rec.event("pdf_open_error", file=p.name, error=str(e))

                items.append(
                    {
                        "doc_id": doc_id,
                        "filename": p.name,
                        "path": str(p),
                        "sha256": h,
                        "bytes": size_bytes,
                        "pages": pages,
                        "language": lang,
                        "doc_type": doc_type,
                        "layout_hint": "two_col" if two_col else "one_col",
                        "registered_at_utc": utc_now_z(),
                    }
                )

    manifest = {
        "generated_at_utc": utc_now_z(),
        "in_dir": str(in_dir),
        "count": len(items),
        "items": items,
    }
    outp.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    rec.finalize(outputs={"manifest": str(outp), "count": len(items)})

    print(f"Wrote manifest: {outp} (items={len(items)})")
    for it in items:
        print(
            f"- {it['doc_id']:<22} {it.get('language','--'):<2} pages={it['pages']:<4} "
            f"layout={it['layout_hint']:<7} {it['bytes']/1024:>8.1f} KB  {it['filename']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())