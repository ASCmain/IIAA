#!/usr/bin/env python3
from __future__ import annotations

import argparse
import glob
import json
from pathlib import Path
from typing import Dict, List

from src.parse.eurlex_html import html_to_blocks
from src.parse.ifrs_extract import extract_standard_paragraphs
from src.telemetry import TelemetryRecorder


TARGETS = {"IAS 36", "IFRS 13", "IFRS 9", "IFRS 7", "IFRS 1"}  # from CELEX 2023/1803 annex
# IFRS 18 is mainly in 2026/338; it might also appear in consolidated texts depending on annex; we report separately.


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--in", dest="inp", required=True, help="debug_dump/eurlex_raw directory")
    p.add_argument("--out", required=True, help="debug_dump/eurlex_parsed (non versionato) or corpus_clean")
    args = p.parse_args()

    step = "m2_parse_eurlex_html"
    rec = TelemetryRecorder(step=step)
    rec.start(inputs={"in": args.inp, "out": args.out}, extra={})

    in_dir = Path(args.inp)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    files = sorted(glob.glob(str(in_dir / "*.html")))
    rec.event("inputs_found", count=len(files))

    report = {
        "inputs": len(files),
        "documents": [],
        "targets": sorted(TARGETS),
    }

    with rec.span("parse_all", count=len(files)):
        for fp in files:
            path = Path(fp)
            raw = path.read_text(encoding="utf-8", errors="ignore")
            blocks = html_to_blocks(raw)
            std_map = extract_standard_paragraphs(blocks)

            doc_entry = {
                "file": path.name,
                "blocks": len(blocks),
                "standards_found": sorted(std_map.keys()),
                "targets": {},
            }

            for t in TARGETS:
                paras = std_map.get(t, [])
                doc_entry["targets"][t] = {
                    "paragraphs": len(paras),
                    "first_keys": [p.key for p in paras[:5]],
                    "last_keys": [p.key for p in paras[-5:]] if paras else [],
                }

            report["documents"].append(doc_entry)
            rec.event("parsed_one", file=path.name, blocks=len(blocks), standards=len(std_map))

    out_path = out_dir / "sanity_report.json"
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    rec.finalize(outputs={"report": str(out_path), "documents": len(report["documents"])})
    print(f"Wrote: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
