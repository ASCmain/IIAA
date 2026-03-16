from __future__ import annotations

from typing import Any


def make_chunk_payload(item: dict[str, Any], page_meta: dict[str, Any], chunk: dict[str, Any]) -> dict[str, Any]:
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
