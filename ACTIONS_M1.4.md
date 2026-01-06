# ACTIONS_M1.4.md
Milestone: M1.4 — Qdrant indexing (Ollama embeddings, deterministic IDs)  
Data: 2026-01-06 (Europe/Rome)  
Branch: `feat/m1.4-qdrant-indexing`  
Repo: `~/Tesi/IIAA`

## Obiettivo
Indicizzare i chunk prodotti da M1.3 in una collezione Qdrant, utilizzando embeddings via Ollama, con:
- ID deterministici (idempotenza/upsert ripetibile).
- Gestione robusta dei limiti di contesto del modello embedding.
- Metaprodotti di audit: manifest e error log JSONL.

## Pre-requisiti (runtime)
1) Attivazione ambiente
```bash
cd ~/Tesi/IIAA
source .venv/bin/activate
```

2) Verifica `.env`
```bash
ls -lah .env
python -c "import os; from dotenv import load_dotenv; load_dotenv(); print('QDRANT_URL=', os.getenv('QDRANT_URL')); print('QDRANT_COLLECTION=', os.getenv('QDRANT_COLLECTION')); print('OLLAMA_BASE_URL=', os.getenv('OLLAMA_BASE_URL')); print('OLLAMA_EMBED_MODEL=', os.getenv('OLLAMA_EMBED_MODEL')); print('OLLAMA_CHAT_MODEL_FAST=', os.getenv('OLLAMA_CHAT_MODEL_FAST')); print('OLLAMA_CHAT_MODEL_QUALITY=', os.getenv('OLLAMA_CHAT_MODEL_QUALITY'))"
```

Valori attesi (esempio):
- `QDRANT_URL=http://localhost:6333`
- `OLLAMA_BASE_URL=http://localhost:11434`
- `OLLAMA_EMBED_MODEL=mxbai-embed-large`
- `QDRANT_COLLECTION=tesi_mvp_ifrs_v01`

3) Verifica Ollama attivo + modello embedding disponibile
```bash
curl -s "http://localhost:11434/api/tags" | head -n 60
ollama list | head -n 50
```

4) Verifica Qdrant attivo
```bash
curl -s "http://localhost:6333/collections"
```

## (Opz.) Pulizia collezioni Qdrant precedenti
```bash
curl -s -X DELETE "http://localhost:6333/collections/<NOME_COLLEZIONE>" | head
curl -s "http://localhost:6333/collections" | head
```

## Implementazione indexer (apps/index_qdrant.py)
- Creato/aggiunto lo script `apps/index_qdrant.py`.
- Installate dipendenze necessarie (Qdrant client + requests/httpx ecc.).
- Successivamente applicato fix robusto per:
  - errore Ollama embedding: `the input length exceeds the context length`
  - truncation + retry adattivo
  - file di error log JSONL per chunk eventualmente saltati
  - manifest JSON di indicizzazione

Comandi tipici:
```bash
python -m compileall apps/index_qdrant.py
git add apps/index_qdrant.py requirements.txt
git commit -m "feat(index): add Qdrant indexer (Ollama embeddings, deterministic IDs)"
# (poi) commit fix robustezza embedding / metaprodotti
git add apps/index_qdrant.py
git commit -m "fix(index): handle embedding context limits + robust outputs"
```

## Smoke test indicizzazione (limit 200)
```bash
python apps/index_qdrant.py   --chunks data/processed/ingestion/chunks_20260106_030806.jsonl   --recreate   --limit 200   --batch 16
```

Risultato atteso:
- `total_read=200`
- `total_upserted=200`
- `total_skipped=0`

Verifica error log:
```bash
wc -l data/processed/ingestion/index_errors_*.jsonl
head -n 3 data/processed/ingestion/index_errors_*.jsonl
```
Atteso (run riuscita): `0` righe.

## Full run indicizzazione (3037 chunk)
```bash
python apps/index_qdrant.py   --chunks data/processed/ingestion/chunks_20260106_030806.jsonl   --recreate   --batch 64
```

Output osservato:
- `total_read=3037`
- `total_upserted=3037`
- `total_skipped=0`
- `max_chars=1200`
- error log presente ma vuoto (0 righe)

Metaprodotti generati (NON versionati, perché sotto `data/processed/...`):
- `data/processed/ingestion/index_manifest_<timestamp>.json`
- `data/processed/ingestion/index_errors_<timestamp>.jsonl` (vuoto se nessun errore)

## Verifica finale in Qdrant
1) Elenco collezioni:
```bash
curl -s "http://localhost:6333/collections" | python -m json.tool
```

2) Conteggio punti (via client):
```bash
python - <<'PY'
import os
from dotenv import load_dotenv
from qdrant_client import QdrantClient
load_dotenv(".env")
client = QdrantClient(url=os.environ["QDRANT_URL"])
col = os.environ["QDRANT_COLLECTION"]
info = client.get_collection(col)
print("collection:", col)
print("points_count:", info.points_count)
PY
```

Atteso: `points_count ≈ 3037` (coerente con i chunk M1.3).

## Note operative (lezioni apprese)
- L’errore HTTP 500 su `/api/embeddings` era deterministico e dovuto al limite di contesto del modello embedding.
- La soluzione stabile è gestire truncation + retry adattivo e produrre un error log JSONL per audit.
- Evitare paste “lunghi” in zsh: preferire patch file o script locali applicati con comandi brevi.

## Stato
M1.4 completato con indicizzazione completa e zero chunk saltati.
