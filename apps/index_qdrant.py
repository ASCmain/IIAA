from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams, PointStruct

from src.telemetry import TelemetryRecorder


def utc_now_z() -> str:
    # ISO8601 in UTC with Z suffix, seconds precision
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def get_git_commit() -> str | None:
    """Return current git commit hash (short) if available."""
    try:
        out = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], stderr=subprocess.DEVNULL)
        return out.decode("utf-8").strip()
    except Exception:
        return None


def ollama_embed(base_url: str, model: str, text: str, max_chars: int = 1200) -> list[float]:
    """Call Ollama embeddings with defensive truncation.

    Some embedding models enforce a context window. We truncate by characters and
    retry with progressive shrinking if Ollama returns a context-length error.
    """
    if text is None:
        text = ""

    # Remove NULs (can break downstream tools / payloads)
    text = text.replace("\x00", " ")

    prompt = text[:max_chars]

    last_body = ""
    for _ in range(8):
        r = requests.post(
            f"{base_url}/api/embeddings",
            json={"model": model, "prompt": prompt},
            timeout=120,
        )

        if r.status_code < 400:
            data = r.json()
            return data["embedding"]

        try:
            last_body = (r.text or "")[:400]
        except Exception:
            last_body = ""

        # Known Ollama error for embedding context overflow
        if "exceeds the context length" in last_body.lower():
            if len(prompt) <= 200:
                break
            prompt = prompt[: max(200, int(len(prompt) * 0.60))]
            continue

        # Other errors: raise
        r.raise_for_status()

    raise RuntimeError(f"ollama embeddings failed (context overflow): {last_body}")


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


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--chunks", required=True, help="Path to chunks_*.jsonl")
    ap.add_argument("--collection", default="", help="Override QDRANT_COLLECTION from .env")
    ap.add_argument("--recreate", action="store_true")
    ap.add_argument("--limit", type=int, default=0, help="Index only first N chunks (0 = all)")
    ap.add_argument("--batch", type=int, default=64)
    ap.add_argument("--max-chars", type=int, default=1200, help="Max chars per chunk sent to embedding model")
    ap.add_argument("--out-manifest", dest="out_manifest", default="", help="Path for index manifest json")
    ap.add_argument("--out-errors", dest="out_errors", default="", help="Path for per-chunk indexing errors jsonl")
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

    # Telemetry (timing + process RSS peak) — controlled by TELEMETRY_ENABLED/TELEMETRY_DIR
    tm = TelemetryRecorder(step="index_qdrant")
    git_commit = get_git_commit()
    tm.start(inputs={
        "chunks_file": str(chunks_path),
        "collection": collection,
        "qdrant_url": qdrant_url,
        "ollama_base_url": ollama_base,
        "embed_model": embed_model,
        "batch": int(args.batch),
        "limit": int(args.limit),
        "max_chars": int(args.max_chars),
        "recreate": bool(args.recreate),
    })
    _t_progress0 = time.perf_counter()
    started = utc_now_z()
    try:
    
        # Determine output paths early (so we can log errors even if indexing fails mid-way)
        default_dir = Path("data/processed/ingestion")
        default_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
        out_manifest = (args.out_manifest or "").strip() or str(default_dir / f"index_manifest_{stamp}.json")
        out_errors = (args.out_errors or "").strip() or str(default_dir / f"index_errors_{stamp}.jsonl")
    
        out_manifest_path = Path(out_manifest).resolve()
        out_manifest_path.parent.mkdir(parents=True, exist_ok=True)
        out_errors_path = Path(out_errors).resolve()
        out_errors_path.parent.mkdir(parents=True, exist_ok=True)
    
        # Detect vector size from one embedding call (short prompt)
        with tm.span("probe_embedding"):
            probe = ollama_embed(ollama_base, embed_model, "vector_size_probe", max_chars=64)
        with tm.span("ensure_collection", recreate=bool(args.recreate)):
            ensure_collection(client, collection, vector_size=len(probe), recreate=args.recreate)
    
        total = 0
        upserted = 0
        skipped = 0
    
        points: list[PointStruct] = []
    
        def flush() -> None:
            nonlocal upserted, points
            if not points:
                return
            with tm.span("qdrant_upsert", n_points=len(points), collection=collection):
                client.upsert(collection_name=collection, points=points)
            upserted += len(points)
            points = []
    
        with tm.span("index_chunks", batch=int(args.batch), limit=int(args.limit)):
            with out_errors_path.open("w", encoding="utf-8") as err_fp:
                with chunks_path.open("r", encoding="utf-8") as f:
                    for line in f:
                        if args.limit and total >= args.limit:
                            break
                        line = line.strip()
                        if not line:
                            continue

                        obj = json.loads(line)
                        total += 1

                        if total % 200 == 0:
                            elapsed = time.perf_counter() - _t_progress0
                            rate = (total / elapsed) if elapsed > 0 else None
                            tm.event("progress", total=total, upserted=upserted, skipped=skipped, chunks_per_s=rate)
                            if rate is not None:
                                print(f"progress: total={total} upserted={upserted} skipped={skipped} rate={rate:.2f} chunks/s")
                            else:
                                print(f"progress: total={total} upserted={upserted} skipped={skipped}")

                        doc_id = obj.get("doc_id", "")
                        page = int(obj.get("page", 0))
                        chunk_sha256 = obj.get("chunk_sha256", "")

                        pid = stable_point_id(doc_id, page, chunk_sha256)
                        text = obj.get("text", "")

                        try:
                            vec = ollama_embed(ollama_base, embed_model, text, max_chars=args.max_chars)
                        except Exception as e:
                            skipped += 1
                            err = {
                                "doc_id": doc_id,
                                "page": page,
                                "chunk_sha256": chunk_sha256,
                                "text_len": len(text or ""),
                                "error": str(e),
                            }
                            err_fp.write(json.dumps(err, ensure_ascii=False) + "\n")
                            continue

                        # Keep full text in payload for grounding
                        payload = obj

                        points.append(PointStruct(id=pid, vector=vec, payload=payload))

                        if len(points) >= args.batch:
                            flush()

            flush()
    
        ended = utc_now_z()
        manifest = {
            "started_utc": started,
            "ended_utc": ended,
            "collection": collection,
            "qdrant_url": qdrant_url,
            "embed_model": embed_model,
            "chunks_file": str(chunks_path),
            "total_read": total,
            "total_upserted": upserted,
            "total_skipped": skipped,
            "batch": args.batch,
            "max_chars": args.max_chars,
            "recreate": bool(args.recreate),
            "errors_file": str(out_errors_path),
            "manifest_file": str(out_manifest_path),
        }
    
        # Qdrant collection stats (post-index)
        try:
            info = client.get_collection(collection)
            points_count = getattr(info, "points_count", None)
        except Exception:
            points_count = None

        try:
            telemetry_file = tm.finalize(
                outputs={
                    "total_read": total,
                    "total_upserted": upserted,
                    "total_skipped": skipped,
                    "points_count": points_count,
                    "errors_file": str(out_errors_path),
                    "manifest_file": str(out_manifest_path),
                },
                git_commit=git_commit,
            )
        except Exception:
            telemetry_file = None
        manifest["telemetry_file"] = str(telemetry_file) if telemetry_file else None
        manifest["points_count"] = points_count

        out_manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(json.dumps(manifest, indent=2, ensure_ascii=False))
    
    
    except Exception as e:
        tm.finalize(outputs={"error": repr(e)}, git_commit=git_commit)
        raise

if __name__ == "__main__":
    main()