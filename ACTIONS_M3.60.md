# ACTIONS_M3.60.md

## Obiettivo
Correggere `src/rag/query_planning.py` aggiungendo i nuovi attributi richiesti da orchestrator:
- analysis_pool_target
- min_candidate_floor
- threshold_fallback_ladder

## Causa
La patch precedente non ha aggiornato correttamente la definizione di `QueryPlan`
o i costruttori di ritorno.

## Esito atteso
Ripristinare la compatibilità tra query planner e orchestrator.
