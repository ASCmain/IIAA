# IIAA — Schema metadati corpus (v0.2)

.env per questa fase: **.env.corpus** (o equivalente). Verificalo solo a inizio nuova chat o quando cambi fase/tool.

Questo documento definisce lo schema metadati consigliato per il corpus “definitivo” (estensibile) con supporto multilingua IT/EN, gerarchia delle fonti e deduplica tra varianti (CELEX vs OJ).

Nota importante: non avendo qui l’elenco completo dei campi “MVP” già implementati nel tuo repo, il presente schema è progettato per essere **retro‑compatibile**: i nuovi campi sono **opzionali** e non rompono i documenti esistenti. Se mi incolli lo schema MVP attuale (anche solo un esempio di record JSON), posso produrre una v0.2 “definitiva” allineata 1:1.

---

## 1. Principi di design

1) **Doc family**: lo stesso contenuto normativo può esistere in più lingue e più “varianti editoriali” (OJ, CELEX base, CELEX consolidato). Si gestisce con un identificatore stabile `doc_family_id`.

2) **Authority / gerarchia**: per le fonti UE, il testo pubblicato in **OJ** è “autentico/binding”; il testo **CELEX consolidato** è eccellente per consultazione e chunking ma resta “reference”. Ciò va codificato in `authority_level` e/o `source_tier`.

3) **Language-aware retrieval**: il retrieval deve privilegiare `language` coerente con la query, con fallback controllato.

4) **Deduplica**: evitare che lo stesso contenuto venga recuperato due volte in lingue/varianti diverse (si usa `doc_family_id` + `doc_variant` + campi di fingerprint di chunk se presenti nel MVP).

---

## 2. Schema logico (alto livello)

Un “document record” del catalog punta a un file (PDF/HTML/TXT), ha metadati di provenienza e versionamento, e opzionalmente include informazioni di relazione (amends/amended_by) per la governance normativa.

---

## 3. Campi (completo: tutti quelli indicati finora)

Di seguito: nome campo, tipo, obbligatorietà consigliata, esempio, funzione.

### 3.1 Identità e file

- **doc_id**  
  Tipo: string  
  Obbligatorio: Sì (consigliato)  
  Esempio: `eu_reg_2023_1803_it_celex_consolidated_2025-07-30`  
  Funzione: identificatore univoco del record nel catalog.

- **path**  
  Tipo: string (relative path nel repo)  
  Obbligatorio: Sì  
  Esempio: `corpus_raw/eu/CELEX_02023R1803-20250730_IT_TXT.pdf`  
  Funzione: posizione del file nel corpus.

- **file_format**  
  Tipo: enum (`pdf`, `html`, `txt`, `docx`, `md`)  
  Obbligatorio: Consigliato  
  Esempio: `pdf`  
  Funzione: routing pipeline (parser/cleaner).

- **sha256**  
  Tipo: string (64 hex)  
  Obbligatorio: Consigliato (forte)  
  Esempio: `b3b...`  
  Funzione: integrità, deduplica, riproducibilità.

- **bytes**  
  Tipo: integer  
  Obbligatorio: Opzionale  
  Esempio: `9038123`  
  Funzione: sanity check e costi.

---

### 3.2 Lingua, giurisdizione, famiglia documentale (multilingua)

- **language**  *(NUOVO)*  
  Tipo: enum (`it`, `en`)  
  Obbligatorio: Sì (consigliato per corpus bilingue)  
  Esempio: `it`  
  Funzione: retrieval language-aware; output e citazioni coerenti.

- **jurisdiction**  *(NUOVO)*  
  Tipo: string/enum (es. `EU`, `IASB`, `UK`, `IT`)  
  Obbligatorio: Consigliato  
  Esempio: `EU`  
  Funzione: filtri (es. “solo norme UE”).

- **doc_family_id**  *(NUOVO)*  
  Tipo: string  
  Obbligatorio: Sì (consigliato)  
  Esempio: `EU:REG:2023/1803`  
  Funzione: unisce lingue e varianti della stessa “opera normativa”.

- **doc_variant**  *(NUOVO)*  
  Tipo: enum (`oj`, `celex_base`, `celex_consolidated`, `other`)  
  Obbligatorio: Consigliato  
  Esempio: `celex_consolidated`  
  Funzione: distinguere la natura editoriale del testo per authority e deduplica.

