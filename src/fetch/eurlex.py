from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import requests


@dataclass(frozen=True)
class FetchResult:
    url: str
    status_code: int
    sha256: str
    saved_path: str
    bytes: int


def _sha256_bytes(b: bytes) -> str:
    h = hashlib.sha256()
    h.update(b)
    return h.hexdigest()


def fetch_html(
    url: str,
    out_path: str,
    user_agent: Optional[str] = None,
    timeout_s: int = 30,
    retries: int = 3,
    backoff_s: float = 1.2,
) -> FetchResult:
    """
    Download an EUR-Lex HTML page, save it, and return sha256.
    out_path: filesystem path where the HTML will be saved.
    """
    headers = {}
    if user_agent:
        headers["User-Agent"] = user_agent

    last_exc: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            r = requests.get(url, headers=headers, timeout=timeout_s)
            content = r.content
            sha = _sha256_bytes(content)

            p = Path(out_path)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(content)

            return FetchResult(
                url=url,
                status_code=r.status_code,
                sha256=sha,
                saved_path=str(p),
                bytes=len(content),
            )
        except Exception as e:
            last_exc = e
            if attempt < retries:
                time.sleep(backoff_s * attempt)
            else:
                raise RuntimeError(f"fetch_html failed after {retries} attempts: {url}") from last_exc

    raise RuntimeError("unreachable")
