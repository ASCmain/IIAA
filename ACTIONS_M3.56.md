# ACTIONS_M3.56.md

## Obiettivo
Arricchire il payload del classifier LLM con metadata e segnali derivati, e ampliare il budget di contesto
per quesiti interpretativi e numerici.

## File coinvolti
- `src/rag/evidence_classifier.py`
- `src/rag/orchestrator.py`

## Razionale
Il classifier deve giudicare le evidenze su un pacchetto informativo più ricco del solo snippet testuale.
