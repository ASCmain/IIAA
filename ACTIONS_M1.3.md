# ACTIONS — M1.3 — Ingestion deterministica (catalog-driven)
Data: 2026-01-06
Branch: feat/m1.3-deterministic-ingestion

## Run (dry-run)
- run_id: 20260106_030702
- indexed_items: 4
- skipped_items: 6
- total_chunks: 3037
- total_chars: 4081959
- warnings: 0

## Run (full)
- run_id: 20260106_030806
- chunks_path: data/processed/ingestion/chunks_20260106_030806.jsonl (~6.8 MB)
- manifest_path: data/processed/ingestion/manifest_20260106_030806.json
- fingerprint_path: data/processed/ingestion/fingerprint_20260106_030806.json
- indexed_items: 4
- skipped_items: 6
- total_chunks: 3037
- total_chars: 4081959
- warnings: 0

## Comandi eseguiti (estratto)
- source .venv/bin/activate
- python -m pip install pypdf python-docx beautifulsoup4 lxml
- python apps/ingest_deterministic.py --catalog corpus/catalog/catalog.json --out-dir data/processed/ingestion --dry-run
- python apps/ingest_deterministic.py --catalog corpus/catalog/catalog.json --out-dir data/processed/ingestion

## Output prodotti
- data/processed/ingestion/* (derivati, non versionati; tracciati tramite manifest+fingerprint)
