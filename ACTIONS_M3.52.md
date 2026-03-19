# ACTIONS_M3.52.md

## Obiettivo
Introdurre un pruning metadata-driven delle evidenze prima dello split core/context.

## Razionale
Il ranking da solo non basta: alcune evidenze semanticamente simili ma professionalmente secondarie
continuano a entrare nella risposta. Per questo si introduce una fase di ammissibilità per tipo di quesito.

## File coinvolti
- `src/rag/source_policy.py`
- `src/rag/orchestrator.py`

## Esito atteso
Ridurre:
- interpretazioni ufficiali non target nei change analysis;
- standard estranei nei transition/disclosure;
- standard collegati non core nei rule interpretation.
