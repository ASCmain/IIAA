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

