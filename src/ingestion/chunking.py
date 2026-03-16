from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .hashing import sha256_text


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
