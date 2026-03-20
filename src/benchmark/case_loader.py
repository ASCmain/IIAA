from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import BenchmarkCase


def load_benchmark_cases(path: str | Path) -> list[BenchmarkCase]:
    p = Path(path)
    data: dict[str, Any] = json.loads(p.read_text(encoding="utf-8"))
    raw_cases = data.get("cases") or []

    out: list[BenchmarkCase] = []
    for row in raw_cases:
        if not isinstance(row, dict):
            continue
        out.append(
            BenchmarkCase(
                case_id=str(row.get("case_id") or "").strip(),
                label=str(row.get("label") or "").strip(),
                query=str(row.get("query") or "").strip(),
                lang_mode=str(row.get("lang_mode") or "IT").strip(),
                top_k=int(row.get("top_k") or 5),
                score_threshold=float(row.get("score_threshold") or 0.0),
                embed_max_chars=int(row.get("embed_max_chars") or 6000),
                temperature=float(row.get("temperature") or 0.0),
            )
        )

    return [c for c in out if c.case_id and c.label and c.query]
