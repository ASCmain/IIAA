# ARCHITECTURE_GUIDE.md

## 1. Scopo del sistema

IIAA (International Intelligence Accounting Assistant) è un assistente RAG locale orientato a principi contabili internazionali IAS/IFRS, con focus professionale su contesto CFO, audit e consulenza contabile.  
L’obiettivo del sistema non è sostituire il professionista, ma fornire risposte grounded, tracciabili e verificabili su base documentale.

Il sistema è sviluppato localmente su Mac Apple Silicon, con pipeline incrementale, corpus governato, retrieval citabile e interfaccia tecnica/user-friendly.

---

## 2. Principi architetturali

1. **Local-first**: sviluppo e test in locale; pubblicazione remota solo dopo stabilizzazione.
2. **Grounded output**: ogni risposta deve essere riconducibile a evidenze recuperate.
3. **Corpus-governed**: la qualità delle risposte dipende da coverage, gerarchia e versioning del corpus.
4. **Modularità**: la logica deve essere suddivisa in moduli piccoli, sostituibili e testabili.
5. **Backward compatibility**: i refactor devono preservare il trunk applicativo ove possibile.
6. **Git discipline**: piccoli commit descrittivi, `CHANGELOG.md` append-only, working tree pulito a fine step.
7. **Runtime artifacts out of Git**: `.env`, `qdrant_data/`, `debug_dump/`, log voluminosi e artefatti runtime non vanno versionati.

---

## 3. Vista ad alto livello della pipeline

### 3.1 Corpus acquisition
Sorgenti normative e documentali vengono raccolte in forma controllata.  
Per EUR-Lex, il progetto privilegia flusso **HTML-first** per parsing/normalizzazione; i PDF locali restano come reference artifacts.

### 3.2 Normalization / chunk preparation
I documenti vengono normalizzati in blocchi o chunk, con metadati minimi coerenti con il retrieval.

Per il ramo PDF/deterministic:
- estrazione pagina per pagina;
- chunking deterministico;
- payload con metadati minimi.

Per il ramo EUR-Lex HTML-first:
- fetch HTML;
- estrazione blocchi logici;
- normalizzazione in righe JSONL.

Metadati minimi coerenti con il retrieval:
- `doc_id`
- `source_url`
- `source_path`
- `language`
- `standard_codes`
- `authority_level`
- `section_path`
- `chunk_id`
- eventuali riferimenti locali come `pdf_reference_path`

### 3.3 Embedding + indexing
I chunk vengono embedded con modello locale Ollama e indicizzati in Qdrant nelle collection canoniche.

### 3.4 Retrieval + prompting
Dato un quesito:
- si rileva la lingua;
- si seleziona la collection corretta;
- si recuperano evidenze rilevanti;
- si costruisce un prompt grounded;
- si genera una risposta con citazioni leggibili.

### 3.5 UI / inspection
La UI Streamlit mostra:
- risposta;
- citations readable;
- riferimenti fonte;
- retrieval evidences raw;
- dump di debug.

### 3.6 Benchmark / regression
Il sistema deve essere validato tramite:
- prompt benchmark professionali;
- regression tests;
- confronto con chatbot generalisti;
- analisi di coverage e pertinenza.

---

## 4. Struttura logica del progetto

### 4.1 Livello corpus
- `corpus_raw/`  
  Artefatti originali di riferimento, inclusi PDF locali.
- `data/processed/`  
  Output intermedi di normalizzazione, chunking e file index-ready.
- `data/manifests/`  
  Manifest generati dai run di indexing o pipeline.
- `debug_dump/`  
  Backup, audit, dump operativi, file temporanei non versionati.

### 4.2 Livello applicativo
- `apps/`  
  Entry point eseguibili, UI, CLI, fetcher, script operativi.
- `src/`  
  Logica di dominio e librerie interne.

