# ACTIONS_M3.76

## Oggetto
Rafforzamento del primary-standard core enforcement e migliore osservabilità core/context.

## Interventi
- rafforzata `apply_focus_enforcement()` per promuovere in core le evidenze allineate al primary standard e demotare le laterali;
- serializzati `core_cite_keys` e `context_cite_keys`;
- rafforzata l'istruzione del prompt grounded: le evidenze core del primary standard devono restare la base della risposta.

## Razionale
Nel caso P9 il sistema classificava correttamente la domanda, ma continuava a fondare la risposta su evidenze laterali non coerenti con lo standard primario.

## Beneficio
- miglior allineamento tra focus detection e grounding reale;
- maggiore auditabilità delle evidenze core versus context;
- base più solida per valutare il caso P9.
