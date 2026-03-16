# ACTIONS_M3.44.md

## Obiettivo
Modularizzare il ramo EUR-Lex HTML-first mantenendo compatibilità con gli script CLI attuali.

## Moduli introdotti
- `src/eurlex/fetch.py`
- `src/eurlex/blocks.py`
- `src/eurlex/normalize.py`
- `src/eurlex/__init__.py`

## Compatibilità
- `src/eurlex_html_blocks.py` resta facade compatibile
- `apps/corpus_fetch_eurlex.py` e `apps/normalize_eurlex_html.py` restano entrypoint CLI