- **canonical_rank**  *(NUOVO)*  
  Tipo: integer (0..n)  
  Obbligatorio: Consigliato  
  Esempio: `0`  
  Funzione: scegliere il “testo preferito” a parità di contenuto (0=canonico).

---

### 3.3 Provenienza, identificativi ufficiali, linkabilità

- **title**  
  Tipo: string  
  Obbligatorio: Consigliato  
  Esempio: `Commission Regulation (EU) 2023/1803`  
  Funzione: display in UI e citazioni.

- **publisher**  
  Tipo: string  
  Obbligatorio: Consigliato  
  Esempio: `European Commission` / `Publications Office of the EU`  
  Funzione: classificazione fonte.

- **source_uri**  *(NUOVO)*  
  Tipo: string (URL)  
  Obbligatorio: Consigliato  
  Esempio: `https://eur-lex.europa.eu/...`  
  Funzione: tracciabilità e re-download.

- **eli_uri**  *(NUOVO)*  
  Tipo: string  
  Obbligatorio: Consigliato per atti UE  
  Esempio: `https://eur-lex.europa.eu/eli/reg/2023/1803/oj`  
  Funzione: identificatore ELI (European Legislation Identifier).

- **celex_id**  *(NUOVO)*  
  Tipo: string  
  Obbligatorio: Consigliato (se CELEX)  
  Esempio: `02023R1803` oppure `32023R1803`  
  Funzione: indicizzazione Eur‑Lex.

- **oj_id**  *(NUOVO)*  
  Tipo: string  
  Obbligatorio: Consigliato (se OJ)  
  Esempio: `OJ:L:2026:338` oppure `OJ_L_202600338`  
  Funzione: riferimento alla GUUE.

- **source_type**  
  Tipo: enum (es. `eu_legislation`, `iasb_standard`, `efrag`, `big4`, `other`)  
  Obbligatorio: Consigliato  
  Esempio: `eu_legislation`  
  Funzione: filtri per gerarchia e policy.

---

### 3.4 Gerarchia e authority (lettura “con precedenza”)

- **source_tier**  *(NUOVO)*  
  Tipo: integer (1..5)  
  Obbligatorio: Consigliato  
  Esempio: `2`  
  Funzione: regola di precedenza nella risposta/grounding.

  Proposta tier:
  1 = Diritto UE “base” (es. Reg. 1606/2002)  
  2 = Regolamenti Commissione di adozione/modifica IFRS (OJ + 2023/1803)  
  3 = IASB standards “as issued” (IAS/IFRS/IFRIC/SIC)  
  4 = EFRAG (advice, effect studies)  
  5 = Big4 / prassi professionale (commentary)

- **authority_level**  *(NUOVO)*  
  Tipo: enum (`binding_text`, `endorsed_standard`, `consolidated_reference`, `non_binding_guidance`, `commentary`)  
  Obbligatorio: Consigliato  
  Esempio: `binding_text` (per OJ) / `consolidated_reference` (per CELEX consolidato)  
  Funzione: controllare cosa “fa fede” e come citare.

- **authority_note**  
  Tipo: string  
  Obbligatorio: Opzionale  
  Esempio: `Consolidated text for documentation; OJ is legally authentic.`  
  Funzione: spiegazione da mostrare in UI o appendice.

---

### 3.5 Date, versioni, efficacia

- **publication_date**  
  Tipo: string (ISO date `YYYY-MM-DD`)  
  Obbligatorio: Consigliato  
  Esempio: `2026-02-19`  
  Funzione: timeline normativa.

- **effective_date**  *(NUOVO)*  
  Tipo: string (ISO date)  
  Obbligatorio: Opzionale  
  Esempio: `2027-01-01`  
  Funzione: regole “da quando si applica” (es. IFRS 18).

- **consolidated_as_of**  *(NUOVO)*  
  Tipo: string (ISO date)  
  Obbligatorio: Opzionale  
  Esempio: `2025-07-30`  
  Funzione: data del testo coordinato CELEX.

- **version_label**  
  Tipo: string  
  Obbligatorio: Opzionale  
  Esempio: `2025-07-30` oppure `v1`  
  Funzione: versionamento umano.

---

### 3.6 Relazioni normative (amendments)

