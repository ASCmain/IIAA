# Glossario IFRS — seed 100 termini (v0.2)

.env per questa fase: **.env.corpus** (o equivalente). Verificalo solo a inizio nuova chat o quando cambi fase/tool.

Formato consigliato: JSON come fonte canonica + CSV per editing rapido.

Campi:
- term_id: id stabile
- lemma_it / lemma_en: lemmi canonici
- aliases_it / aliases_en: sinonimi/varianti (separati da `|` nel CSV)
- definition_it / definition_en: definizioni brevi (1–2 frasi)
- domain_tags: tag dominio (es. impairment, fair value, disclosure, transition, eu_law, financial instruments)
- standards_refs: standard/atti collegati (es. IAS 36, IFRS 13, IFRS 9, IFRS 7, IFRS 1, EU:REG:2023/1803)

Nota: alcuni record finali possono essere placeholder `todo` da completare durante la curatela.

## Preview (prime 25 righe)

- T001_financial_statements: bilancio ↔ financial statements  [IFRS]
- T002_statement_of_financial_position: stato patrimoniale ↔ statement of financial position  [IFRS 18, IAS 1]
- T003_statement_of_profit_or_loss: conto economico ↔ statement of profit or loss  [IFRS 18, IAS 1]
- T004_statement_of_comprehensive_income: prospetto della redditività complessiva ↔ statement of comprehensive income  [IAS 1, IFRS 18]
- T005_statement_of_cash_flows: rendiconto finanziario ↔ statement of cash flows  [IAS 7]
- T006_notes_to_the_financial_statements: note ↔ notes to the financial statements  [IAS 1, IFRS 7]
- T007_disclosure: informativa ↔ disclosure  [IFRS 7, IFRS 13]
- T008_international_financial_reporting_standa: principi contabili internazionali ↔ International Financial Reporting Standards  [IFRS]
- T009_recognition: rilevazione ↔ recognition  [IFRS Framework]
- T010_measurement: valutazione ↔ measurement  [IFRS Framework]
- T011_presentation: presentazione ↔ presentation  [IFRS 18, IAS 1]
- T012_accounting_policies: politiche contabili ↔ accounting policies  [IAS 8, IFRS 1]
- T013_accounting_estimates: stime contabili ↔ accounting estimates  [IAS 8]
- T014_errors: errori ↔ errors  [IAS 8]
- T015_materiality: materialità ↔ materiality  [IFRS Practice Statement 2]
- T016_going_concern: continuità aziendale ↔ going concern  [IAS 1]
- T017_accrual_basis: competenza economica ↔ accrual basis  [IFRS Framework]
- T018_equity: patrimonio netto ↔ equity  [IAS 1]
- T019_asset: attività ↔ asset  [IFRS Framework]
- T020_liability: passività ↔ liability  [IFRS Framework]
- T021_revenue: ricavi ↔ revenue  [IFRS 15]
- T022_expenses: costi ↔ expenses  [IFRS Framework]
- T023_profit: utile ↔ profit  [IFRS Framework]
- T024_loss: perdita ↔ loss  [IFRS Framework]
- T025_amortised_cost: costo ammortizzato ↔ amortised cost  [IFRS 9]