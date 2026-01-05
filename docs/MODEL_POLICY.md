# MODEL_POLICY — IIAA (Intelligent International Accounting Assistant)

Versione: 0.1
Data: 2026-01-05

## Scopo
Politica per gestione modelli (embedding/chat/router/critic/writer) con freeze per milestone, local-only e tracciabilità.

## Vincolo local-only
Il prototipo utilizza esclusivamente modelli eseguibili localmente via Ollama. Modelli cloud esclusi.

## Freeze per milestone
- Embedding model invariato nella milestone.
- Chat model invariato nella milestone salvo bug critici documentati.
Cambio modello solo a milestone successiva con aggiornamento POLICY + CHANGELOG + tag.

## Ruoli via .env
- OLLAMA_EMBED_MODEL
- OLLAMA_CHAT_MODEL
- OLLAMA_ROUTER_MODEL (opzionale)
- OLLAMA_CRITIC_MODEL (opzionale)
- OLLAMA_WRITER_MODEL (opzionale)

## Scelte M1
- Embedding: mxbai-embed-large
- Chat: llama3.1:8b
