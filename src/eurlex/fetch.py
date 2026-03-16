from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from src.fetch.eurlex import fetch_html


def load_sources(path: Path) -> List[Dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data["sources"]


def safe_name(s: str) -> str:
    return "".join(c if c.isalnum() or c in ("-", "_", ".") else "_" for c in s)


def write_manifest(out_dir: Path, ts: str, fetched: list, failed: list, suffix: str = "") -> Path:
    name = f"manifest.{ts}{suffix}.json"
    p = out_dir / name
    p.write_text(
        json.dumps({"downloaded_at_utc": ts, "fetched": fetched, "failed": failed}, indent=2),
        encoding="utf-8",
    )
    return p


__all__ = [
    "fetch_html",
    "load_sources",
    "safe_name",
    "write_manifest",
]
