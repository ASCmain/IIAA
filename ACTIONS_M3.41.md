# ACTIONS_M3.41.md

## Obiettivo
Modularizzare `src/ingestion/deterministic.py` mantenendo compatibilità con `apps/ingest_deterministic.py`.

## Moduli introdotti
- `src/ingestion/hashing.py`
- `src/ingestion/textnorm.py`
- `src/ingestion/chunking.py`
- `src/ingestion/pdf_io.py`
- `src/ingestion/catalog.py`
- `src/ingestion/payloads.py`
- `src/ingestion/__init__.py`

## Compatibilità
- `src/ingestion/deterministic.py` resta facade compatibile.
- `apps/ingest_deterministic.py` non cambia import in questa fase.