### 4.3 Livello RAG
### 4.3.a Advanced RAG policy layer
Il livello RAG è stato esteso con una politica esplicita di query planning e source policy:

- `src/rag/query_planning.py`  
  Classificazione generale del quesito (change analysis, transition/disclosure, rule interpretation, numeric, ecc.).
- `src/rag/source_policy.py`  
  Politica di selezione e ordinamento delle evidenze in base a:
  - priorità tra atto modificativo e consolidato;
  - standard target;
  - disclosure/transizione;
  - trattamento dei quesiti numerici;
  - distinzione progressiva tra evidenze core e di contesto.

Questa logica è descritta in modo esteso in `docs/ADVANCED_RAG_POLICY.md`.

La source policy è ora orientata anche da una gerarchia metadata-driven a doppio asse:
- `legal_tier`: ruolo giuridico della fonte nel contesto UE (atto modificativo, consolidato, ecc.)
- `semantic_tier`: ruolo contabile della fonte (standard target, interpretazione ufficiale, supporto, ecc.)

Questo consente di distinguere meglio:
- fonte legalmente primaria;
- fonte concettualmente centrale;
- fonte collegata ma solo contestuale.


È inoltre previsto un classificatore locale delle evidenze (`src/rag/evidence_classifier.py`) servito tramite Ollama:
- in modalità `off`, `shadow` o `assist`
- con output strutturato `core/context/exclude`
- usato inizialmente per confronto e telemetria, e successivamente come supporto conservativo al bucket assignment core/context

Il coordinamento in `src/rag/orchestrator.py` include inoltre:
- retrieval pool esteso rispetto al solo `top_k`;
- selezione di un `analysis_pool` guidato da `analysis_pool_target`, `min_candidate_floor` e `threshold_fallback_ladder`;
- pruning successivo prima dello split `core/context`;
- telemetry timing per fasi (`embed`, `retrieve`, `policy`, `classifier`, `prompt`).



- `src/rag/models.py`  
  Modelli di dominio del retrieval, es. `Evidence`.
- `src/rag/ollama_io.py`  
  I/O verso Ollama: chat ed embeddings.
- `src/rag/language.py`  
  Rilevazione lingua.
- `src/rag/prompting.py`  
  Formattazione evidenze, label citazionali, prompt grounded.
- `src/rag/retrieval.py`  
  Query verso Qdrant, mapping payload → evidenze.
- `src/rag/orchestrator.py`  
  Coordinamento end-to-end del flusso query → retrieval → risposta.
- `src/PW_query_routing.py`  
  Facade compatibile per il trunk attuale.

### 4.3.b Benchmark smoke e osservabilità
Lo smoke benchmark applicativo (`apps/run_benchmark_smoke.py`) è stato esteso con:
- progress callback live per singolo case;
- telemetria standard di progetto in `telemetry/benchmark_smoke/run_*.json`;
- artifact di run in `debug_dump/benchmark_runs/smoke_*/`;
- summary sintetico con quick checks, segnali architetturali per-case e aggregati temporali.

Il runner (`src/benchmark/runner.py`) emette eventi `case_start` e `case_done`, comprensivi di timing per-case e metadati utili al benchmarking architetturale.

### 4.4 Livello ingestion PDF / deterministic
- `src/ingestion/hashing.py`  
  Hashing di file e testo.
- `src/ingestion/textnorm.py`  
  Normalizzazione testo.
- `src/ingestion/chunking.py`  
  Chunking deterministico.
- `src/ingestion/pdf_io.py`  
  Lettura pagine PDF.
- `src/ingestion/catalog.py`  
  Catalogo, iterazione item, risoluzione path, fingerprint runtime.
- `src/ingestion/payloads.py`  
  Costruzione payload chunk.
- `src/ingestion/deterministic.py`  
  Facade compatibile.

### 4.5 Livello EUR-Lex HTML-first
- `src/eurlex/fetch.py`  
  Supporto fetch HTML, loading source list, manifest writing.
