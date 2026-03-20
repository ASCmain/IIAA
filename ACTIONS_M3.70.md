# ACTIONS_M3.70

## Oggetto
Rendere il benchmark smoke resiliente a errori parziali e selettivo per subset di casi.

## Modifiche introdotte
- persistenza append-only dei risultati per-case in `results.jsonl`;
- gestione `status=ok|error` e campo `error` nei risultati benchmark;
- supporto a selezione di subset tramite `BENCHMARK_CASE_IDS`;
- supporto a comportamento `fail_fast` configurabile tramite `BENCHMARK_FAIL_FAST`;
- gestione di eventi `case_error` in progress bar e telemetria.

## Razionale
In presenza di errori su casi lunghi o computazionalmente intensivi, il benchmark non deve perdere i risultati già completati.
Inoltre è utile poter eseguire rapidamente:
- un solo caso;
- un gruppo mirato di casi;
- l'intera suite.

## Benefici
- maggiore robustezza operativa;
- migliore osservabilità;
- riduzione del costo iterativo di test e debugging.
