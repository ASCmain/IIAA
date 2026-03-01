# IIAA — Spec tecnico di parsing e chunking (v0.3)

.env per questa fase: **.env.corpus** (o equivalente). Verificalo solo a inizio nuova chat o quando cambi fase/tool.

Scopo: definire regole deterministiche e riproducibili per importare testi UE (OJ + CELEX) che incorporano IFRS/IAS/IFRIC/SIC, preservando riferimenti (articoli, standard, paragrafi) e gestendo marker editoriali CELEX.

Questo spec è progettato per:
- PDF CELEX consolidato (con marker ►M…, ▼B…)
- PDF CELEX “base” (testo non consolidato)
- PDF OJ (GUUE) dei regolamenti e dei regolamenti di modifica (es. 2026/338)

---

## 1. Concetti e output attesi

### 1.1 Unità di output
Il parser produce un “document object” con:
- `doc_text_clean` (testo pulito, opzionale se usi chunk-only)
- `chunks[]`: lista di chunk strutturati, ognuno con:
  - `chunk_id` (stabile)
  - `text` (pulito)
  - `anchors` (riferimenti citabili)
  - `metadata` (language, doc_family_id, authority_level, ecc.)

### 1.2 Anchors (riferimenti citabili)
Due famiglie:

A) **EU legal anchors** (Regulation/OJ):
- `anchor_type = "eu_article"`: `EU-REG-YYYY-NNNN:ArtX`
- `anchor_type = "eu_recital"`: `EU-REG-YYYY-NNNN:Recital{n_start}-{n_end}`
- `anchor_type = "eu_annex"`: `EU-REG-YYYY-NNNN:Annex{roman}` (quando presente)

B) **IFRS anchors** (standard/paragrafi):
- `anchor_type = "ifrs_paragraph"`: `IAS36:59` oppure `IFRS13:72` oppure `IFRS9:5.5.3`
- `anchor_type = "ifrs_range"`: `IAS36:59-63`
- `anchor_type = "ifrs_appendix"`: `IFRS13:AppA` / `IFRS9:AppB` / `IAS36:AppC` (se presenti)

---

## 2. Pipeline di parsing (alto livello)

### Step P0 — Ingest (file → testo raw)
Input: PDF/HTML/TXT
Output: `raw_lines[]` (lista di righe, preservando ordine)

- PDF: usa un estrattore robusto (es. pdfminer.six) con:
  - `laparams` per mantenere l’ordine di lettura
  - separazione pagine per debugging (opzionale)
- HTML: estrazione testo dal DOM, mantenendo heading (h1/h2/…)
- TXT: carica diretto

### Step P1 — Normalizzazione linee
Input: `raw_lines[]`
Output: `norm_lines[]`

Operazioni (ordine consigliato):
1) trim spazi, normalizza whitespace interno (multi-space → single)
2) rimuovi righe vuote ripetute
3) **de-hyphenation controllata**:
   - se una riga termina con `-` e la successiva inizia con lettera minuscola → unisci rimuovendo `-`
   - non unire se la riga termina con `-` ma la successiva inizia con Maiuscola (potrebbe essere nuovo titolo)
4) normalizza apostrofi/virgolette (’ → ' dove necessario)

### Step P2 — Rimozione boilerplate (header/footer/page artifacts)
Output: `clean_lines[]`

Regole:
- rimuovi linee che matchano:
  - `^\s*\d+\s*/\s*\d+\s*$` (numeri pagina)
  - `^\s*L\s+\d+\s*/\s*\d+\s*$` (OJ paginazione tipo “L 45/12”)
  - `^\s*020\d{2}R\d{4}\s+—\s+(EN|IT)\s+—\s+\d{2}\.\d{2}\.\d{4}.*$` (header CELEX consolidato)
  - righe ripetute identiche su molte pagine (heuristic: top-10 freq lines)

Nota: conserva sempre righe con “Article”, “Whereas”, “ANNEX”, “INTERNATIONAL … STANDARD” perché sono boundary.

### Step P3 — Gestione marker editoriali CELEX (solo CELEX consolidati)
Obiettivo: eliminare i marker dalla superficie del testo, ma conservarli se vuoi come “provenance”.

Marker tipici:
- `►M\d+` (modifica/amendment marker)
- `►C\d+` (corrigendum marker)
- `▼B` (baseline marker)

Regole:
- Se una riga contiene SOLO marker (es. `►M3`) → rimuovi la riga e registra `last_marker = "M3"`.
- Se il marker precede testo sulla stessa riga, rimuovi marker e mantieni il testo.
- Opzionale: aggiungi `metadata.amendment_marker = last_marker` ai chunk fino al prossimo marker.

Regex:
- `CELEX_MARKER = r"(?:^|\s)(►\s*[MC]\d+|▼\s*B)\s*"`

---

## 3. Segmentazione documentale (boundary detection)

### 3.1 Riconoscimento “parte normativa UE” (Recitals + Articles)
Boundary principali:
- Recitals: linee che iniziano con `(1)` … `(n)` oppure “Whereas”
- Articles: linee che matchano `^Article\s+\d+` (EN) / `^Articolo\s+\d+` (IT)
- Annex: `^ANNEX\b` / `^ALLEGATO\b`

Algoritmo:
1) Scansiona `clean_lines[]` e crea “blocks”:
   - `block_type = recital_block` quando incontri il primo recital (o “Whereas”)
   - `block_type = article` da `Article X` fino a prima di `Article X+1` o `ANNEX`
   - `block_type = annex` da `ANNEX` in poi

