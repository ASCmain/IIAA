
## QC monoblocco — esito (doc_id=eu_oj_02023R1803_20250730, celex=02023R1803-20250730)
Output:
- EN: 15476 righe; 10392028 bytes
- IT: 15479 righe; 11324510 bytes
Validità JSONL: bad_lines=0 (EN/IT)
Schema: campi completi, tipi coerenti (EN/IT)
Block index: consecutivo, no duplicati, last=total-1 (EN/IT)
Heading path:
- EN with_heading_path 15471; max_depth 6
- IT with_heading_path 15474; max_depth 6
Distribuzione kind:
- EN: paragraph=12519, td=946, heading=2011
- IT: paragraph=12524, td=946, heading=2009
Normalizzazione: soft_hyphen=0, zero_width=0, spaced_letters=0 (EN/IT)
Keyword hits:
- EN: INTERNATIONAL ACCOUNTING STANDARD=26; Article 1=1; ANNEX=1
- IT: PRINCIPI CONTABILI=2; Articolo 1=1; ALLEGATO=1
SHA coerenza: JSONL sha256 == HTML sha256 (EN/IT)
Telemetria (ultimo run):
- events: inputs, result
- spans: read_and_hash, extract_blocks, build_rows, write_jsonl


## M2.3 — Normalizzazione EUR-Lex oracle HTML → blocks JSONL (EN/IT)

### Root cause (heading_path vuoto)
Gli HTML “oracle” EUR-Lex non usano tag semantici h1..h6 (conteggio h1..h6 = 0). I titoli sono codificati prevalentemente come `<p class="title-...">` (es. title-doc-*, title-article-norm, title-annex-1, title-gr-seq-level-1..5). Di conseguenza, l’estrattore iniziale (basato su h1..h6) produceva `heading_path=[]` per tutti i record.

### Fix implementato
- Aggiornato `src/eurlex_html_blocks.py` per riconoscere heading tramite classi `title-*`:
  - `title-gr-seq-level-N` → livello N
  - `title-doc-*` → livello 1
  - `title-article-norm` e `title-annex-*` → livello 2
  - fallback prudente `title-*` → livello 3
- `apps/normalize_eurlex_html.py` aggiornato per telemetria completa: eventi `inputs` e `result`, spans `read_and_hash`, `extract_blocks`, `build_rows`, `write_jsonl`.
- Utility `src/text_normalize.py` per normalizzazione conservativa (NFKC, rimozione caratteri invisibili, whitespace).

### Output generato
- EN: `data/processed/eu_oj/blocks/eu_oj_02023R1803_20250730__02023R1803-20250730__EN.blocks.jsonl`
- IT: `data/processed/eu_oj/blocks/eu_oj_02023R1803_20250730__02023R1803-20250730__IT.blocks.jsonl`
Nota: output in `data/processed/` considerato artefatto runtime e non versionato.

### QC (monoblocco)
A) Presenza file:
- HTML_EN: 8720069 bytes
- HTML_IT: 9259822 bytes
- JSONL_EN: 10392028 bytes
- JSONL_IT: 11324510 bytes

B) Validità JSONL:
- EN bad_lines=0 su 15476
- IT bad_lines=0 su 15479

C) Schema & tipi (EN/IT):
Campi presenti: doc_id, celex, language, source_url, source_path, sha256, block_index, kind, heading_path, text.
Tipi coerenti: block_index=int, heading_path=list, text=str.

D) Integrità block_index:
- EN: first=0 last=15475, consecutivo, duplicati=0, last==total-1=True
- IT: first=0 last=15478, consecutivo, duplicati=0, last==total-1=True

E) Heading_path:
- EN: with_heading_path=15471, max_depth=6
- IT: with_heading_path=15474, max_depth=6

F) Distribuzione kind:
- EN: paragraph=12519, td=946, heading=2011
- IT: paragraph=12524, td=946, heading=2009

G) Normalizzazione caratteri:
- soft-hyphen=0, zero-width=0, spaced_letters_like=0 (EN/IT)

H) Keyword smoke test:
- EN: INTERNATIONAL ACCOUNTING STANDARD=26; Article 1=1; ANNEX=1
- IT: PRINCIPI CONTABILI=2; Articolo 1=1; ALLEGATO=1

I) Tracciabilità SHA:
- EN: sha256 JSONL == sha256 HTML (match True)
- IT: sha256 JSONL == sha256 HTML (match True)

J) Telemetria (ultimo run):
- step=normalize_eurlex_html
- events=[inputs, result]
- spans=[read_and_hash, extract_blocks, build_rows, write_jsonl]
- path: `telemetry/normalize_eurlex_html/run_*.json`


Nota: questo file contiene un primo recap M2.3 e un’integrazione successiva più completa (QC monoblocco + root cause/fix). La seconda sezione prevale come riferimento operativo.

Nota di consolidamento: M2.3 è stato documentato in due passaggi (recap iniziale + integrazione completa con QC monoblocco, root cause e fix heading via classi EUR-Lex). Fare riferimento alla sezione “M2.3 — Normalizzazione EUR-Lex oracle HTML → blocks JSONL (EN/IT)” come sintesi definitiva.
