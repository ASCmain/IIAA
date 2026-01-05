from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Europe/Rome")

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def load_catalog(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Catalog not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))

def save_catalog(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

def main() -> None:
    ap = argparse.ArgumentParser(description="Add a document entry to corpus catalog (APA-ready).")
    ap.add_argument("--catalog", default="corpus/catalog/catalog.json")
    ap.add_argument("--doc-id", required=True)
    ap.add_argument("--standard", required=True)
    ap.add_argument("--title", required=True)
    ap.add_argument("--author", action="append", required=True, help="Repeatable. Example: --author 'IFRS Foundation'")
    ap.add_argument("--publisher", required=True)
    ap.add_argument("--publication-date", required=True, help="YYYY or YYYY-MM-DD")
    ap.add_argument("--language", required=True, choices=["en", "it"])
    ap.add_argument("--local-path", required=True, help="Relative path under corpus/original/, e.g. corpus/original/IAS36.pdf")
    ap.add_argument("--source-url", default="")
    ap.add_argument("--notes", default="")
    args = ap.parse_args()

    catalog_path = Path(args.catalog)
    local_path = Path(args.local_path)

    if not local_path.exists():
        raise FileNotFoundError(f"Local file not found: {local_path}")

    checksum = sha256_file(local_path)
    accessed_at = datetime.now(TZ).isoformat(timespec="seconds")

    cat = load_catalog(catalog_path)
    docs = cat.get("documents", [])

    # prevent duplicates by doc_id
    if any(d.get("doc_id") == args.doc_id for d in docs):
        raise ValueError(f"doc_id already exists in catalog: {args.doc_id}")

    entry = {
        "doc_id": args.doc_id,
        "standard": args.standard,
        "title": args.title,
        "authors": args.author,
        "publisher": args.publisher,
        "publication_date": args.publication_date,
        "source_url": args.source_url,
        "accessed_at": accessed_at,
        "language": args.language,
        "local_path": str(local_path),
        "checksum_sha256": checksum,
        "notes": args.notes,
    }

    docs.append(entry)
    cat["documents"] = docs
    cat["generated_at"] = datetime.now(TZ).date().isoformat()

    save_catalog(catalog_path, cat)
    print(f"Added: {args.doc_id}")
    print(f"SHA256: {checksum}")
    print(f"Accessed at: {accessed_at}")

if __name__ == "__main__":
    main()
