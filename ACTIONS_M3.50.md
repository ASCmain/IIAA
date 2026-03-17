# ACTIONS_M3.50.md

## Obiettivo
Implementare la distinzione tra evidenze core e di contesto nel layer Advanced RAG.

## File coinvolti
- `src/rag/source_policy.py`
- `src/rag/prompting.py`
- `src/rag/orchestrator.py`

## Logica introdotta
- source policy con due bucket: `core_evidences` e `context_evidences`
- prompt grounded con doppia sezione
- tracciamento del numero di evidenze core/context nell'output

## Esito atteso
Aumentare il contesto disponibile per quesiti interpretativi e numerici senza perdere la priorità logica delle fonti.
