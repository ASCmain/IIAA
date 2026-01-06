from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from pypdf import PdfReader


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def normalize_text(text: str) -> str:
    t = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = []
    for line in t.split("\n"):
        line = " ".join(line.split())
        lines.append(line)
    t = "\n".join(lines)
    while "\n\n\n" in t:
        t = t.replace("\n\n\n", "\n\n")
    return t.strip()


@dataclass(frozen=True)
class ChunkSpec:
    max_chars: int = 1800
    overlap_chars: int = 200


def chunk_text(text: str, spec: ChunkSpec) -> list[dict[str, Any]]:
    if not text:
        return []

    max_chars = max(200, int(spec.max_chars))
    overlap = max(0, min(int(spec.overlap_chars), max_chars - 1))

    out: list[dict[str, Any]] = []
    start = 0
    idx = 0
    n = len(text)

    while start < n:
        end = min(n, start + max_chars)
        chunk = text[start:end]
        out.append(
            {
                "chunk_index": idx,
                "start_char": start,
                "end_char": end,
                "text": chunk,
                "chunk_sha256": sha256_text(chunk),
            }
        )
        idx += 1
        if end >= n:
            break
        start = end - overlap

    return out


def read_pdf_pages(path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    reader = PdfReader(str(path))
    pages: list[dict[str, Any]] = []
    empty_pages = 0

    for i, page in enumerate(reader.pages, start=1):
        raw = page.extract_text() or ""
        txt = normalize_text(raw)
        if not txt:
            empty_pages += 1
        pages.append({"page": i, "text": txt})

    stats = {
        "pages_total": len(reader.pages),
        "pages_empty": empty_pages,
    }
    return pages, stats


def load_catalog(catalog_path: Path) -> dict[str, Any]:
    data = json.loads(catalog_path.read_text(encoding="utf-8"))
    if "items" not in data or not isinstance(data["items"], list):
        raise ValueError("catalog.json must contain an 'items' list")
    # determinismo: ordina per doc_id
    data["items"].sort(key=lambda x: x.get("doc_id", ""))
    return data


def env_fingerprint() -> dict[str, Any]:
    def _run(cmd: list[str]) -> str:
        try:
            return subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True).strip()
        except Exception:
            return ""

    return {
        "timestamp_utc": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "python_version": sys.version,
        "platform": platform.platform(),
        "git_commit": _run(["git", "rev-parse", "HEAD"]),
        "git_branch": _run(["git", "rev-parse", "--abbrev-ref", "HEAD"]),
        "pip_freeze": _run([sys.executable, "-m", "pip", "freeze"]),
    }


def iter_items(catalog: dict[str, Any]) -> Iterable[dict[str, Any]]:
    for it in catalog["items"]:
        yield it


def resolve_source_path(repo_root: Path, item: dict[str, Any]) -> Path | None:
    sp = item.get("source_path")
    if not sp:
        return None
    p = Path(sp)
    if p.is_absolute():
        return p
    return (repo_root / p).resolve()


def make_chunk_payload(item: dict[str, Any], page_meta: dict[str, Any], chunk: dict[str, Any]) -> dict[str, Any]:
    # Copia metadati rilevanti dall'item; evita campi potenzialmente grandi o non serializzabili
    keep_fields = [
        "doc_id", "title", "source_family", "doc_type", "authority_level", "jurisdiction",
        "language", "publication_date", "effective_date", "version_kind", "standard_codes",
        "license_class", "redistribution_allowed", "source_path", "source_url",
        "retrieval_date", "sha256", "notes"
    ]
    base = {k: item.get(k) for k in keep_fields if k in item}

    payload = {
        **base,
        **{k: v for k, v in page_meta.items() if k != "text"},
        "chunk_index": chunk["chunk_index"],
        "start_char": chunk["start_char"],
        "end_char": chunk["end_char"],
        "chunk_sha256": chunk["chunk_sha256"],
        "text": chunk["text"],
    }
    return payload
