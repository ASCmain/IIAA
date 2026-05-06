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


### Added
- distinzione tra `citations` candidate e `used_citations` effettivamente richiamate nel testo finale;
- nuovi segnali `used_citations_count` e `citation_candidates_count` nel benchmark smoke;
- visualizzazione in UI delle citazioni effettivamente usate per migliorare la citation fidelity.


### Added
- persistenza append-only per-case dei risultati benchmark in `results.jsonl`;
- supporto a esecuzione selettiva dei casi con `BENCHMARK_CASE_IDS`;
- supporto a `BENCHMARK_FAIL_FAST` per decidere se interrompere o proseguire dopo errori per-case.


### Added
- propagazione dei segnali di focus nei risultati benchmark;
- correzione del tracker `used_citations` per escludere il blocco finale di riepilogo citazioni.


### Added
- focus enforcement conservativo sul bucket `core/context`;
- serializzazione di `max_core`, `max_context` e `policy_trace` nel benchmark;
- miglioramento del tracker `used_citations` per varianti del blocco finale citazioni.


### Added
- semantic router locale embedding-based per il query planning;
- catalogo versionato degli intent semantici in `config/semantic_intent_catalog.json`.


### Added
- rafforzamento del primary-standard core enforcement;
- esposizione di `core_cite_keys` e `context_cite_keys` nel benchmark.


### Added
- primary-standard candidate gating prima dello split `core/context`.


### Added
- esportazione documentabile dei metadati della query embedding-based nel benchmark finale IIAA;
- generazione dell'appendice tecnica dei risultati benchmark IIAA;
- completamento del benchmark finale su 10 prompt senza errori runtime.


### Added
- esportazione documentabile dei metadati della query embedding-based nel benchmark finale IIAA;
- generazione dell'appendice tecnica dei risultati benchmark IIAA;
- completamento del benchmark finale su 10 prompt senza errori runtime;
- allineamento della documentazione architetturale su query compaction, subset benchmark execution ed export dei risultati.


### Added
- consolidamento del semantic router locale con catalogo intenti versionato;
- allineamento definitivo della suite benchmark `benchmark_prompts_v3_exact.json`;
- rifiniture finali di query planning, source policy, prompting e focus detection per il benchmark conclusivo.


## [Unreleased]
### Added
- Added Apache License 2.0 to the repository.
- Added NOTICE file for project attribution.
- Updated README with licensing and attribution guidance for public publication.
