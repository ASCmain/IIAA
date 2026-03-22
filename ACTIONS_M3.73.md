# ACTIONS_M3.73

## Oggetto
Focus enforcement conservativo e maggiore osservabilità del policy layer RAG.

## Interventi
- focus enforcement conservativo sul bucket `core/context` in base al `primary_standards` rilevato;
- serializzazione di `max_core`, `max_context` e `policy_trace`;
- miglioramento del tracker `used_citations` con regex robusta contro varianti del blocco finale citazioni;
- arricchimento del benchmark con segnali di pianificazione e policy applicata.

## Razionale
I casi critici mostravano che:
- il focus veniva riconosciuto correttamente;
- ma non sempre rispettato nella selezione finale delle evidenze;
- e i pesi/soglie per tipologia di domanda non erano ancora abbastanza osservabili.

## Beneficio
- migliore auditabilità della classificazione domanda → policy;
- maggiore controllo sul perché una risposta usa certe fonti;
- base più solida per eventuale tuning successivo dei pesi.
