from __future__ import annotations

import argparse
import json
import os
import uuid
from datetime import datetime
from pathlib import Path

import requests
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams


def ollama_embed(base_url: str, model: str, text: str) -> list[float]:
    r = requests.post(
        f"{base_url}/api/embeddings",
        json={"model": model, "prompt": text},
        timeout=120,
    )
    r.raise_for_status()
    data = r.json()
    return data["embedding"]


def stable_point_id(doc_id: str, page: int, chunk_sha256: str) -> str:
    name = f"{doc_id}|p{page}|{chunk_sha256}"
    return str(uuid.uuid5(uuid.NAMESPACE_URL, name))


def ensure_collection(client: QdrantClient, name: str, vector_size: int, recreate: bool = False) -> None:
    existing = [c.name for c in client.get_collections().collections]
    if recreate and name in existing:
        client.delete_collection(name)
        existing.remove(name)

    if name not in existing:
        client.create_collection(
            collection_name=name,
            vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
        )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--chunks", required=True, help="Path to chunks_*.jsonl")
    ap.add_argument("--collection", default="", help="Override QDRANT_COLLECTION from .env")
    ap.add_argument("--recreate", action="store_true")
    ap.add_argument("--limit", type=int, default=0, help="Index only first N chunks (0 = all)")
    ap.add_argument("--batch", type=int, default=64)
    ap.add_argument("--out-manifest", default="")
    args = ap.parse_args()

    load_dotenv(dotenv_path=Path(".env"))

    qdrant_url = os.environ["QDRANT_URL"]
    collection = args.collection or os.environ.get("QDRANT_COLLECTION", "iiaa_mvp_v01")
    ollama_base = os.environ["OLLAMA_BASE_URL"]
    embed_model = os.environ["OLLAMA_EMBED_MODEL"]

    client = QdrantClient(url=qdrant_url)

    chunks_path = Path(args.chunks).resolve()
    if not chunks_path.exists():
        raise SystemExit(f"Missing chunks file: {chunks_path}")

    # Detect vector size from one embedding call
    probe = ollama_embed(ollama_base, embed_model, "vector_size_probe")
    ensure_collection(client, collection, vector_size=len(probe), recreate=args.recreate)

    total = 0
    upserted = 0
    started = datetime.utcnow().isoformat(timespec="seconds") + "Z"

    ids: list[str] = []
    vecs: list[list[float]] = []
    payloads: list[dict] = []

    def flush():
        nonlocal upserted, ids, vecs, payloads
        if not ids:
            return
        client.upsert(collection_name=collection, points=list(zip(ids, vecs, payloads)))
        upserted += len(ids)
        ids, vecs, payloads = [], [], []

    with chunks_path.open("r", encoding="utf-8") as f:
        for line in f:
            if args.limit and total >= args.limit:
                break
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            total += 1

            doc_id = obj.get("doc_id", "")
            page = int(obj.get("page", 0))
            chunk_sha256 = obj.get("chunk_sha256", "")

            pid = stable_point_id(doc_id, page, chunk_sha256)
            text = obj["text"]
            vec = ollama_embed(ollama_base, embed_model, text)

            # Keep full text in payload for grounding
            payload = obj

            ids.append(pid)
            vecs.append(vec)
            payloads.append(payload)

            if len(ids) >= args.batch:
                flush()

    flush()

    ended = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    manifest = {
        "started_utc": started,
        "ended_utc": ended,
        "collection": collection,
        "qdrant_url": qdrant_url,
        "embed_model": embed_model,
        "chunks_file": str(chunks_path),
        "total_read": total,
        "total_upserted": upserted,
        "batch": args.batch,
        "recreate": bool(args.recreate),
    }

    out_manifest = args.out-manifest if hasattr(args, "out-manifest") else args.out_manifest
    out_manifest = (out_manifest or "").strip() or f"data/processed/ingestion/index_manifest_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    out_path = Path(out_manifest).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(json.dumps(manifest, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
