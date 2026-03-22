# ACTIONS_M3.75

## Oggetto
Introduzione di semantic router locale embedding-based per la disambiguazione semantica del query planning.

## Interventi
- creato `config/semantic_intent_catalog.json` come catalogo versionato di intent semantici;
- creato `src/rag/semantic_router.py` per routing embedding-based locale;
- integrato il semantic router in `src/rag/orchestrator.py` prima del `query_planning`;
- aggiornato `src/rag/query_planning.py` per accettare `semantic_route` e usarlo come hint semantico non ambiguo;
- aggiornato `.env.example` con le variabili del semantic router.

## Razionale
Le euristiche lessicali pure non bastavano a distinguere usi diversi della stessa parola, ad esempio "transizione" in contesto normativo versus "rischi di transizione" in contesto gestionale/climatico.

## Beneficio
- migliore word sense disambiguation nel routing;
- maggiore auditabilità tramite catalogo di intent versionato;
- base per futura escalation LLM solo nei casi semanticamente ambigui.
