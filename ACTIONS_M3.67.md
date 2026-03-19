# ACTIONS_M3.67

## Oggetto
Micro-fix UX del benchmark smoke e allineamento documentale dell'architettura Advanced RAG.

## Intervento applicativo
Nel benchmark smoke:
- corretta la progress bar del `case_start` per evitare l'avvio mostrato come `0/N`;
- aggiunti aggregati sintetici nel `summary.json`:
  - distribuzione dei `question_type`
  - statistiche sintetiche sui `case_total_ms` (`count`, `min`, `max`, `avg`)

## Intervento documentale
Sono stati aggiornati:
- `ARCHITECTURE_GUIDE.md`
- `docs/ADVANCED_RAG_POLICY.md`

### Contenuti introdotti
- classifier locale con modalità `off`, `shadow`, `assist`;
- ruolo conservativo della modalità `assist`;
- analysis pool adattivo con `analysis_pool_target`, `min_candidate_floor`, `threshold_fallback_ladder`;
- benchmark smoke come componente osservabile con telemetria standard di progetto;
- segnali architetturali per-case e artifact di run.

## Beneficio
Questa tranche migliora:
- leggibilità operativa del benchmark;
- auditabilità architetturale;
- coerenza tra implementazione reale, variabili ambiente e documentazione tecnica.

