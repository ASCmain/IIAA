# ACTIONS_M3.58.md

## Obiettivo
Separare retrieval pool, analysis pool e final citation budget.

## Razionale
Per testi consolidati IAS/IFRS non è sufficiente lavorare con pochi chunk.
Il sistema deve:
- raccogliere un pool ampio sopra soglia;
- applicare fallback di soglia se il pool è troppo piccolo;
- tracciare quantità e tempi;
- distinguere tra fonti analizzate e fonti poi citate.

## File coinvolti
- src/rag/query_planning.py
- src/rag/source_policy.py
- src/rag/orchestrator.py
