# ACTIONS_M3.62.md

## Obiettivo
Rendere robusto il parser del classifier LLM.

## Problema osservato
Il classifier produce raw_response utile, ma `classifier_items_count=0` in alcuni casi
perché `_safe_parse_classifier_output()` accetta solo JSON perfetto via `json.loads(raw)`.

## Intervento
- parsing diretto
- estrazione del primo blocco JSON plausibile
- tentativo di chiusura assistita di brace/bracket
- validazione soft degli item
