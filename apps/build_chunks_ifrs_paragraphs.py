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
import re
from collections import defaultdict
from datetime import datetime, timezone
from typing import Dict, Iterable, List, Optional, Tuple

from src.ingestion.deterministic import sha256_text
from src.telemetry import TelemetryRecorder

# ----------------------------
# Normalization helpers
# ----------------------------
CELEX_MARKERS = re.compile(r"(►\s*[MC]\d+|▼\s*B|◄|►)")

def clean_celex(s: str) -> str:
    s = CELEX_MARKERS.sub("", s)
    return " ".join(s.split()).strip()

def norm_key(s: str) -> str:
    # Canonical key for matching titles / heading_path labels across minor unicode/whitespace variations
    return clean_celex(s).casefold()

# ----------------------------
# Detection patterns
# ----------------------------
# Paragraph keys
PARA_DOTTED = re.compile(r"^(\d+(?:\.\d+){1,4})\s+(.+)$")   # 5.5.1
PARA_INT = re.compile(r"^(\d{1,3})\s+(.+)$")               # 141
PARA_APP = re.compile(r"^((?:B|IE|BC)\d+)\s+(.+)$")         # B47

# Standard boundaries (short form)
STD_SHORT = re.compile(r"^(IAS|IFRS|IFRIC|SIC)\s+(\d+)\b", re.I)

# EN long form (sometimes appears in EN headings)
STD_EN_LONG = re.compile(
    r"^INTERNATIONAL\s+(ACCOUNTING|FINANCIAL\s+REPORTING)\s+STANDARD\s+(\d+)\b",
    re.I,
)

def para_split(text: str) -> Optional[Tuple[str, str]]:
    for rx in (PARA_DOTTED, PARA_INT, PARA_APP):
        m = rx.match(text)
        if m:
            return m.group(1), m.group(2)
    return None

def detect_standard(text: str) -> Optional[str]:
    # EN long
    m = STD_EN_LONG.match(text)
    if m:
        grp = m.group(1).lower()
        n = m.group(2)
        if "accounting" in grp:
            return f"IAS {n}"
        return f"IFRS {n}"
    # Short
    m = STD_SHORT.match(text)
    if m:
        return f"{m.group(1).upper()} {m.group(2)}"
    return None

def compact_std(std: str) -> str:
    # IAS 36 -> IAS36
    return std.replace(" ", "")

def iter_jsonl(path: Path) -> Iterable[dict]:
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            yield json.loads(line)