- `src/eurlex/blocks.py`  
  Parsing HTML EUR-Lex e block extraction.
- `src/eurlex/normalize.py`  
  Costruzione righe normalizzate JSONL.
- `src/eurlex/__init__.py`  
  Export compatibile dei componenti del ramo HTML.
- `src/eurlex_html_blocks.py`  
  Facade compatibile verso il parser blocchi.

---

## 5. Contratti dati principali

### 5.1 Evidence
Oggetto logico di retrieval con campi minimi:
- `point_id`
- `score`
- `text`
- `source`
- `cite_key`
- `standard_id`
- `para_key`
- `section_path`
- `pdf_reference_path`

### 5.2 Citation output
La risposta applicativa deve restituire per ogni citazione:
- label leggibile (`cite_key` o fallback)
- `source`
- eventuale `pdf_reference_path`
- score
- locator logico (`standard_id`, `para_key`, `section_path`)

### 5.3 Fallback label
Se manca un `cite_key`, il sistema usa un’etichetta leggibile derivata dalla fonte, ad esempio:
- `CELEX:32025R1266`

---

## 6. Regole per aggiunte future

### 6.1 Se aggiungi un nuovo tipo di retrieval
Intervenire prima in:
- `src/rag/retrieval.py`
- poi eventualmente in `src/rag/orchestrator.py`

### 6.2 Se cambi il comportamento della risposta
Intervenire prima in:
- `src/rag/prompting.py`

### 6.3 Se cambi modelli LLM o embedding
Intervenire prima in:
- `src/rag/ollama_io.py`
- config/runtime UI in `apps/`

### 6.4 Se aggiungi nuove fonti corpus
Intervenire prima su:
- fetch / normalize / index-ready pipeline
- solo poi su retrieval e benchmark

### 6.5 Se aggiungi supporti documentali locali
Conservare distinzione tra:
- **fonte ufficiale** (`source`, `source_url`)
- **riferimento locale** (`pdf_reference_path` o equivalente)

---

## 7. Refactor roadmap consigliata

### 7.1 Priorità alta
1. refactor indexing in moduli dedicati `src/indexing/`
2. separazione rendering/debug UI da logica Streamlit principale
3. introduzione harness di regression test sui casi benchmark

### 7.1.a Refactor già completati
- modularizzazione del nucleo RAG in `src/rag/`
- modularizzazione ingestion PDF/deterministic in `src/ingestion/`
- modularizzazione EUR-Lex HTML-first in `src/eurlex/`

### 7.2 Priorità media
1. introduzione regression harness
2. config centralizzata per collection, modelli, thresholds
3. ranking/reranking professionale per atti UE specifici

### 7.3 Priorità documentale
1. mantenere aggiornata questa guida
2. usare questa guida come base per appendice tecnica
3. aggiungere diagrammi logici e mapping file → responsabilità

---

## 8. Stato attuale del trunk

### Punti stabilizzati
- runtime locale Ollama + Qdrant
- facade compatibile `src/PW_query_routing.py`
- modularizzazione del nucleo RAG
- citazioni leggibili
- supporto `pdf_reference_path`
- UI con fonte ufficiale + riferimento locale PDF

### Punti ancora da rifinire
- ranking su atti modificativi specifici
- coverage benchmark mirata
- tuning di pertinenza su IFRS 9 / IFRS 7 / IAS 36
- harness di regression test
- modularizzazione completa ingestion/indexing/UI

---

## 9. Convenzioni operative

- verificare `.env` solo a inizio nuova chat o a cambio contesto/tool
- usare zsh come shell di riferimento
- preferire heredoc per snippet multi-line robusti
- mantenere `git status` pulito a fine step
- spostare backup e file temporanei in `debug_dump/`
- produrre file `ACTIONS_Mx.x.md` per step significativi


---

## 10. Gestione `.env` e variabili ambiente

