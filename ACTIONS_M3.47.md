# ACTIONS_M3.47.md

## Obiettivo
Introdurre un benchmark/regression harness minimale per rieseguire casi benchmark e salvare output strutturati.

## Moduli introdotti
- `src/benchmark/models.py`
- `src/benchmark/serializers.py`
- `src/benchmark/runner.py`
- `src/benchmark/__init__.py`
- `apps/run_benchmark_smoke.py`

## Esito atteso
Possibilità di eseguire un piccolo set di benchmark locali tramite `run_query` e salvare i risultati in JSON.
