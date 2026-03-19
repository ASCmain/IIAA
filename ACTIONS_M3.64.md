# ACTIONS_M3.64

## Oggetto
Abilitazione della telemetria standard di progetto nello smoke benchmark.

## Intervento
È stato integrato `src.telemetry.TelemetryRecorder` in `apps/run_benchmark_smoke.py` usando le API standard:
- `start(inputs=..., extra=...)`
- `event(name, **fields)`
- `span(name, **fields)`
- `finalize(outputs=..., inputs=..., extra=...)`

## Copertura introdotta
Sono stati aggiunti:
- span `bootstrap`
- span `run_benchmark_cases`
- span `build_summary`
- span `write_outputs`

Sono stati aggiunti anche eventi:
- `phase_start`
- `phase_done`
- `case_result`

## Output
Il run produce ora:
- artifact benchmark in `debug_dump/benchmark_runs/smoke_<run_id>/`
- telemetria standard in `telemetry/benchmark_smoke/run_<timestamp>.json`

## Beneficio
Questa tranche rende osservabile la performance dello smoke benchmark secondo lo standard del progetto, senza modificare ancora il core del runner.

