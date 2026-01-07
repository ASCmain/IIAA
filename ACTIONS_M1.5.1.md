# ACTIONS_M1.5.1 — Telemetria base su indicizzazione Qdrant

Data: 2026-01-07  
Branch: feat/m1.4-qdrant-indexing

## Obiettivo
Introdurre telemetria (tempo end-to-end, spans, RSS peak) e progress indicator per la fase di indexing su Qdrant.

## Modifiche
- Aggiunto modulo: `src/telemetry.py`
- Aggiornato `.gitignore` per ignorare output telemetria mantenendo versionati README e schemi
- Strumentato `apps/index_qdrant.py` con:
  - TelemetryRecorder(step="index_qdrant")
  - spans principali (read_chunks, upsert_qdrant)
  - progress log ogni 200 chunk con throughput (chunks/s)

## Comandi eseguiti
- cd ~/Tesi/IIAA
- source .venv/bin/activate
- pip install -U psutil
- python apps/index_qdrant.py --chunks data/processed/ingestion/chunks_20260106_030806.jsonl --batch 64

## Output / Risultati run
- total_read: 3037
- total_upserted: 3037
- skipped: 0
- durata: 2026-01-06T23:53:06Z → 2026-01-06T23:55:25Z (~139s)
- throughput: ~21.8–22.1 chunks/s
- telemetry_file: telemetry/index_qdrant/run_20260106_235306Z.json
- points_count: 3037
