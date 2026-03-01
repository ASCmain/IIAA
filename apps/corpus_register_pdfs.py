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
from typing import Dict, List, Optional, Tuple

import pdfplumber

from src.telemetry import TelemetryRecorder


RX_LANG = re.compile(r"_(IT|EN)_TXT$", re.I)
RX_OJ = re.compile(r"^(OJ_[A-Z]_[0-9A-Z_]+)", re.I)          # e.g. OJ_L_202600338_IT_TXT
RX_CELEX = re.compile(r"^(CELEX_[0-9A-Z\-]+)", re.I)         # e.g. CELEX_02023R1803-20250730_IT_TXT
RX_CELEX_FAMILY = re.compile(r"^(CELEX_[0-9A-Z\-]+)", re.I)  # keep full celex id if present


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def normalize_stem(stem: str) -> str:
    return stem.replace(" ", "_")


def guess_language_from_stem(stem: str) -> Optional[str]:
    m = RX_LANG.search(stem)
    if m:
        return m.group(1).upper()
    return None


def guess_doc_type(stem: str) -> str:
    u = stem.upper()
    if u.startswith("OJ_"):
        return "eu_oj_pdf"
    if u.startswith("CELEX_"):
        return "eu_celex_pdf"
    if "EFRAG" in u:
        return "efrag_report_pdf"
    return "pdf"


def guess_ids(path: Path) -> Tuple[str, str, Optional[str]]:
    """
    Returns (doc_id, doc_family_id, language).
    doc_id must be UNIQUE per file.
    doc_family_id groups IT/EN variants and versions.
    """
    stem = normalize_stem(path.stem)

    lang = guess_language_from_stem(stem)

    # Unique per file
    doc_id = stem

    # Family id
    m = RX_OJ.match(stem)
    if m:
        family = m.group(1)
        return doc_id, family, lang

    m = RX_CELEX.match(stem)
    if m:
        family = m.group(1)
        return doc_id, family, lang

    # fallback: use stem as family too
    return doc_id, stem, lang


def two_col_heuristic(pdf: pdfplumber.PDF, max_pages: int = 3) -> bool:
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
            with rec.span("file", file_name=p.name):
                doc_id, doc_family_id, lang = guess_ids(p)
                doc_type = guess_doc_type(p.stem)
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
                        "doc_family_id": doc_family_id,
                        "filename": p.name,
                        "path": str(p),
                        "sha256": h,
                        "bytes": size_bytes,
                        "pages": pages,
                        "language": lang,  # may be None (e.g., EFRAG)
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
        lang_print = it.get("language") or "--"
        print(
            f"- {it['doc_id']:<40} fam={it['doc_family_id']:<26} {lang_print:<2} "
            f"pages={it['pages']:<4} layout={it['layout_hint']:<7} {it['bytes']/1024:>8.1f} KB  {it['filename']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