2) Per `recital_block`: chunk a finestre (es. 3–8 recitals per chunk) mantenendo numerazione.

Regex utili:
- `RECITAL_EN = r"^\(\d+\)\s+"`
- `RECITAL_IT = r"^\(\d+\)\s+"` (spesso uguale)
- `ARTICLE_EN = r"^Article\s+(\d+)\b"`
- `ARTICLE_IT = r"^Articolo\s+(\d+)\b"`
- `ANNEX_EN = r"^ANNEX\b"`
- `ANNEX_IT = r"^ALLEGATO\b"`

### 3.2 Riconoscimento “standard IFRS dentro Annex”
Dopo `ANNEX/ALLEGATO`, individua l’inizio di ciascuno standard.

Boundary standard (pattern tipici in CELEX):
- `^INTERNATIONAL\s+ACCOUNTING\s+STANDARD\s+\d+\b` (IAS n)
- `^INTERNATIONAL\s+FINANCIAL\s+REPORTING\s+STANDARD\s+\d+\b` (IFRS n)
- `^IFRIC\s+\d+\b`
- `^SIC\s+\d+\b`

Italiano:
- `^PRINCIPIO\s+CONTABILE\s+INTERNAZIONALE\s+\d+\b` (può variare)
- oppure intestazioni mantenute in EN anche nei testi IT (capita spesso nei regolamenti UE)

Regola robusta:
- usa sia pattern EN sia pattern IT, e in fallback rileva righe che contengono “IAS”/“IFRS” in maiuscolo + numero.

Extraction `standard_id`:
- IAS: `IAS 36`
- IFRS: `IFRS 13`, `IFRS 9`, `IFRS 7`, `IFRS 1`, `IFRS 18`
- IFRIC: `IFRIC 23`
- SIC: `SIC 7`

Regex:
- `STD_IAS = r"^INTERNATIONAL\s+ACCOUNTING\s+STANDARD\s+(\d+)\b"`
- `STD_IFRS = r"^INTERNATIONAL\s+FINANCIAL\s+REPORTING\s+STANDARD\s+(\d+)\b"`
- `STD_IFRIC = r"^IFRIC\s+(\d+)\b"`
- `STD_SIC = r"^SIC\s+(\d+)\b"`
- `STD_FALLBACK = r"\b(IAS|IFRS|IFRIC|SIC)\s*(\d+)\b"`

---

## 4. Segmentazione a paragrafi IFRS (core)

### 4.1 Riconoscimento paragrafi numerati
Obiettivo: identificare linee che aprono un paragrafo IFRS/IAS.

Pattern frequenti:
- `^\d+\s+` (paragrafo intero: “59 …”)
- `^\d+\.` (meno frequente)
- `^B\d+\s+` (appendici: “B1 …”)
- `^IE\d+\s+` (illustrative examples)
- `^BC\d+\s+` (basis for conclusions) — se presenti nei testi UE (spesso no)

IFRS 9 ha spesso riferimenti tipo `5.5.1`, `5.5.2`, ecc.
Pattern:
- `^\d+\.\d+(?:\.\d+)*\s+`  (es. 5.5.3)

Regex:
- `PARA_INT = r"^(\d{1,3})\s+(.+)$"`
- `PARA_DOTTED = r"^(\d+(?:\.\d+){1,4})\s+(.+)$"`
- `PARA_APP_B = r"^(B\d+)\s+(.+)$"`
- `PARA_APP_IE = r"^(IE\d+)\s+(.+)$"`
- `PARA_APP_BC = r"^(BC\d+)\s+(.+)$"`

### 4.2 Algoritmo di parsing paragrafi
Dato un blocco standard `std_lines[]`:
1) Scansiona linee; quando una linea matcha una delle regex di paragrafo, inizia un nuovo paragrafo.
2) Accumula linee successive finché non incontri il prossimo “start paragrafo” o un boundary di sezione (heading).

Output di paragrafo:
- `para_key`: string (`"59"` oppure `"5.5.3"` oppure `"B12"`)
- `para_text`: testo unito con spazi, preservando punteggiatura.

### 4.3 Heading e section_path (opzionale ma utile)
Riconosci heading in maiuscolo (EN) o con stile tipico:
- riga in ALL CAPS e lunghezza 3–80
- riga che matcha `^(Objective|Scope|Definitions|Recognition|Measurement|Disclosure|Effective date|Transition)\b` (EN)
- IT analogo: `^(Obiettivo|Ambito|Definizioni|Rilevazione|Valutazione|Informativa|Data di efficacia|Transizione)\b`

