# ACTIONS_M3.72

## Oggetto
Correzione dell'osservabilità focus e della fidelity del tracker citazionale.

## Interventi
- propagazione dei campi focus dal payload RAG ai risultati benchmark;
- correzione di `_extract_used_citations` per ignorare il blocco finale "Citations used";
- miglioramento della misurabilità dei casi P5, P8, P9.

## Razionale
La tranche precedente aveva introdotto la focus detection nel RAG, ma i segnali non risultavano osservabili in `results.jsonl`.
Inoltre il conteggio delle citazioni usate era contaminato dal riepilogo finale, rendendo poco affidabile l'indicatore `used_citations_count`.

## Beneficio
- benchmark più auditabile;
- miglior separazione tra citazioni realmente usate nel corpo e citazioni solo riepilogate;
- base più solida per valutare la qualità del grounding.
