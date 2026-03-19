# ACTIONS_M3.66

## Oggetto
Arricchimento della telemetria per-case con segnali architetturali del benchmark smoke.

## Intervento
Sono stati estesi gli eventi `case_done` per includere, oltre ai tempi:
- `question_type`
- `source_preference`
- `target_standards`
- `analysis_pool_count`
- `analysis_pool_target`
- `threshold_effective`
- `core_evidences_count`
- `context_evidences_count`

## Beneficio
La telemetria del benchmark smoke non misura più solo la durata del case, ma anche il profilo architetturale della risposta. Questo migliora:
- auditabilità;
- confronto tra casi;
- base dati per benchmarking metodologico in appendice tecnica.

