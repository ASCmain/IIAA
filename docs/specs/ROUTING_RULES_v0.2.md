# IIAA — Regole di routing (v0.2)

.env per questa fase: **.env.corpus** (o equivalente). Verificalo solo a inizio nuova chat o quando cambi fase/tool.

Questo documento definisce regole “complete” e operative per:
1) determinare la lingua della query (IT/EN/mista),
2) normalizzare la terminologia tramite glossario IT↔EN,
3) costruire piani di retrieval (vector + opzionale graph),
4) applicare gerarchia delle fonti (tier/authority),
5) deduplicare e scegliere il “canonical set” di evidenze,
6) citare correttamente (OJ vs CELEX consolidato, ecc.).

Il design è compatibile con un RAG ibrido: Vector DB (retrieval) + Graph DB (routing/relazioni) + LLM (sintesi grounded).

---

## 1. Terminologia e obiettivi del routing

- **Routing**: scelta dei filtri e della strategia di retrieval in base alla query (lingua, dominio, tipo domanda).
- **Goal**: massimizzare *coverage* e *precision* riducendo duplicazioni e “bias” (es. stessa norma recuperata 2 volte in IT/EN).

---

## 2. Riconoscimento lingua query (Query Language Detection)

### 2.1 Classificazione principale (3 stati)
- `query_lang = it`
- `query_lang = en`
- `query_lang = mixed`

### 2.2 Regole pratiche (deterministiche, senza modelli esterni)
Usa indicatori leggeri (keyword + caratteri + stopwords) e un punteggio.

A) Tokenizzazione
- lower-case
- split su spazi e punteggiatura
- conserva acronimi (IFRS, IAS, ECL, RoU, etc.)

B) Score
- `score_it`: conteggio stopword IT + pattern (es. “il/la/lo”, “ai sensi”, “bilancio”, “rilevazione”)
- `score_en`: conteggio stopword EN + pattern (es. “the/of”, “recognition”, “measurement”, “disclosure”)
- `score_tech`: conteggio acronimi/termini IFRS (neutral)

C) Decisione
- se `score_it >= score_en * 1.3` → it
- se `score_en >= score_it * 1.3` → en
- altrimenti → mixed

### 2.3 Eccezioni
- Se la query è in IT ma contiene molti termini IFRS in EN (es. “right-of-use asset”, “lease liability”) → mixed.
- Se la query è brevissima (< 6 token) → fallback su `auto` con retrieval bilingue bilanciato (vedi §4).

---

## 3. Normalizzazione terminologica (glossario IT↔EN)

### 3.1 Obiettivo
- Mappare sinonimi e varianti a un lemma “canonico” (es. IT e EN).
- Creare due rappresentazioni della query:
  - `q_user`: query originale (per UI e logging)
  - `q_norm_it`, `q_norm_en`: query normalizzate per retrieval

### 3.2 Regole
Dato un glossario (es. `ifrs_terms_v1.json`) con campi `lemma_it`, `lemma_en`, `aliases_it`, `aliases_en`:

- Per ogni n-gram (1..4 token) della query:
  - se match in `aliases_it` o `lemma_it` → sostituisci con `lemma_it` in `q_norm_it`
  - se match in `aliases_en` o `lemma_en` → sostituisci con `lemma_en` in `q_norm_en`
- Se match solo su una lingua:
  - copia anche sull’altra lingua usando la coppia equivalente (es. impairment ↔ perdita di valore)

Output:
- `q_norm_it` (sempre)
- `q_norm_en` (sempre)

---

## 4. Routing retrieval (Vector DB)

### 4.1 Filtri standard
Ogni query produce un “retrieval plan” con filtri su metadati (quando disponibili):
- `language`
- `jurisdiction`
- `source_type`
- `source_tier`
- `authority_level`
- `doc_variant`
- eventuali `standard_tags` (IFRS 16, IAS 36, ecc.)

### 4.2 Regole di scelta lingua per retrieval
Definisci una distribuzione `lang_mix` (pesi che sommano a 1).

- Se `query_lang = it`:
  - `lang_mix = {it: 0.85, en: 0.15}`
- Se `query_lang = en`:
  - `lang_mix = {en: 0.85, it: 0.15}`
- Se `query_lang = mixed`:
  - `lang_mix = {it: 0.55, en: 0.45}`
- Se `query_lang = auto_short` (query < 6 token):
  - `lang_mix = {it: 0.50, en: 0.50}`

### 4.3 Regole di scelta “documenti canonici” (OJ vs CELEX)
Per normativa UE:
- per affermazioni normative e citazioni: preferisci `authority_level=binding_text` + `doc_variant=oj` quando presente
- per contesto lungo e ricerca interna: includi anche `authority_level=consolidated_reference` + `doc_variant=celex_consolidated`

In retrieval plan, implementa due passaggi (two-pass):

Pass 1 (binding-first):
- filtri: `authority_level in {binding_text, endorsed_standard}`
- `top_k = K1` (es. 8)
- lingua secondo `lang_mix`

Pass 2 (context):
- filtri: `authority_level in {consolidated_reference, non_binding_guidance, commentary}`
- `top_k = K2` (es. 12)
- lingua secondo `lang_mix`
- opzionale: amplia `source_tier` se coverage basso

