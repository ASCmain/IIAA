# ACTIONS_M3.35.md

## Obiettivo
Documentare la gestione `.env`, le variabili ambiente minime del trunk e gli handle runtime principali.

## Interventi eseguiti
1. Aggiornato `ARCHITECTURE_GUIDE.md` con:
   - politica `.env`
   - variabili minime
   - export di sessione
   - runtime handles Docker / Qdrant / Ollama / UI
   - checklist di startup locale

2. Creato/aggiornato `.env.example` con:
   - `QDRANT_URL`
   - `OLLAMA_BASE_URL`
   - `QDRANT_COLLECTION_IT`
   - `QDRANT_COLLECTION_EN`

## Esito
Il progetto dispone ora di una base documentale versionabile per:
- configurazione runtime;
- onboarding;
- ripartenza ordinata delle sessioni;
- futura appendice tecnica.
