# ACTIONS_M3.65

## Oggetto
Telemetria live per singolo case nel benchmark smoke.

## Intervento
È stato esteso `src/benchmark/runner.py` con un callback opzionale `progress_cb` che emette:
- `case_start`
- `case_done`

Per ogni case viene misurato anche:
- `case_total_ms`

Il wrapper `apps/run_benchmark_smoke.py` usa tale callback per:
- registrare eventi telemetry live;
- mostrare progress bar reale durante l'esecuzione dei case;
- preservare gli artifact già prodotti in `debug_dump/benchmark_runs/...` e `telemetry/benchmark_smoke/...`.

## Evidenza
Nel run telemetry risultano ora eventi per-case:
- `case_start` con `case_id`, `idx`, `total`, `label`, `lang_mode`, `top_k`
- `case_done` con `citations_count`, `evidences_count`, `classifier_items_count`, `answer_len`, `case_total_ms`

## Tempi osservati
Esempio run `20260319_004032Z`:
- `pw_ifrs9_7_reg_2025_1266_main_changes`: 16084 ms
- `pw_ifrs7_reg_2025_1266_disclosure_transition`: 20388 ms
- `pw_ias36_mvp_smoke`: 17649 ms

## Beneficio
Questa tranche sposta l'osservabilità dal solo wrapper esterno al livello del runner, rendendo il benchmark più utile per:
- audit tecnico;
- confronto prestazionale per-case;
- futura progress bar più granulare;
- analisi architetturale del costo di retrieval, classifier e generazione.

