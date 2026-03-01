# IIAA — Addendum HTML-first (Parsing Spec v0.4)

.env per questa fase: **.env.corpus** (o equivalente). Verificalo solo a inizio nuova chat o quando cambi fase/tool.

Questo documento aggiorna lo spec v0.3: sostituisce le fasi P0/P2 per lavorare in modalità **HTML-first** con EUR-Lex, mantenendo invariati:
- marker handling (P3),
- boundary detection (standard/Articles/Annex),
- parsing paragrafi IFRS,
- chunking e anchors.

Obiettivo: ridurre gli errori tipici da estrazione PDF (ordine lettura, header/footer, spezzature) e rendere più deterministico il mantenimento di paragrafi e heading.

---

## 1. Sorgenti e architettura “canonical HTML + audit PDF”

Regola:
- **Canonical ingestion**: HTML EUR-Lex (`source_uri`).
- **Audit trail**: PDF locale (se disponibile) per riproducibilità, confronti, backup offline.

Metadati:
- `source_uri` (HTML)
- `local_pdf_path` (opzionale)
- `downloaded_at` (runtime, in telemetry)
- `sha256` del contenuto HTML scaricato (runtime o salvato nel catalog dopo fetch)

---

## 2. Fetch HTML (P0-HTML)

Input: URL EUR-Lex (legal-content/.../TXT/HTML/?uri=...)
Output: `raw_html` + `raw_text_blocks[]`

### 2.1 Raccomandazioni tecniche
- User-Agent esplicito; gestione retry/backoff.
- Salvataggio raw HTML in `debug_dump/eurlex_raw/` (non versionato) per riproducibilità locale.
- Normalizzazione encoding in UTF-8.

### 2.2 Estrazione “text blocks” (DOM-aware)
Invece di righe da PDF, estrai blocchi testuali in ordine DOM:
- paragrafi (`<p>`)
- heading (`<h1>..<h4>` o elementi con classi/ruoli di heading)
- elementi lista (`<li>`) quando contengono recitals o elenchi standard
- tabelle (solo se contengono testo normativo; altrimenti ignora o serializza separatamente)

Output: `raw_blocks[] = [{"kind":"heading|p|li|table","text":"..."}]`

Nota: EUR-Lex spesso ha contenitori specifici per il contenuto (es. `div#TexteOnly` o simili). L’estrazione deve limitarsi al contenitore principale del testo giuridico, escludendo menu, breadcrumb, footer.

---

## 3. Cleaning HTML (P2-HTML)

### 3.1 Boilerplate
Rimuovi blocchi che contengono:
- elementi di navigazione (“Back to top”, menu, “Official Journal”, cookie banners)
- “This document is a consolidation…” (può essere conservato come `authority_note` ma escluso dal testo indicizzato)

### 3.2 De-hyphenation
Spesso non necessaria in HTML; applicala solo se trovi pattern residuali (da copy/paste).

### 3.3 Marker CELEX (P3 invariato)
I marker in HTML possono apparire:
- come testo inline (`►M3`)
- come nodi dedicati (span)

Applica le regole v0.3:
- rimuovi marker dal testo visibile
- opzionalmente registra `amendment_marker` in metadati.

---

## 4. Boundary detection (invariato, ma più robusto)

In HTML, i boundary “Article”, “ANNEX”, “INTERNATIONAL ACCOUNTING STANDARD …” di solito sono in heading o paragrafi distinti.
Applica le stesse regex del v0.3 su `block.text`.

Suggerimento:
- se un heading contiene “Article”/“ANNEX”, trattalo come boundary “forte”.

---

## 5. Paragrafi IFRS (invariato)

Riconoscimento paragrafi numerati come v0.3, ma con vantaggio:
- spesso `para_key` e testo stanno nello stesso `<p>` → minor rischio di “spillover” tra paragrafi.

Se EUR-Lex separa `para_key` in `<span class=...>`, ricomponi: `para_key + " " + rest`.

---

## 6. Vantaggi / rischi e mitigazioni

Vantaggi:
- migliore preservazione di heading e struttura
- riduzione rumore header/footer
- minori errori di ordine lettura
- chunking più “auditabile” (meno dipendente da layout)

Rischi:
- layout HTML può cambiare nel tempo (classi/DOM); mitigazione: estrazione per container “testo” + fallback regex su tutto il body.
- marker CELEX restano; mitigazione: gestione P3 + metadato `doc_variant`.

---

## 7. Output e validazioni (identiche a v0.3)

Le validazioni su coverage, marker leakage, deduplica e anchor integrity restano uguali.
