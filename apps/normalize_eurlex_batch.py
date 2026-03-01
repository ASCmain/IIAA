#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]

def load_sources(p: Path) -> List[dict]:
    return json.loads(p.read_text(encoding="utf-8"))["sources"]

def newest_dump(raw_dir: Path, doc_id: str) -> Optional[Path]:
    # match: <doc_id>.<timestamp>.html (or .pdf saved as .html by fetcher)
    candidates = sorted(raw_dir.glob(f"{doc_id}.*.html"), key=lambda x: x.name)
    return candidates[-1] if candidates else None

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sources", required=True)
    ap.add_argument("--raw", required=True)
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--telemetry-out", default="telemetry")
    args = ap.parse_args()

    sources = load_sources(Path(args.sources))
    raw_dir = Path(args.raw)
    out_dir = Path(args.outdir)
    out_dir.mkdir(parents=True, exist_ok=True)

    ok = 0
    ko = 0

    for i, s in enumerate(sources, start=1):
        doc_id = s.get("doc_id")
        url = s.get("source_uri")
        lang = (s.get("language") or "").lower()
        celex = s.get("celex_id") or s.get("oj_id") or ""

        if not doc_id:
            ko += 1
            print(f"[{i:02d}] MISSING doc_id -> skip")
            continue

        src = newest_dump(raw_dir, doc_id)
        if not src:
            ko += 1
            print(f"[{i:02d}] {doc_id}  NO_DUMP -> skip")
            continue

        # map lang -> EN/IT expected by normalize_eurlex_html.py
        if lang == "it":
            lang_arg = "IT"
        elif lang == "en":
            lang_arg = "EN"
        else:
            # fallback: infer from URL path
            if url and "/IT/" in url:
                lang_arg = "IT"
            elif url and "/EN/" in url:
                lang_arg = "EN"
            else:
                lang_arg = "EN"

        out_path = out_dir / f"{doc_id}.jsonl"

        cmd = [
            sys.executable,
            str(REPO_ROOT / "apps" / "normalize_eurlex_html.py"),
            "--input", str(src),
            "--out", str(out_path),
            "--doc-id", doc_id,
            "--celex", celex if celex else doc_id,
            "--lang", lang_arg,
            "--source-url", url or "",
            "--telemetry-out", args.telemetry_out,
        ]

        print(f"[{i:02d}] {doc_id}  -> {out_path.name}")
        try:
            subprocess.check_call(cmd)
            ok += 1
        except subprocess.CalledProcessError as e:
            ko += 1
            print(f"     FAIL: {e}")

    print(f"DONE ok={ok} fail={ko}")
    return 0 if ko == 0 else 2

if __name__ == "__main__":
    raise SystemExit(main())
