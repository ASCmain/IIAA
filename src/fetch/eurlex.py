from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

import requests


@dataclass(frozen=True)
class FetchResult:
    url: str
    status_code: int
    sha256: str
    saved_path: str
    bytes: int


ProgressCB = Callable[[str, dict], None]


def _sha256_bytes(b: bytes) -> str:
    h = hashlib.sha256()
    h.update(b)
    return h.hexdigest()


def _guess_accept_language(url: str) -> str:
    if "/IT/" in url:
        return "it-IT,it;q=0.9,en;q=0.6"
    if "/EN/" in url:
        return "en-GB,en;q=0.9,it;q=0.6"
    return "en-GB,en;q=0.9,it;q=0.6"


def _retry_after_seconds(headers: dict) -> float:
    ra = headers.get("Retry-After")
    if not ra:
        return 0.0
    try:
        return float(ra)
    except Exception:
        return 0.0


def fetch_html(
    url: str,
    out_path: str,
    user_agent: Optional[str] = None,
    timeout_s: int = 50,
    retries: int = 10,
    backoff_s: float = 2.0,
    min_bytes: int = 2000,
    progress: Optional[ProgressCB] = None,
) -> FetchResult:
    """
    Robust downloader for EUR-Lex HTML (and some PDFs).
    Success only if HTTP 200 and body >= min_bytes.
    Treat 202 as transient (EUR-Lex sometimes returns Accepted/processing).
    Retry on 202/429/5xx with backoff and optional Retry-After.
    """
    headers = {
        "Accept": "text/html,application/xhtml+xml,application/pdf;q=0.9,*/*;q=0.8",
        "Accept-Language": _guess_accept_language(url),
        "Connection": "keep-alive",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }
    if user_agent:
        headers["User-Agent"] = user_agent

    session = requests.Session()
    last_err: Exception | None = None

    for attempt in range(1, retries + 1):
        if progress:
            progress("attempt", {"attempt": attempt, "retries": retries})

        try:
            r = session.get(url, headers=headers, timeout=timeout_s, allow_redirects=True)
            status = r.status_code

            if status in (202, 429, 502, 503, 504):
                ra = _retry_after_seconds(r.headers)
                sleep_s = ra if ra > 0 else backoff_s * attempt
                sleep_s = min(sleep_s, 30.0)
                if progress:
                    progress("retry", {"status": status, "attempt": attempt, "sleep_s": sleep_s})
                time.sleep(sleep_s)
                raise RuntimeError(f"transient_http_{status}")

            if status != 200:
                raise RuntimeError(f"http_{status}")

            content = r.content or b""
            if len(content) < min_bytes:
                raise RuntimeError(f"body_too_small_{len(content)}")

            sha = _sha256_bytes(content)
            p = Path(out_path)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(content)

            if progress:
                progress("success", {"status": status, "bytes": len(content)})

            return FetchResult(
                url=url,
                status_code=status,
                sha256=sha,
                saved_path=str(p),
                bytes=len(content),
            )

        except KeyboardInterrupt:
            # propagate immediately
            raise
        except Exception as e:
            last_err = e
            if attempt < retries:
                # small extra delay to reduce rate limiting
                time.sleep(0.5)
                continue
            raise RuntimeError(f"fetch_html failed after {retries} attempts: {url} ({e})") from last_err

    raise RuntimeError("unreachable")
