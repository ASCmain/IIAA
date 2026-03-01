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
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.fetch.eurlex import fetch_html
from src.telemetry import TelemetryRecorder


def load_sources(path: Path) -> List[Dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data["sources"]


def safe_name(s: str) -> str:
    return "".join(c if c.isalnum() or c in ("-", "_", ".") else "_" for c in s)


def _git_commit() -> Optional[str]:
    head = REPO_ROOT / ".git" / "HEAD"
    try:
        if head.exists():
            ref = head.read_text().strip()
            if ref.startswith("ref:"):
                ref_path = REPO_ROOT / ".git" / ref.split(":", 1)[1].strip()
                if ref_path.exists():
                    return ref_path.read_text().strip()
            return ref
    except Exception:
        return None
    return None


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--sources", required=True, help="Path to EURLEX_SOURCES_*.json")
    p.add_argument("--out", required=True, help="Directory for raw HTML dumps (debug_dump/eurlex_raw)")
    p.add_argument("--user-agent", default="IIAA/0.2 (html-first; eur-lex fetch)")
    args = p.parse_args()

    step = "m2_fetch_eurlex_html"
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    inputs = {"sources": args.sources, "out": str(out_dir)}
    extra = {"user_agent": args.user_agent, "download_ts_utc": ts}

    rec = TelemetryRecorder(step=step)
    rec.start(inputs=inputs, extra=extra)

    sources = load_sources(Path(args.sources))
    rec.event("sources_loaded", count=len(sources))

    fetched: List[Dict[str, Any]] = []
    failed: List[Dict[str, Any]] = []

    with rec.span("fetch_all", count=len(sources)):
        for s in sources:
            url = s.get("source_uri", "")
            doc_id = s.get("doc_id", "unknown")
            if not url:
                failed.append({"doc_id": doc_id, "reason": "missing source_uri"})
                rec.event("fetch_skipped", doc_id=doc_id, reason="missing_source_uri")
                continue

            fname = safe_name(f"{doc_id}.{ts}.html")
            out_path = out_dir / fname

            try:
                r = fetch_html(url=url, out_path=str(out_path), user_agent=args.user_agent)
                fetched.append(
                    {
                        "doc_id": doc_id,
                        "url": url,
                        "status_code": r.status_code,
                        "sha256": r.sha256,
                        "bytes": r.bytes,
                        "saved_path": r.saved_path,
                        "downloaded_at_utc": ts,
                    }
                )
                rec.event("fetched_one", doc_id=doc_id, status_code=r.status_code, bytes=r.bytes)
            except Exception as e:
                failed.append({"doc_id": doc_id, "url": url, "error": str(e)})
                rec.event("fetch_failed", doc_id=doc_id, error=str(e))

    manifest = {"downloaded_at_utc": ts, "fetched": fetched, "failed": failed}
    (out_dir / f"manifest.{ts}.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    rec.finalize(
        outputs={"fetched": len(fetched), "failed": len(failed), "manifest": str(out_dir / f"manifest.{ts}.json")},
        git_commit=_git_commit(),
    )

    return 0 if not failed else 2


if __name__ == "__main__":
    raise SystemExit(main())
