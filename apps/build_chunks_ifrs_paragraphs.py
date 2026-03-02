#!/usr/bin/env python3
from __future__ import annotations

# Bootstrap: allow running from repo root without installing as a package
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from src.ingestion.deterministic import sha256_text
from src.parse.eurlex_html import TextBlock
from src.parse.ifrs_extract import extract_standard_paragraphs
from src.telemetry import TelemetryRecorder


def utc_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def iter_jsonl(path: Path) -> Iterable[dict]:
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


def load_sources(path: Path) -> Dict[str, dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    items = data.get("sources") or data.get("items") or []
    return {it["doc_id"]: it for it in items if isinstance(it, dict) and "doc_id" in it}


def kind_to_textblock_kind(kind: str) -> str:
    k = (kind or "").lower().strip()
    if k in ("heading", "h1", "h2", "h3", "h4"):
        return "heading"
    if k == "li":
        return "li"
    return "p"


def compact_std(std: str) -> str:
    return std.replace(" ", "")


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in-jsonl", required=True, help="Normalized EUR-Lex HTML JSONL (one doc)")
    ap.add_argument("--sources", required=True, help="data/sources/EURLEX_SOURCES_v0.1.json")
    ap.add_argument("--out", required=True, help="Output chunks jsonl")
    ap.add_argument("--limit", type=int, default=0, help="Limit chunks for test (0=all)")
    ap.add_argument("--progress-every", type=int, default=0, help="Progress print every N blocks (0=off)")
    return ap.parse_args()


def main() -> int:
    args = parse_args()
    inp = Path(args.in_jsonl)
    outp = Path(args.out)

    sources = load_sources(Path(args.sources))

    rows_iter = iter_jsonl(inp)
    first_row = None
    rows: List[dict] = []
    for r in rows_iter:
        if first_row is None:
            first_row = r
        rows.append(r)

    if not rows or first_row is None:
        raise SystemExit("Empty input JSONL")

    doc_id = first_row.get("doc_id") or inp.stem
    lang = (first_row.get("language") or first_row.get("lang") or "").upper() or "UNK"
    src_meta = sources.get(doc_id, {})

    step = "m2_build_chunks_ifrs_paragraphs"
    rec = TelemetryRecorder(step=step)
    rec.start(
        inputs={"in": str(inp), "out": str(outp), "sources": args.sources},
        extra={"doc_id": doc_id, "lang": lang, "run_id": utc_run_id()},
    )

    outp.parent.mkdir(parents=True, exist_ok=True)
    if outp.exists():
        outp.unlink(missing_ok=True)

    base: Dict[str, object] = {}
    for k in [
        "doc_id",
        "doc_family_id",
        "doc_variant",
        "source_tier",
        "authority_level",
        "jurisdiction",
        "celex_id",
        "oj_id",
        "publication_date",
        "effective_date",
        "license_class",
        "redistribution_allowed",
        "version_kind",
        "source_family",
        "title",
    ]:
        if k in src_meta:
            base[k] = src_meta.get(k)

    base.setdefault("doc_id", doc_id)
    base["language"] = lang
    base["source_url"] = first_row.get("source_url")
    base["source_path"] = first_row.get("source_path")
    base["sha256"] = first_row.get("sha256")

    blocks: List[TextBlock] = []
    with rec.span("load_blocks", rows=len(rows)):
        for i, r in enumerate(rows, start=1):
            txt = (r.get("text") or "").strip()
            if not txt:
                continue
            tb_kind = kind_to_textblock_kind(r.get("kind") or "p")
            blocks.append(TextBlock(kind=tb_kind, text=txt, amendment_marker=None))

            if args.progress_every and i % args.progress_every == 0:
                print(f"[{i}] blocks scanned (kept={len(blocks)})")

    with rec.span("extract_standard_paragraphs", blocks=len(blocks)):
        extracted = extract_standard_paragraphs(blocks)

    counts = {k: len(v) for k, v in extracted.items()}
    total_paras = sum(counts.values())

    if args.limit and total_paras > args.limit:
        total_target = args.limit
    else:
        total_target = total_paras

    std_counter = Counter()
    max_len = 0
    max_len_std = None
    max_len_key = None

    chunk_index = 0
    written = 0

    with rec.span("write_chunks", standards=len(extracted), paragraphs_total=total_target):
        with outp.open("a", encoding="utf-8") as fout:
            for std in sorted(extracted.keys()):
                paras = extracted.get(std) or []
                for p in paras:
                    if args.limit and written >= args.limit:
                        break

                    text = (p.text or "").strip()
                    if not text:
                        continue

                    para_key = p.key
                    cite_key = f"{compact_std(std)}:{para_key}"

                    chunk_sha = sha256_text(text)

                    std_counter[std] += 1
                    if len(text) > max_len:
                        max_len = len(text)
                        max_len_std = std
                        max_len_key = para_key

                    payload = {
                        **base,
                        "page": 0,
                        "standard_id": std,
                        "standard_codes": [std],
                        "para_key": para_key,
                        "cite_key": cite_key,
                        "section_path": getattr(p, "section_path", None),
                        "chunk_index": chunk_index,
                        "chunk_sha256": chunk_sha,
                        "text": text,
                    }

                    fout.write(json.dumps(payload, ensure_ascii=False) + "\n")
                    chunk_index += 1
                    written += 1

                if args.limit and written >= args.limit:
                    break

    stats = {
        "doc_id": doc_id,
        "language": lang,
        "standards_extracted": len(extracted),
        "paragraphs_total": written,
        "top_20_standards": sorted(((k, v) for k, v in std_counter.items()), key=lambda x: x[1], reverse=True)[:20],
        "max_paragraph_len": max_len,
        "max_paragraph_ref": {"standard_id": max_len_std, "para_key": max_len_key},
    }

    rec.finalize(outputs={"chunks_written": written, "out": str(outp), "doc_id": doc_id, "stats": stats})
    print(json.dumps({"doc_id": doc_id, "lang": lang, "chunks_written": written, "out": str(outp)}, ensure_ascii=False, indent=2))
    print(json.dumps(stats, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
