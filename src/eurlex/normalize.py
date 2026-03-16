from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write_jsonl(out_path: Path, rows: list[dict[str, Any]]) -> None:
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
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
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


__all__ = [
    "sha256_file",
    "write_jsonl",
    "build_rows",
]
