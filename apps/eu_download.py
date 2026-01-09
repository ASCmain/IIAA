from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from contextlib import nullcontext
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import requests
from dotenv import load_dotenv

# Ensure project root is importable when running as a script from apps/
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from src.telemetry import TelemetryRecorder
except Exception:
    TelemetryRecorder = None  # graceful fallback


EURLEX_LEGAL_NOTICE_URL = "https://eur-lex.europa.eu/content/legal-notice/legal-notice.html"


def sha256_bytes(b: bytes) -> str:
    h = hashlib.sha256()
    h.update(b)
    return h.hexdigest()


def ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def eurlex_content_url(celex: str, lang: str, fmt: str) -> str:
    """
    EUR-Lex endpoints:
      HTML: https://eur-lex.europa.eu/legal-content/{LANG}/TXT/HTML/?uri=CELEX%3A{CELEX}
      PDF:  https://eur-lex.europa.eu/legal-content/{LANG}/TXT/PDF/?uri=CELEX%3A{CELEX}
    """
    celex_enc = celex.replace(":", "%3A")
    if fmt == "html":
        return f"https://eur-lex.europa.eu/legal-content/{lang}/TXT/HTML/?uri=CELEX%3A{celex_enc}"
    if fmt == "pdf":
        return f"https://eur-lex.europa.eu/legal-content/{lang}/TXT/PDF/?uri=CELEX%3A{celex_enc}"
    raise ValueError(f"Unsupported format: {fmt}")


def http_get(url: str, timeout: int = 120) -> requests.Response:
    headers = {
        "User-Agent": "IIAA-EURLexDownloader/0.2 (+local research)",
        "Accept": "*/*",
    }
    return requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)


def write_manifest_row(manifest_path: Path, row: Dict[str, Any]) -> None:
    ensure_dir(manifest_path.parent)
    with manifest_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def main() -> None:
    load_dotenv(dotenv_path=Path(".env"))

    ap = argparse.ArgumentParser()
    ap.add_argument("--celex", required=True, help="e.g., 02023R1803-20250730")
    ap.add_argument("--doc-id", required=True, help="local doc id, e.g. eu_oj_02023R1803_20250730")
    ap.add_argument("--langs", default="EN,IT", help="comma-separated, e.g. EN,IT")
    ap.add_argument("--formats", default="html,pdf", help="comma-separated: html,pdf")
    ap.add_argument("--out-dir", default="corpus/legal/eu_oj", help="base output dir")
    ap.add_argument("--manifest", default="corpus/legal/eu_oj/manifests/manifest_eurlex_downloads.jsonl")
    ap.add_argument("--sleep", type=float, default=0.5, help="seconds between downloads")
    args = ap.parse_args()

    base_dir = Path(args.out_dir)
    manifest_path = Path(args.manifest)

    langs = [x.strip().upper() for x in args.langs.split(",") if x.strip()]
    fmts = [x.strip().lower() for x in args.formats.split(",") if x.strip()]

    # Telemetry (aligned to src/telemetry.py API)
    rec = None
    if TelemetryRecorder is not None:
        rec = TelemetryRecorder(step="eu_download", out_dir=Path("telemetry"))
        rec.start(
            inputs={
                "celex": args.celex,
                "doc_id": args.doc_id,
                "langs": langs,
                "formats": fmts,
            },
            extra={
                "manifest_path": str(manifest_path),
                "license_notice_url": EURLEX_LEGAL_NOTICE_URL,
            },
        )

    started = datetime.now(timezone.utc)

    downloads_ok = 0
    downloads_total = 0

    for lang in langs:
        for fmt in fmts:
            downloads_total += 1
            url = eurlex_content_url(args.celex, lang, fmt)

            cm = rec.span(f"download_{lang}_{fmt}", url=url) if rec else nullcontext()
            with cm:
                status: Optional[int] = None
                content = b""
                err = None
                try:
                    r = http_get(url)
                    status = r.status_code
                    content = r.content or b""
                except Exception as e:
                    status = -1
                    err = str(e)

                saved_path = None
                sha = ""
                nbytes = len(content)

                if status == 200 and content:
                    out_path = (
                        base_dir / "original" / f"{args.doc_id}_{lang}.pdf"
                        if fmt == "pdf"
                        else base_dir / "oracle_html" / f"{args.doc_id}_{lang}.html"
                    )
                    ensure_dir(out_path.parent)
                    out_path.write_bytes(content)
                    saved_path = str(out_path)
                    sha = sha256_bytes(content)
                    downloads_ok += 1

                row: Dict[str, Any] = {
                    "doc_id": args.doc_id,
                    "celex": args.celex,
                    "language": lang,
                    "format": fmt,
                    "source_url": url,
                    "saved_path": saved_path,
                    "accessed_at_utc": datetime.now(timezone.utc).isoformat(),
                    "http_status": status,
                    "bytes": nbytes,
                    "sha256": sha,
                    "license_notice_url": EURLEX_LEGAL_NOTICE_URL,
                    "redistribution_allowed": True,
                    "notes": err,
                }
                write_manifest_row(manifest_path, row)

                if rec:
                    rec.event(
                        "download_result",
                        language=lang,
                        format=fmt,
                        http_status=status,
                        bytes=nbytes,
                        saved_path=saved_path,
                    )

            time.sleep(max(0.0, float(args.sleep)))

    ended = datetime.now(timezone.utc)

    telemetry_file = None
    if rec:
        telemetry_file = rec.finalize(
            outputs={
                "manifest_file": str(manifest_path),
                "downloads_total": downloads_total,
                "downloads_ok": downloads_ok,
            },
            extra={"started_utc": started.isoformat(), "ended_utc": ended.isoformat()},
        )

    print(
        json.dumps(
            {
                "celex": args.celex,
                "doc_id": args.doc_id,
                "manifest": str(manifest_path),
                "telemetry_file": str(telemetry_file) if telemetry_file else None,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
