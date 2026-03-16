from __future__ import annotations

import json
import platform
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable


def load_catalog(catalog_path: Path) -> dict[str, Any]:
    data = json.loads(catalog_path.read_text(encoding="utf-8"))
    if "items" not in data or not isinstance(data["items"], list):
        raise ValueError("catalog.json must contain an 'items' list")
    data["items"].sort(key=lambda x: x.get("doc_id", ""))
    return data


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
