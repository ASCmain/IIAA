# ACTIONS_M3.57.md

## Obiettivo
Correggere il NameError `_PlanShim` in `src/rag/evidence_classifier.py`.

## Causa
La funzione `_build_prompt()` usa `_PlanShim(plan)` per classificare i tier delle evidenze,
ma la classe `_PlanShim` non è stata inserita correttamente nel file.

## Esito atteso
Ripristinare il funzionamento del classifier LLM in modalità `assist`.
