#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

# --- repo-root bootstrap (MUST be before importing `src.*`) ---
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.telemetry import TelemetryRecorder
from src.parse.ifrs_extract import detect_standard_boundary


TARGETS = ["IAS 36", "IFRS 1", "IFRS 7", "IFRS 9", "IFRS 13"]


def utc_now_z() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Sanity checks for HTML-first EUR-Lex normalized JSONL.")
    p.add_argument("--in", dest="inp", required=True, help="Input normalized blocks JSONL")
    p.add_argument("--out", required=True, help="Output report JSON")
    p.add_argument("--telemetry-out", default="telemetry", help="Telemetry base directory (default: telemetry)")
    p.add_argument("--max-lines", type=int, default=0, help="0=all; for quick debug")
    return p.parse_args()


def load_jsonl(path: Path, max_lines: int = 0) -> List[dict]:
    rows: List[dict] = []
    with path.open("r", encoding="utf-8") as f:
        for i, line in enumerate(f, start=1):
            if max_lines and i > max_lines:
                break
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def main() -> int:
    args = parse_args()
    inp = Path(args.inp)
    outp = Path(args.out)
    outp.parent.mkdir(parents=True, exist_ok=True)

    rec = TelemetryRecorder(step="m2_sanity_ifrs_html", out_dir=Path(args.telemetry_out))
    rec.start(inputs={"in": str(inp), "out": str(outp), "max_lines": args.max_lines}, extra={})

    try:
        rows = load_jsonl(inp, max_lines=args.max_lines)

        counts_kind = Counter((r.get("kind") or "unknown") for r in rows)
        counts_std = Counter()
        std_first_examples: Dict[str, List[dict]] = defaultdict(list)

        for r in rows:
            txt = (r.get("text") or "").strip()
            if not txt:
                continue

            # STRICT boundary detection (prevents "IFRS 9 permits ..." false positives)
            sid = detect_standard_boundary(txt)
            if sid:
                counts_std[sid] += 1
                if len(std_first_examples[sid]) < 3:
                    std_first_examples[sid].append(
                        {
                            "block_index": r.get("block_index"),
                            "kind": r.get("kind"),
                            "heading_path": r.get("heading_path"),
                            "text": txt[:200],
                        }
                    )

        report = {
            "input": str(inp),
            "rows": len(rows),
            "kinds": dict(counts_kind),
            "standards_detected": dict(counts_std),
            "targets": {
                t: {"hits": int(counts_std.get(t, 0)), "examples": std_first_examples.get(t, [])}
                for t in TARGETS
            },
            "generated_at_utc": utc_now_z(),
        }

        outp.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

        rec.finalize(outputs={"report": str(outp), "rows": len(rows), "standards_unique": len(counts_std)})
        print(json.dumps(report["targets"], indent=2, ensure_ascii=False))
        print(f"Wrote: {outp}")
        return 0

    except Exception as e:
        rec.event("error", error_type=type(e).__name__, message=str(e))
        rec.finalize(outputs={"error": str(e)})
        raise


if __name__ == "__main__":
    raise SystemExit(main())