### 10.1 Regola generale
- Il file `.env` reale è locale e **non va versionato**.
- Il file `.env.example` documenta le chiavi attese e **va versionato**.
- Le variabili ambiente vanno verificate:
  - all’inizio di una nuova chat;
  - quando cambia contesto, tool o fase della pipeline;
  - quando si passa tra script diversi o tra runtime diversi.

### 10.2 Variabili minime del trunk attuale
Le variabili minime attese per il funzionamento del PoC attuale sono:

- `QDRANT_URL`
- `OLLAMA_BASE_URL`
- `QDRANT_COLLECTION_IT`
- `QDRANT_COLLECTION_EN`

Valori attesi nel trunk attuale:
- `QDRANT_URL=http://localhost:6333`
- `OLLAMA_BASE_URL=http://localhost:11434`
- `QDRANT_COLLECTION_IT=iiaa_eurlex_02023R1803_it`
- `QDRANT_COLLECTION_EN=iiaa_eurlex_02023R1803_en`

### 10.3 Export di sessione
Per test rapidi o smoke test locali, è ammesso usare export di sessione shell invece di modificare `.env`:

export QDRANT_URL="http://localhost:6333"
export OLLAMA_BASE_URL="http://localhost:11434"
export QDRANT_COLLECTION_IT="iiaa_eurlex_02023R1803_it"
export QDRANT_COLLECTION_EN="iiaa_eurlex_02023R1803_en"

### 10.4 Priorità operativa

Ordine consigliato:
    1.    .env.example come riferimento documentale;
    2.    .env locale come configurazione stabile;
    3.    export temporanei per test o debug.

⸻

## 11. Runtime handles: Docker, Qdrant, Ollama, UI

### 11.1 Docker

Docker viene usato come runtime container per Qdrant.

Comandi utili:

open -a Docker
docker info >/dev/null && echo "Docker OK" || echo "Docker NON pronto"
docker ps -a --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}'

### 11.2 Qdrant

Container canonico del progetto:
    •    iiaa-qdrant

Avvio e verifica:
docker start iiaa-qdrant
curl -s http://localhost:6333/collections

Collezioni canoniche attuali:
    •    iiaa_eurlex_02023R1803_it
    •    iiaa_eurlex_02023R1803_en

### 11.3 Ollama

Ollama è il runtime locale per:
    •    embeddings
    •    chat generation

Verifica:
ollama list
curl -s http://localhost:11434/api/tags

Modelli attualmente usati nel trunk:
    •    embeddings: mxbai-embed-large:latest
    •    chat: mistral:latest oppure llama3.1:8b

### 11.4 UI Streamlit

Entry point attuale:
    •    apps/PW_projectwork_ui_streamlit.py

Avvio:

streamlit run apps/PW_projectwork_ui_streamlit.py

### 11.5 Provenance runtime

Per documenti EUR-Lex HTML-first:
    •    source / source_url = fonte ufficiale EUR-Lex
    •    pdf_reference_path = riferimento locale PDF, se presente

Questa distinzione va preservata anche nelle future estensioni del progetto.

## 12. Checklist di startup locale

### 12.1 Sequenza consigliata
    1.    attivare virtual environment
    2.    verificare Docker
    3.    avviare iiaa-qdrant
    4.    verificare Ollama
    5.    verificare variabili ambiente
    6.    lanciare UI o smoke test

12.2 Esempio operativo

cd ~/Tesi/IIAA
source .venv/bin/activate

open -a Docker
docker start iiaa-qdrant

export QDRANT_URL="http://localhost:6333"
export OLLAMA_BASE_URL="http://localhost:11434"
export QDRANT_COLLECTION_IT="iiaa_eurlex_02023R1803_it"
export QDRANT_COLLECTION_EN="iiaa_eurlex_02023R1803_en"

curl -s http://localhost:6333/collections
curl -s http://localhost:11434/api/tags

streamlit run apps/PW_projectwork_ui_streamlit.py

