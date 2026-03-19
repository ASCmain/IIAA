# ACTIONS_M3.55.md

## Obiettivo
Promuovere il classificatore LLM da `shadow` a `assist` leggero.

## Regola
La source policy metadata-driven resta primaria.
Il classificatore LLM può solo rifinire i bucket finali:
- `core` resta candidato a core
- `context` viene spostato in context
- `exclude` viene escluso dai core e, di norma, anche dal context finale

## File coinvolti
- `src/rag/orchestrator.py`

## Esito atteso
Rendere operativo il doppio canale:
- policy normativa/metadata-driven
- assistenza semantica locale LLM-based