- **amends**  *(NUOVO)*  
  Tipo: array[string] (doc_family_id o doc_id)  
  Obbligatorio: Opzionale  
  Esempio: `["EU:REG:2023/1803"]`  
  Funzione: questo atto modifica altri atti.

- **amended_by**  *(NUOVO)*  
  Tipo: array[string]  
  Obbligatorio: Opzionale  
  Esempio: `["EU:REG:2026/338"]`  
  Funzione: questo atto è modificato da altri atti.

- **repeals**  
  Tipo: array[string]  
  Obbligatorio: Opzionale  
  Esempio: `["IAS:IAS_1"]`  
  Funzione: gestire abrogazioni/ritiri (utile con IFRS 18).

- **replaced_by**  
  Tipo: array[string]  
  Obbligatorio: Opzionale  
  Esempio: `["IASB:IFRS_18"]`  
  Funzione: relazioni di sostituzione (utile anche in Graph DB).

---

### 3.7 Ambito contenutistico (classificazione)

- **topic_tags**  
  Tipo: array[string]  
  Obbligatorio: Opzionale  
  Esempio: `["IFRS", "endorsement", "financial statements presentation"]`  
  Funzione: filtri e routing query.

- **standard_tags**  
  Tipo: array[string]  
  Obbligatorio: Opzionale  
  Esempio: `["IFRS 18", "IAS 1"]`  
  Funzione: retrieval mirato per standard.

---

### 3.8 Campi “glossario” (per bilingua)

Questi campi NON vanno per forza in ogni documento. Si consiglia un file separato di glossario versionato; tuttavia puoi referenziarlo:

- **glossary_ref**  *(NUOVO)*  
  Tipo: string (path o id)  
  Obbligatorio: Opzionale  
  Esempio: `data/glossary/ifrs_terms_v1.json`  
  Funzione: collegamento al glossario usato per normalizzare i termini.

- **preferred_terminology**  *(NUOVO)*  
  Tipo: enum (`it`, `en`, `auto`)  
  Obbligatorio: Opzionale  
  Esempio: `auto`  
  Funzione: suggerimento al generatore (prompt) su lingua/termini.

---

## 4. Esempio record (catalog.json)

```json
{
  "doc_id": "eu_reg_2023_1803_it_celex_consolidated_2025-07-30",
  "path": "corpus_raw/eu/CELEX_02023R1803-20250730_IT_TXT.pdf",
  "file_format": "pdf",
  "sha256": "…",
  "bytes": 9612345,

  "title": "Regolamento (UE) 2023/1803 della Commissione",
  "publisher": "Publications Office of the EU",
  "source_type": "eu_legislation",

  "jurisdiction": "EU",
  "language": "it",
  "doc_family_id": "EU:REG:2023/1803",
  "doc_variant": "celex_consolidated",
  "canonical_rank": 0,

  "celex_id": "02023R1803",
  "eli_uri": "https://eur-lex.europa.eu/eli/reg/2023/1803/oj",
  "source_uri": "https://eur-lex.europa.eu/…",

  "authority_level": "consolidated_reference",
  "source_tier": 2,
  "authority_note": "Consolidated text for documentation; OJ is legally authentic.",

  "publication_date": "2023-08-10",
  "consolidated_as_of": "2025-07-30",

  "topic_tags": ["IFRS", "endorsement"],
  "standard_tags": ["IAS", "IFRS", "IFRIC", "SIC"],
  "glossary_ref": "data/glossary/ifrs_terms_v1.json"
}
```

---

## 5. Raccomandazioni operative (minime, per non rompere MVP)

1) Aggiungi i campi nuovi come **opzionali** (default null).  
2) Implementa nel retriever:
   - filtro `language` coerente con la query;
   - deduplica per `doc_family_id` (a parità di “intent”).
3) In generazione risposta:
   - per affermazioni “normative”: preferisci `authority_level=binding_text` (OJ) se disponibile;
   - usa `celex_consolidated` per contesto, ma non come “testo autentico”.

---

## 6. Prossimo passo consigliato

Se mi condividi (anche copiaincolla) un singolo record del tuo catalog MVP, ti restituisco una **v0.2 finalizzata** con:
- mappatura 1:1 tra campi MVP e nuovi campi,
- valori default,
- regole di validazione (JSON Schema) e check automatici in pipeline.