Mantieni uno stack di heading:
- `section_path = "IAS 36 > Measuring recoverable amount > Value in use"`

Regex EN:
- `HEADING_EN = r"^(OBJECTIVE|SCOPE|DEFINITIONS|RECOGNITION|MEASUREMENT|DISCLOSURE|EFFECTIVE\s+DATE|TRANSITION)\b"`
Regex generic caps:
- `HEADING_CAPS = r"^[A-Z][A-Z\s\-]{2,80}$"`

---

## 5. Chunking policy (deterministica)

### 5.1 Chunk base per IFRS paragraphs
- unità: paragrafo (o sub-paragrafo) come definito in §4
- chunk size: 1–3 paragrafi contigui (configurabile)
- overlap: 1 paragrafo (configurabile)

Regole:
- non attraversare cambi di heading se non includendo heading come prefisso del chunk
- se un singolo paragrafo è troppo lungo (es. > 1.500–2.000 caratteri):
  - spezzalo su frasi (periodi) mantenendo `para_key` e aggiungendo `part_index`

### 5.2 Chunk per Articles (EU law)
- chunk = un articolo (da “Article X” fino a prima di “Article X+1”)
- se articolo molto lungo: spezza per commi (quando identificabili) o per frasi con overlap.

### 5.3 Chunk per Recitals
- finestra: 3–8 recitals per chunk
- anchor: `Recital{start}-{end}`

---

## 6. Metadati minimi per chunk (compatibili con schema v0.2)

Ogni chunk deve includere almeno:
- `doc_id`, `doc_family_id`, `doc_variant`, `authority_level`, `source_tier`
- `language`, `jurisdiction`
- `anchor_type`, `cite_key` (o `anchor_key`)
- `standard_id` (solo per IFRS chunks)
- `paragraph_start`, `paragraph_end` (solo per IFRS chunks; o `para_key` per singolo)
- `section_path` (opzionale)
- `amendment_marker` (opzionale, utile per CELEX)

Esempio IFRS chunk (JSON):
```json
{
  "chunk_id": "EU:REG:2023/1803|IAS36|59-61|en|v2025-07-30",
  "text": "IAS 36 — Value in use ... [para 59] ... [para 60] ... [para 61] ...",
  "anchors": [{"anchor_type":"ifrs_range","cite_key":"IAS36:59-61"}],
  "metadata": {
    "doc_family_id":"EU:REG:2023/1803",
    "doc_variant":"celex_consolidated",
    "authority_level":"consolidated_reference",
    "source_tier":2,
    "jurisdiction":"EU",
    "language":"en",
    "standard_id":"IAS 36",
    "paragraph_start":"59",
    "paragraph_end":"61",
    "section_path":"IAS 36 > Measuring recoverable amount > Value in use",
    "consolidated_as_of":"2025-07-30",
    "amendment_marker":"M4"
  }
}
```

Esempio Article chunk (JSON):
```json
{
  "chunk_id": "EU:REG:2026/338|Art2|it",
  "text": "Regulation (EU) 2026/338 — Article 2 ...",
  "anchors": [{"anchor_type":"eu_article","cite_key":"EU-REG-2026-338:Art2"}],
  "metadata": {
    "doc_family_id":"EU:REG:2026/338",
    "doc_variant":"oj",
    "authority_level":"binding_text",
    "source_tier":2,
    "jurisdiction":"EU",
    "language":"it"
  }
}
```

---

## 7. Validazioni e sanity check automatici

1) **Coverage paragrafi**: per ogni standard chiave (IAS 36, IFRS 13, IFRS 9, IFRS 7, IFRS 1, IFRS 18) calcola:
- numero di paragrafi riconosciuti / stimati
- warning se sotto 98%

2) **Monotonia**: i para_key numerici devono essere non-decrescenti.

3) **Duplicati**:
- duplicati di `chunk_id` non ammessi
- duplicati di `(standard_id, paragraph_range, language, doc_family_id)` → warning

4) **Marker leakage**:
- warning se nel testo pulito compaiono ancora `►` o `▼`

5) **Anchor integrity**:
- ogni chunk deve avere almeno 1 anchor (cite_key)
- per IFRS chunk deve avere `standard_id` e `paragraph_start`

---

## 8. Parametri consigliati (baseline)

- `ifrs_chunk_paragraphs = 2` (1–3 ok)
- `ifrs_overlap_paragraphs = 1`
- `article_max_chars = 2200` (oltre spezza)
- `recital_window = 5`, `recital_overlap = 1`

---

## 9. Note operative (MVP compatibility)

- Se l’MVP attuale chunkava “per lunghezza” senza ancoraggi, questa v0.3 introduce ancoraggi citabili. È il principale upgrade richiesto per tesi e affidabilità.
- Per gli standard IASB “as issued” (non UE): usa lo stesso schema paragrafi; cambiano `jurisdiction="IASB"` e `authority_level="endorsed_standard"` o altro, in base alla policy.