### 4.4 Adaptive expansion (copertura bassa)
Se dopo Pass 1+2:
- pochi risultati (es. < 6 evidenze),
- oppure bassa confidenza (es. score medio < soglia),
allora:
- aumenta peso della lingua secondaria (es. 0.30),
- rimuovi filtro `jurisdiction` se la domanda è IASB “as issued”,
- espandi a tier 3–5 (IASB/EFRAG/Big4) secondo il tipo di domanda.

---

## 5. Routing “tipo domanda” (dominio / intent)

### 5.1 Classi di intent (minime)
- `intent = normative` (richiesta “cosa dice la norma”, requisiti, obblighi)
- `intent = application` (come applicare, esempi, casi)
- `intent = disclosure` (informativa, note, disclosure requirements)
- `intent = comparison` (IFRS vs IAS, differenze, prima/dopo)
- `intent = governance` (rischi IA, compliance, controlli)

### 5.2 Heuristic classifier (rule-based)
Esempi:
- “ai sensi”, “articolo”, “regolamento”, “deve”, “shall”, “requires” → normative
- “come si contabilizza”, “example”, “in practice”, “case study” → application
- “informativa”, “disclosure”, “note to the financial statements” → disclosure
- “differenza”, “compare”, “versus”, “prima/dopo” → comparison
- “risk”, “GDPR”, “AI Act”, “governance” → governance

### 5.3 Mapping intent → tier/authority
- normative: tier 1–3, authority alta (binding_text / endorsed_standard)
- application: tier 2–5 con bilanciamento; include Big4/EFRAG
- disclosure: forte su IASB standards + eventuali Big4 per checklist
- comparison: include versioning (effective_date) e atti di modifica
- governance: include fonti UE (GDPR/AI Act) + prassi (CNDCEC/Big4)

---

## 6. Deduplica e selezione evidenze

### 6.1 Deduplica document-level
Rimuovi duplicati per `doc_family_id` + `doc_variant` quando:
- stessa lingua, stesso variant, stesso titolo → tieni canonical_rank più basso
Per cross-variant:
- Se hai sia OJ che CELEX consolidato per stessa doc_family:
  - conserva entrambi ma assegna priorità: OJ per citazione, CELEX per contesto.

### 6.2 Deduplica chunk-level (consigliata)
Se nel MVP hai `chunk_id` / `chunk_hash`:
- rimuovi chunk con hash uguale
Altrimenti:
- usa fingerprint (simhash/minhash) come campo runtime non versionato.

---

## 7. Regole di risposta (grounded, con citazioni)

### 7.1 Precedence
Quando la risposta contiene enunciati normativi:
1) cita OJ (binding_text) se presente
2) usa CELEX consolidato per contesto, citando come “testo consolidato”
3) integra IASB/EFRAG/Big4 solo come supporto interpretativo, chiarendo status

### 7.2 Output lingua
- Output primario nella lingua della query (it/en).
- Se query mixed: output in IT (se utente italiano) ma con termini tecnici normalizzati e, dove utile, coppie IT/EN (es. “attività per diritto d’uso / right‑of‑use asset”).

---

## 8. Parametri consigliati (baseline)

- `K1 (binding-first) = 8`
- `K2 (context) = 12`
- `max_evidence_total = 16`
- `min_unique_doc_family = 3` (se <3, attiva expansion)
- `lang_mix` come §4.2

---

## 9. Logging e telemetria (essenziale per tesi)

Logga per ogni query:
- `q_user`, `q_norm_it`, `q_norm_en`
- `query_lang`, `intent`
- `retrieval_plan` (filtri, pesi lingua, K1/K2)
- lista evidenze con (`doc_id`, `doc_family_id`, `language`, `authority_level`, score)
- esito deduplica (#rimossi)

---

## 10. Esempio di “retrieval plan” serializzabile (JSON)

```json
{
  "query_lang": "it",
  "intent": "normative",
  "q_user": "Come cambia la presentazione del conto economico con IFRS 18?",
  "q_norm_it": "Come cambia la presentazione del conto economico con IFRS 18?",
  "q_norm_en": "How does presentation of profit or loss change under IFRS 18?",
  "lang_mix": {"it": 0.85, "en": 0.15},
  "passes": [
    {
      "name": "binding-first",
      "filters": {
        "authority_level": ["binding_text", "endorsed_standard"],
        "source_tier": [1, 2, 3]
      },
      "top_k": 8
    },
    {
      "name": "context",
      "filters": {
        "authority_level": ["consolidated_reference", "non_binding_guidance", "commentary"],
        "source_tier": [2, 3, 4, 5]
      },
      "top_k": 12
    }
  ],
  "dedup": {"by_doc_family": true, "by_chunk_hash": true}
}
```

---

## 11. Checklist implementativa (per MVP → v0.2)

1) Aggiungi campi metadati: `language`, `doc_family_id`, `doc_variant`, `authority_level`, `source_tier`, `canonical_rank`.  
2) Implementa query language detection + query normalization.  
3) Implementa two-pass retrieval + adaptive expansion.  
4) Implementa deduplica doc/chunk e precedence citazioni.  
5) Logga tutto in telemetry.

