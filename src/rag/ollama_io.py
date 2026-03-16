from __future__ import annotations

from typing import List

import requests


def ollama_chat(base_url: str, model: str, prompt: str, temperature: float = 0.1) -> str:
    r = requests.post(
        f"{base_url}/api/generate",
        json={"model": model, "prompt": prompt, "stream": False, "options": {"temperature": temperature}},
        timeout=300,
    )
    r.raise_for_status()
    data = r.json()
    return (data.get("response") or "").strip()


def ollama_embed(base_url: str, model: str, text: str, max_chars: int = 6000) -> List[float]:
    text = (text or "").replace("\x00", " ")
    prompt = text[: max(1, int(max_chars))]
    r = requests.post(
        f"{base_url}/api/embeddings",
        json={"model": model, "prompt": prompt},
        timeout=180,
    )
    r.raise_for_status()
    data = r.json()
    return data["embedding"]
