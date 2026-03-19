# ACTIONS_M2.6

## Oggetto
Fix del parser robusto per output JSON troncati del classifier LLM locale e verifica end-to-end nel benchmark smoke.

## Problema osservato
Nel caso `pw_ifrs7_reg_2025_1266_disclosure_transition`, il classifier locale produceva `raw_response` con struttura JSON quasi valida ma troncata nell'ultimo oggetto dell'array `items`. Il parser precedente restituiva:
- `classifier_items_count = 0`
- `classifier_label_counts = {}`

pur in presenza di output semanticamente recuperabile.

## Diagnosi
Sono stati eseguiti:
- ispezione del file `src/rag/evidence_classifier.py`;
- test diretto di `_safe_parse_classifier_output(raw)` sul `classifier_raw_response` salvato nel benchmark;
- confronto tra `results.jsonl` e `summary.json`.

## Intervento
È stato introdotto un recovery layer più robusto:
- parsing diretto del JSON;
- estrazione del primo oggetto JSON plausibile;
- chiusura assistita del JSON troncato;
- recovery specifico dell'array `items`;
- inserimento delle graffe mancanti prima della `]` finale nel caso di ultimo oggetto incompleto.

## Verifica
Test manuale su raw reale:
- `items_count = 3`
- `parse_error = ""`

Rerun benchmark smoke:
- `pw_ifrs7_reg_2025_1266_disclosure_transition`
  - `classifier_items_count = 3`
  - `classifier_label_counts = {"context": 2, "core": 1}`
  - `core_evidences_count = 2`
  - `context_evidences_count = 2`

## Valore architetturale
Il classifier locale è ora:
- osservabile;
- auditabile;
- resiliente a output strutturati incompleti.

Questo giustifica nel project work l'adozione di un parser robusto come parte integrante del layer Advanced RAG locale.

