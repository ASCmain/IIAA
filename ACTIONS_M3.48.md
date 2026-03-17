# ACTIONS_M3.48.md

## Obiettivo
Introdurre un query planning layer generale per pilotare il retrieval in modo difendibile e non benchmark-specifico.

## Moduli introdotti
- `src/rag/query_planning.py`
- `src/rag/source_policy.py`

## Estensioni
- `src/rag/orchestrator.py` usa ora query plan + source policy
- benchmark smoke salva anche il query plan per ciascun caso
- introdotto supporto esplicito ai casi con componente numerica

## Esito atteso
Il sistema decide la strategia di retrieval in base al tipo di domanda, allo standard target e alla priorità tra testo consolidato e atto modificativo.
