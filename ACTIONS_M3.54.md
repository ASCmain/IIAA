# ACTIONS_M3.54.md

## Obiettivo
Integrare un classificatore LLM locale delle evidenze in modalità shadow.

## Modalità
- `off`: disabilitato
- `shadow`: classifica le evidenze ma non modifica ancora la selezione finale
- `assist`: previsto per step successivo

## File coinvolti
- `src/rag/evidence_classifier.py`
- `src/rag/orchestrator.py`
- `.env.example`
- `docs/ADVANCED_RAG_POLICY.md`
- `ARCHITECTURE_GUIDE.md`

## Esito atteso
Aggiungere alla pipeline un secondo livello di giudizio semantico locale, senza compromettere il funzionamento attuale del project work.
