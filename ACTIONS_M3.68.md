# ACTIONS_M3.68

## Oggetto
Introduzione del focus detection layer in shadow mode con catalogo dominio versionato IFRS/IAS.

## File introdotti
- `config/focus_catalog_ifrs.json`
- `src/rag/focus_detection.py`

## File aggiornati
- `.env.example`
- `src/rag/orchestrator.py`
- `apps/PW_projectwork_ui_streamlit.py`

## Contenuto della tranche
- aggiunto catalogo dominio iniziale versionato e revisionabile da professionista;
- introdotto modulo di focus detection locale via Ollama;
- integrazione in `orchestrator.py` in modalità solo osservativa (`shadow`);
- esposizione di focus detection nel payload applicativo;
- visualizzazione del focus nel tab Debug della UI;
- visualizzazione delle env di focus detection nel tab System.

## Razionale
La focus detection non è basata su shortcut hard-coded di casi benchmark, ma su un catalogo controllato:
- aperto nel linguaggio della query;
- chiuso nell’ontologia interna;
- sottoponibile a validazione human-in-the-loop;
- utile per appendice tecnica e governance semantica del sistema.
