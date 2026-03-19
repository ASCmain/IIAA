# CHANGELOG

Append-only. Ogni modifica che impatta file/struttura/comportamento deve essere tracciata qui.

## [Unreleased]
- Initial scaffolding.

## [Unreleased]
- docs: aggiunta Model Policy e ruoli modello in .env.example (M1 freeze, local-only).

## [Unreleased]
- corpus: aggiunta struttura corpus e catalogo bibliografico APA-ready (catalog.json + schema) con tool di add/validate.

## Unreleased
- Fix: add missing dependency  required by telemetry logging.

## [Unreleased]

### Fixed
- robustito il parsing degli output JSON troncati del classifier LLM locale (`src/rag/evidence_classifier.py`);
- reso osservabile il classifier in modalità `assist`, con persistenza di `classifier_items_count`, `classifier_label_counts` e `classifier_raw_response`;
- corretto il recovery del caso `transition_disclosure` in cui l'LLM produceva array `items` con ultimo oggetto non chiuso.

### Changed
- estesa la telemetria del benchmark smoke con metriche su retrieval, soglie adattive, analysis pool, classifier e tempi per fase;
- migliorata la leggibilità diagnostica del run `smoke_*` per audit tecnico del layer Advanced RAG.


### Added
- integrazione della telemetria standard di progetto nello smoke benchmark (`apps/run_benchmark_smoke.py`);
- emissione di run telemetry in `telemetry/benchmark_smoke/run_*.json`;
- progress bar testuale per fasi e stampa risultati dello smoke run.


### Added
- telemetria live per singolo case nel benchmark smoke tramite callback `progress_cb` in `src/benchmark/runner.py`;
- registrazione di eventi `case_start` e `case_done` con `case_total_ms` nel run telemetry.


### Added
- arricchimento degli eventi `case_done` del benchmark smoke con segnali architetturali per-case (`question_type`, `source_preference`, `target_standards`, `analysis_pool_count`, `analysis_pool_target`, `threshold_effective`, `core_evidences_count`, `context_evidences_count`).


### Added
- micro-fix UX della progress bar del benchmark smoke per il primo `case_start`;
- aggregati sintetici nel `summary.json` dello smoke benchmark (`question_type_counts`, statistiche `case_total_ms`);
- allineamento documentale di `ARCHITECTURE_GUIDE.md` e `docs/ADVANCED_RAG_POLICY.md` rispetto a classifier locale, analysis pool adattivo e benchmark telemetry.