def load_sources(path: Path) -> Dict[str, dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    items = data.get("sources") or data.get("items") or []
    return {it["doc_id"]: it for it in items if isinstance(it, dict) and "doc_id" in it}

def build_title_to_code_map(rows: List[dict]) -> Dict[str, str]:
    """
    For consolidated EUR-Lex: there is an index section where td cells appear in pairs:
      td "IAS 36" ; td "Riduzione di valore delle attività"
    We map normalized title -> code, so later we can infer standard_id from heading_path[0] title.
    """
    title2code: Dict[str, str] = {}

    def is_index_root(hp0: str) -> bool:
        u = hp0.upper()
        return u in ("PRINCIPI CONTABILI INTERNAZIONALI", "INTERNATIONAL ACCOUNTING STANDARDS")

    for i, r in enumerate(rows):
        if (r.get("kind") or "").lower() != "td":
            continue

        hp = r.get("heading_path") or []
        hp0 = hp[0] if isinstance(hp, list) and hp else ""
        if not hp0 or not is_index_root(hp0):
            continue

        t = clean_celex((r.get("text") or "").strip())
        m = STD_SHORT.match(t)
        if not m:
            continue

        code = f"{m.group(1).upper()} {m.group(2)}"

        # Next td likely contains the title
        if i + 1 < len(rows):
            r2 = rows[i + 1]
            if (r2.get("kind") or "").lower() == "td":
                title = clean_celex((r2.get("text") or "").strip())
                if title and not STD_SHORT.match(title):
                    title2code[norm_key(title)] = code

    return title2code

def utc_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

# ----------------------------
# Main
# ----------------------------
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in-jsonl", required=True, help="Normalized EUR-Lex JSONL (one doc)")
    ap.add_argument("--sources", required=True, help="data/sources/EURLEX_SOURCES_v0.1.json")
    ap.add_argument("--out", required=True, help="Output chunks jsonl")
    ap.add_argument("--limit", type=int, default=0, help="Limit chunks for test (0=all)")
    args = ap.parse_args()

    inp = Path(args.in_jsonl)
    outp = Path(args.out)
    sources = load_sources(Path(args.sources))

    rows = list(iter_jsonl(inp))
    if not rows:
        raise SystemExit("Empty input JSONL")

    doc_id = rows[0].get("doc_id") or inp.stem
    lang = (rows[0].get("language") or "").upper()
    src_meta = sources.get(doc_id, {})

    # Title->code map for IT segmenting (and also useful for EN if needed)
    title2code = build_title_to_code_map(rows)

    step = "m2_build_chunks_ifrs_paragraphs"
    rec = TelemetryRecorder(step=step)
    rec.start(
        inputs={"in": str(inp), "out": str(outp), "sources": args.sources},
        extra={"doc_id": doc_id, "lang": lang, "run_id": utc_run_id()},
    )

    outp.parent.mkdir(parents=True, exist_ok=True)
    if outp.exists():
        outp.unlink(missing_ok=True)

    # Base payload fields (join what exists in sources; fall back to JSONL header fields)
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
    ]:
        if k in src_meta:
            base[k] = src_meta.get(k)

    base.setdefault("doc_id", doc_id)
    base.setdefault("language", lang)
    base["source_url"] = rows[0].get("source_url")
    base["sha256"] = rows[0].get("sha256")
    base["source_path"] = rows[0].get("source_path")  # raw html path for audit

    cur_std: Optional[str] = None
    chunk_index = 0
    written = 0

    # Collect chunks in a streaming write (deterministic order = input order)
    with rec.span("build_chunks", rows=len(rows)):
        with outp.open("a", encoding="utf-8") as fout:
            for r in rows:
                kind = (r.get("kind") or "").lower()
                text = clean_celex((r.get("text") or "").strip())
                if not text:
                    continue

                hp = r.get("heading_path") or []
                hp0 = hp[0] if isinstance(hp, list) and hp else ""
                hp0_key = norm_key(hp0) if hp0 else ""

                # (1) IT segment anchor: if heading_path root title maps to a code, force cur_std
                # This is the key fix for IAS 36 IT and similar standards.
                if lang == "IT" and hp0_key and hp0_key in title2code:
                    cur_std = title2code[hp0_key]

                # (2) EN/IT headings can still explicitly carry standard boundary
                if kind in ("heading", "h1", "h2", "h3", "h4", "td"):
                    s = detect_standard(text)
                    if s:
                        cur_std = s

                # We chunk only paragraph rows (consistent with earlier design)
                if kind != "paragraph":
                    continue
                if not cur_std:
                    continue

                ps = para_split(text)
                if not ps:
                    continue
                para_key, para_text = ps

                # Optional noise filter for IFRS 9 consolidated tail (keeps dotted + B/IE/BC + 2-digit+)
                if cur_std == "IFRS 9" and para_key.isdigit():
                    # drop very small ints that often come from table artifacts
                    if int(para_key) < 20:
                        continue

                cite_key = f"{compact_std(cur_std)}:{para_key}"

                payload = {
                    **base,
                    "page": 0,  # indexer compatibility
                    "standard_id": cur_std,
                    "para_key": para_key,
                    "cite_key": cite_key,
                    "heading_path": hp,
                    "block_index": r.get("block_index"),
                    "chunk_index": chunk_index,
                    "chunk_sha256": sha256_text(para_text),
                    "text": para_text,
                }

                fout.write(json.dumps(payload, ensure_ascii=False) + "\n")

                chunk_index += 1
                written += 1
                if args.limit and written >= args.limit:
                    break

    rec.finalize(outputs={"chunks_written": written, "out": str(outp), "doc_id": doc_id})
    print(json.dumps({"doc_id": doc_id, "lang": lang, "chunks_written": written, "out": str(outp)}, ensure_ascii=False, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
