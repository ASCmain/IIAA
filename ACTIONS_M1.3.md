# ACTIONS — M1.3 — Ingestion deterministica (catalog-driven)
Data: 2026-01-06
Branch: feat/m1.3-deterministic-ingestion

## Comandi eseguiti
- source .venv/bin/activate
- python -m pip install pypdf python-docx beautifulsoup4 lxml
- (fix) apps/ingest_deterministic.py: sys.path repo root
- (fix) corpus/catalog/catalog.json normalizzato in formato root+items
- python apps/ingest_deterministic.py --catalog corpus/catalog/catalog.json --out-dir data/processed/ingestion --dry-run
- python apps/ingest_deterministic.py --catalog corpus/catalog/catalog.json --out-dir data/processed/ingestion

## Risultati dry-run (manifest)
- total_items: 10
- indexed_items: 4
- skipped_items: 6
- total_chunks: 3037
- total_chars: 4081959
- warnings: 0

## Output prodotti (non versionati, in gitignore)
- data/processed/ingestion/manifest_<run_id>.json
- data/processed/ingestion/chunks_<run_id>.jsonl
- data/processed/ingestion/errors_<run_id>.jsonl (se presente)
- data/processed/ingestion/fingerprint_<run_id>.json

## Note / anomalie
- Nessuna anomalia sul parsing PDF (warnings=0).
