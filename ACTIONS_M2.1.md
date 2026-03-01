# ACTIONS_M2.1 — Sistemazione artefatti iniziali + commit documentazione

.env: .env.corpus

## Obiettivo
Versionare sorgenti, spec tecniche e glossario seed per avviare M2 (HTML-first EU-Lex).

## Comandi eseguiti (sintesi)
- git switch -c feat/html-first-ingestion-m2
- mkdir -p data/sources data/glossary docs/specs
- mv file dalla root verso:
  - data/sources/
  - docs/specs/
  - data/glossary/
- git add/commit:
  - docs(corpus): eur-lex sources list + parsing spec html-first
  - docs(specs): metadata schema + routing rules + parsing spec v0.3
  - feat(glossary): seed bilingual IFRS glossary (100 terms)

## Stato finale
- git status: clean
