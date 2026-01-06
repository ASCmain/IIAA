from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from src.ingestion.deterministic import (
    ChunkSpec,
    env_fingerprint,
    iter_items,
    load_catalog,
    make_chunk_payload,
    read_pdf_pages,
    resolve_source_path,
    sha256_text,
    chunk_text,
)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--catalog", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--run-id", default="")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--max-chars", type=int, default=1800)
    ap.add_argument("--overlap-chars", type=int, default=200)
    args = ap.parse_args()

    repo_root = Path(".").resolve()
    catalog_path = (repo_root / args.catalog).resolve()
    out_dir = (repo_root / args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    run_id = args.run_id or datetime.now().strftime("%Y%m%d_%H%M%S")
    chunks_path = out_dir / f"chunks_{run_id}.jsonl"
    manifest_path = out_dir / f"manifest_{run_id}.json"
    errors_path = out_dir / f"errors_{run_id}.jsonl"
    fingerprint_path = out_dir / f"fingerprint_{run_id}.json"

    catalog = load_catalog(catalog_path)
    spec = ChunkSpec(max_chars=args.max_chars, overlap_chars=args.overlap_chars)

    fp = env_fingerprint()
    fingerprint_path.write_text(json.dumps(fp, indent=2, ensure_ascii=False), encoding="utf-8")

    total_items = 0
    indexed_items = 0
    skipped_items = 0
    total_chunks = 0
    total_chars = 0
    warnings = 0

    # raccogli un piccolo report per dry-run
    preview = []

    def log_error(obj: dict):
        with errors_path.open("a", encoding="utf-8") as ef:
            ef.write(json.dumps(obj, ensure_ascii=False) + "\n")

    if not args.dry_run:
        # azzera eventuali log precedenti di questo run
        if errors_path.exists():
            errors_path.unlink(missing_ok=True)
        if chunks_path.exists():
            chunks_path.unlink(missing_ok=True)

    for item in iter_items(catalog):
        total_items += 1

        src_path = resolve_source_path(repo_root, item)
        if src_path is None:
            skipped_items += 1
            continue

        if not src_path.exists():
            skipped_items += 1
            log_error(
                {
                    "doc_id": item.get("doc_id"),
                    "error": "missing_source_file",
                    "source_path": str(src_path),
                }
            )
            continue

        # MVP: gestiamo PDF. Estendibile a DOCX/HTML in iterazioni successive.
        if src_path.suffix.lower() != ".pdf":
            skipped_items += 1
            log_error(
                {
                    "doc_id": item.get("doc_id"),
                    "error": "unsupported_file_type",
                    "source_path": str(src_path),
                    "suffix": src_path.suffix.lower(),
                }
            )
            continue

        try:
            pages, pdf_stats = read_pdf_pages(src_path)
        except Exception as e:
            skipped_items += 1
            log_error(
                {
                    "doc_id": item.get("doc_id"),
                    "error": "pdf_parse_failed",
                    "source_path": str(src_path),
                    "exception": repr(e),
                }
            )
            continue

        indexed_items += 1

        # warning se troppe pagine vuote
        if pdf_stats.get("pages_total", 0) > 0:
            empty_ratio = pdf_stats.get("pages_empty", 0) / pdf_stats["pages_total"]
            if empty_ratio > 0.2:
                warnings += 1
                log_error(
                    {
                        "doc_id": item.get("doc_id"),
                        "error": "warning_many_empty_pages",
                        "source_path": str(src_path),
                        "pages_total": pdf_stats["pages_total"],
                        "pages_empty": pdf_stats["pages_empty"],
                    }
                )

        # genera chunk pagina per pagina (più facile per citazioni)
        for p in pages:
            page_text = p.get("text", "")
            if not page_text:
                continue

            chunks = chunk_text(page_text, spec)
            total_chars += len(page_text)
            total_chunks += len(chunks)

            if args.dry_run and len(preview) < 3:
                preview.append(
                    {
                        "doc_id": item.get("doc_id"),
                        "page": p.get("page"),
                        "chunks_on_page": len(chunks),
                        "sample_chunk_sha256": chunks[0]["chunk_sha256"] if chunks else None,
                    }
                )

            if args.dry_run:
                continue

            with chunks_path.open("a", encoding="utf-8") as cf:
                for ch in chunks:
                    payload = make_chunk_payload(item, {"page": p.get("page")}, ch)
                    cf.write(json.dumps(payload, ensure_ascii=False) + "\n")

    manifest = {
        "run_id": run_id,
        "catalog_path": str(catalog_path),
        "out_dir": str(out_dir),
        "chunks_path": str(chunks_path),
        "errors_path": str(errors_path),
        "fingerprint_path": str(fingerprint_path),
        "total_items": total_items,
        "indexed_items": indexed_items,
        "skipped_items": skipped_items,
        "total_chunks": total_chunks,
        "total_chars": total_chars,
        "warnings": warnings,
        "dry_run_preview": preview,
    }

    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(manifest, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
