# ACTIONS_M3.33.md

## Obiettivo
Propagare e mostrare in UI il riferimento locale PDF per il caso EUR-Lex 2025/1266, mantenendo come fonte ufficiale la URL EUR-Lex HTML.

## Interventi eseguiti
1. Patch di `src/PW_query_routing.py`
   - aggiunto `pdf_reference_path` alla dataclass `Evidence`
   - aggiunto mapping `pdf_reference_path` in `retrieve()`
   - aggiunto `pdf_reference_path` nelle `citations` restituite da `run_query()`

2. Enrichment dei file index-ready del 2025/1266
   - IT: `corpus_raw/eurlex_pdf/OJ_L_202501266_IT_TXT.pdf`
   - EN: `corpus_raw/eurlex_pdf/OJ_L_202501266_EN_TXT.pdf`

3. Reindicizzazione mirata del solo 2025/1266 nelle collection canoniche
   - `iiaa_eurlex_02023R1803_it`
   - `iiaa_eurlex_02023R1803_en`

4. Patch di `apps/PW_projectwork_ui_streamlit.py`
   - aggiunto `pdf_reference_path` nel blocco “Citations (readable)”
   - aggiunta sezione “Riferimenti fonte”
   - mostrati:
     - Fonte ufficiale: URL EUR-Lex
     - Riferimento locale PDF: path locale, se presente

## Esito
- Provenance corretta fino alla UI.
- Evidenze da `CELEX:32025R1266` mostrano anche il PDF locale.
- Il PoC resta però ancora da rifinire sul piano della pertinenza/ranking e della disciplina citazionale nel testo di risposta.

## Prossimo step consigliato
Patch del prompt grounded per:
1. vietare citazioni numeriche `[1] [2] ...`
2. usare solo `cite_key` reali se presenti
3. usare fallback esplicito per atti OJ/CELEX senza `cite_key`
