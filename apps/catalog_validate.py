from __future__ import annotations

import json
import sys
from pathlib import Path

REQUIRED = [
    "doc_id", "standard", "title", "authors", "publisher",
    "publication_date", "accessed_at", "language", "local_path", "checksum_sha256"
]

def main() -> None:
    path = Path(sys.argv[1] if len(sys.argv) > 1 else "corpus/catalog/catalog.json")
    data = json.loads(path.read_text(encoding="utf-8"))
    docs = data.get("documents", [])
    seen = set()
    errors = 0

    for d in docs:
        doc_id = d.get("doc_id")
        if not doc_id:
            print("ERROR: missing doc_id")
            errors += 1
            continue
        if doc_id in seen:
            print(f"ERROR: duplicate doc_id: {doc_id}")
            errors += 1
        seen.add(doc_id)

        for k in REQUIRED:
            if k not in d or d[k] in ("", None, []):
                print(f"ERROR: {doc_id}: missing/empty {k}")
                errors += 1

        if not str(d.get("local_path", "")).startswith("corpus/original/"):
            print(f"ERROR: {doc_id}: local_path must start with corpus/original/")
            errors += 1

    if errors:
        print(f"Validation FAILED: {errors} error(s)")
        sys.exit(1)

    print(f"Validation OK: {len(docs)} document(s)")
