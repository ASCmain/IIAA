# ACTIONS_M3.69

## Oggetto
Introduzione della citation fidelity: separazione tra citazioni candidate e citazioni effettivamente usate nel testo.

## File aggiornati
- `src/rag/orchestrator.py`
- `src/benchmark/models.py`
- `src/benchmark/runner.py`
- `apps/run_benchmark_smoke.py`
- `apps/PW_projectwork_ui_streamlit.py`

## Contenuto della tranche
- aggiunto estrattore delle citazioni effettivamente richiamate nella risposta;
- introdotti nel payload:
  - `used_citations`
  - `used_citations_count`
  - `citation_candidates_count`
- propagazione dei nuovi campi nel benchmark runner;
- inclusione dei nuovi segnali nel summary e nella telemetria dello smoke benchmark;
- visualizzazione in UI delle citazioni usate effettivamente.

## Razionale
Il blocco `Citations used` non deve coincidere automaticamente con l'intero set di evidenze finali.
Questa tranche migliora l'auditabilità della risposta distinguendo:
- evidenze candidate passate al prompt;
- citazioni realmente presenti nel testo generato.
