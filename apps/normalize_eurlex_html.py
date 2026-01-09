# apps/normalize_eurlex_html.py
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Ensure repo root is on sys.path so `import src...` works when running `python apps/...`
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dotenv import load_dotenv

from src.eurlex_html_blocks import extract_blocks_from_file
from src.telemetry import TelemetryRecorder


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write_jsonl(out_path: Path, rows: list[dict]) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def build_rows(
    *,
    blocks,
    doc_id: str,
    celex: str,
    language: str,
    source_url: str | None,
    source_path: Path,
    source_sha256: str,
) -> list[dict]:
    rows: list[dict] = []
    for i, b in enumerate(blocks):
        rows.append(
            {
                "doc_id": doc_id,
                "celex": celex,
                "language": language,
                "source_url": source_url,
                "source_path": str(source_path),
                "sha256": source_sha256,
                "block_index": i,
                "kind": b.kind,
                "heading_path": b.heading_path,
                "text": b.text,
            }
        )
    return rows


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Normalize EUR-Lex 'oracle' HTML and emit structured blocks JSONL."
    )
    p.add_argument("--input", required=True, help="Path to oracle HTML file")
    p.add_argument("--out", required=True, help="Output JSONL path")
    p.add_argument(
        "--doc-id",
        required=True,
        help="Logical doc_id (e.g. eu_oj_02023R1803_20250730)",
    )
    p.add_argument("--celex", required=True, help="CELEX (e.g. 02023R1803-20250730)")
    p.add_argument("--lang", required=True, choices=["EN", "IT"], help="Language code")
    p.add_argument("--source-url", default=None, help="Optional source URL for traceability")
    p.add_argument(
        "--telemetry-out",
        default="telemetry",
        help="Telemetry base directory (default: telemetry)",
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()

    load_dotenv(dotenv_path=Path(".env"))

    input_path = Path(args.input)
    out_path = Path(args.out)
    telemetry_base = Path(args.telemetry_out)

    rec = TelemetryRecorder(step="normalize_eurlex_html", out_dir=telemetry_base)

    inputs = {
        "input_path": str(input_path),
        "out_path": str(out_path),
        "doc_id": args.doc_id,
        "celex": args.celex,
        "language": args.lang,
        "source_url": args.source_url,
    }
    extra = {
        "started_utc": datetime.now(timezone.utc).isoformat(),
    }

    rec.start(inputs=inputs, extra=extra)

    rec.event("inputs", **inputs)

    outputs: dict = {}

    try:
        with rec.span("read_and_hash"):
            if not input_path.exists():
                raise FileNotFoundError(str(input_path))
            source_sha256 = sha256_file(input_path)

        with rec.span("extract_blocks"):
            blocks = extract_blocks_from_file(input_path)

        with rec.span("build_rows"):
            rows = build_rows(
                blocks=blocks,
                doc_id=args.doc_id,
                celex=args.celex,
                language=args.lang,
                source_url=args.source_url,
                source_path=input_path,
                source_sha256=source_sha256,
            )

        with rec.span("write_jsonl"):
            write_jsonl(out_path, rows)

        outputs = {
            "blocks_count": len(rows),
            "output_bytes": out_path.stat().st_size if out_path.exists() else 0,
            "sha256": source_sha256,
        }
        rec.event("result", **outputs)
        return 0

    except Exception as e:
        rec.event("error", error_type=type(e).__name__, message=str(e))
        raise
    finally:
        rec.finalize(outputs=outputs)


if __name__ == "__main__":
    raise SystemExit(main())
