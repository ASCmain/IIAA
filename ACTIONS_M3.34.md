# ACTIONS_M3.34.md

## Obiettivo
Modularizzare il query routing RAG e correggere la disciplina citazionale del prompt.

## Interventi eseguiti
1. Introdotta struttura modulare `src/rag/`:
   - `models.py`
   - `ollama_io.py`
   - `language.py`
   - `prompting.py`
   - `retrieval.py`
   - `orchestrator.py`
   - `__init__.py`

2. Trasformato `src/PW_query_routing.py` in facade compatibile.

3. Corretta la provenance:
   - `pdf_reference_path` propagato in `Evidence`
   - `pdf_reference_path` esposto nelle citations
   - UI aggiornata con fonte ufficiale + riferimento locale PDF

4. Corretta la disciplina citazionale:
   - introdotto fallback label `CELEX:32025R1266`
   - rimosso il prefisso numerico nel bundle evidenze
   - eliminate citazioni numeriche `[1] [2]` dal comportamento del modello

## Esito
- Il PoC continua a funzionare tramite la facade compatibile.
- Le citazioni sono ora leggibili e coerenti con le evidenze.
- Il sistema resta da rifinire sul ranking, perché il contenuto resta ancora troppo trainato dai paragrafi del consolidato 2023/1803 rispetto all’atto modificativo 2025/1266.
