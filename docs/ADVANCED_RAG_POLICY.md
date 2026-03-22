# ADVANCED_RAG_POLICY.md

## 1. Scopo del documento

Questo documento descrive la logica di ragionamento architetturale adottata nel project work IIAA per evolvere da un retrieval vettoriale semplice a un **Advanced RAG** più adatto a quesiti professionali in ambito IAS/IFRS.

L'obiettivo non è ottimizzare il sistema su singoli prompt di benchmark, ma definire una **politica generale e difendibile** di:
- comprensione della query;
- selezione delle fonti;
- recupero delle evidenze;
- sintesi grounded.

Il documento costituisce base tecnica per l'appendice metodologica del project work.

---

## 2. Razionale del passaggio da simple RAG a Advanced RAG

Nel dominio contabile-finanziario, un semplice approccio:
- query embedding
- top-k retrieval fisso
- sintesi LLM

non è sufficiente, perché rischia di:
- recuperare evidenze semanticamente simili ma normativamente secondarie;
- confondere testo consolidato vigente, atto modificativo, disclosure, definizioni e standard contigui;
- non distinguere correttamente tra quesiti interpretativi, di transizione, di modifica normativa e di calcolo numerico;
- fornire risposte plausibili ma non pienamente allineate alla gerarchia professionale delle fonti.

Per questo motivo il sistema è stato esteso con un **query planning layer** e una **source policy layer**.

---

## 3. Principio metodologico

La risposta non deve dipendere solo dal modello linguistico, ma da una pipeline di decisione esplicita:

1. **Query understanding**
2. **Query planning**
3. **Source policy**
4. **Retrieval ampio ma governato**
5. **Selezione evidenze**
6. **Prompt grounded**
7. **Sintesi finale**

In questa impostazione, il modello generativo non è il punto di partenza, ma il livello finale di verbalizzazione di un insieme di evidenze filtrate e priorizzate.

---

## 4. Query planning layer

### 4.1 Funzione

Il query planning layer trasforma la domanda in un piano di retrieval generale e spiegabile.

### 4.2 Output del piano

Il piano include almeno:
- `question_type`
- `target_standards`
- `source_preference`
- `needs_change_tracking`
- `needs_transition_focus`
- `needs_disclosure_focus`
- `needs_numeric_reasoning`
- `needs_consolidated_priority`
- `needs_modifying_act_priority`
- `suggested_top_k`
- `notes`

### 4.3 Classi di quesito considerate

Le classi introdotte sono:

- `definition`
- `rule_interpretation`
- `change_analysis`
- `transition_disclosure`
- `numeric_calculation`
- `mixed_numeric_interpretive`
- `comparison`

Questa classificazione è generale e non dipende da benchmark specifici.

---

## 5. Regola generale sulle fonti

### 5.1 Default professionale

Per impostazione predefinita, il sistema privilegia il **testo consolidato vigente**, perché nella pratica professionale il quesito più frequente riguarda la regola applicabile oggi.

### 5.2 Eccezione: atto modificativo esplicito

Se la query richiama in modo esplicito un atto modificativo e chiede:
- modifiche,
- cambiamenti,
- transizione,
- disclosure,

allora la priorità diventa:

1. atto modificativo
2. testo consolidato collegato
3. paragrafi del principio target
4. eventuali fonti laterali o amendment chain solo se pertinenti

Questa è una regola generale, non una scorciatoia su casi benchmark.

---

## 6. Perché top-k fisso non basta

Un semplice `top_k = 5` è metodologicamente debole nel dominio IAS/IFRS.

I motivi principali sono:

- alcuni quesiti richiedono più contesto normativo di altri;
- i quesiti interpretativi e numerico-contabili richiedono non solo la regola core, ma anche definizioni, basi valutative e concetti limitrofi;
- una soglia troppo stretta aumenta il rischio di semplificazioni concettualmente scorrette;
- una soglia troppo larga senza gerarchia aumenta il rumore.

Per questo il sistema evolve verso una logica a più livelli:
- retrieval pool ampio;
- soglia adattiva;
- source hierarchy policy;
- evidenze finali per il prompt.

---

## 7. Threshold adattive per tipo di quesito

La numerosità del retrieval e delle evidenze passate al prompt non deve essere costante.

### 7.1 Change analysis
- retrieval pool: medio-alto
- threshold: medio-basso
- evidenze finali: medie
- gerarchia: stretta sull'atto modificativo e sugli standard target

### 7.2 Transition / disclosure
- retrieval pool: alto
- threshold: medio-basso
- evidenze finali: medio-alte
- gerarchia: atto modificativo + disclosure/transizione + consolidato

### 7.3 Rule interpretation
- retrieval pool: alto
- threshold: medio
- evidenze finali: alte
- gerarchia: principio target + definizioni + basi valutative + standard strettamente connessi

### 7.4 Numeric / mixed numeric
- retrieval pool: alto
- threshold: medio
- evidenze finali: alte
- gerarchia: regola core + basi di misurazione + definizioni + standard strettamente connessi

Questa scelta riflette il fatto che, nei quesiti professionali, il rischio principale non è solo il rumore, ma anche la perdita di contesto rilevante.

---

## 8. Core evidences vs context evidences

### 8.1 Razionale

Non tutte le evidenze hanno lo stesso ruolo.

Per questo il sistema viene impostato verso una distinzione tra:

- **Core evidences**: fonti normative e paragrafi direttamente decisivi per rispondere
- **Context evidences**: fonti di supporto utili a evitare errori concettuali, chiarire basi valutative o collegare regole contigue

### 8.2 Vantaggio

Questa distinzione consente di:
- mantenere grounding forte;
- evitare sovraccarico del prompt;
- non sacrificare il contesto professionale necessario;
- distinguere meglio tra regola principale e materiale esplicativo.

---

## 9. Caso specifico dei quesiti numerici

Nei quesiti numerici il sistema non deve limitarsi a fare calcolo. Deve prima verificare il corretto impianto normativo.

Per questo un quesito numerico viene trattato come combinazione di:
- retrieval della regola applicabile;
- retrieval delle definizioni di misura;
- chiarimento della base valutativa corretta;
- solo successivamente eventuale calcolo o scaffold di calcolo.

Questo evita errori come:
- confondere fair value, value in use, carrying amount, historical cost;
- usare una base misurativa incompatibile con il principio applicabile;
- eseguire un calcolo formalmente corretto ma concettualmente errato.

---

## 10. Implicazioni metodologiche per il benchmark

Il benchmark non deve valutare solo la qualità del testo generato, ma anche:
- il tipo di piano di query prodotto;
- la coerenza della source policy;
- la qualità delle evidenze selezionate;
- la capacità del sistema di non perdere contesto professionale rilevante.

Per questo i run di benchmark vengono estesi per registrare:
- query plan
- source preference
- target standards
- flag numerici / disclosure / transition
- set di evidenze selezionate

---

## 11. Posizionamento rispetto al Graph DB

Il presente layer di query planning e source policy è compatibile con future estensioni basate su Graph DB.

In prospettiva, un Graph DB potrà rafforzare:
- collegamento tra atto modificativo e consolidato;
- relazioni tra paragrafi, definizioni, eccezioni e transizioni;
- catene di amendment;
- query multi-hop su standard collegati.

Tuttavia, la logica attuale è già utile e difendibile anche senza graph traversal esplicito, perché introduce una governance semantica del retrieval.

---

## 12. Conclusione operativa

L'Advanced RAG del project work IIAA non coincide con un semplice incremento del top-k o con un prompt più lungo. Consiste piuttosto in una **politica strutturata di lettura del quesito e delle fonti**.

Il valore aggiunto dell'architettura non deriva solo dal modello linguistico usato, ma dalla capacità del sistema di:
- capire il tipo di domanda;
- attribuire la giusta priorità alle fonti;
- recuperare abbastanza contesto senza perdere precisione;
- distinguere tra evidenze centrali e di supporto;
- sostenere anche quesiti numerici con basi normative corrette.

Questo rappresenta uno dei contributi qualificanti del project work rispetto a un uso generico di strumenti conversazionali non governati.


---

## 13. Evoluzione prevista: core/context prompt grounding

Il passo evolutivo successivo previsto nel project work consiste nel separare le evidenze finali in due bucket:

- `core_evidences`
- `context_evidences`

L'obiettivo è costruire prompt grounded con due livelli di rilevanza:

1. **Core evidences**
   - paragrafi normativi direttamente decisivi
   - disposizioni di recognition, measurement, transition o disclosure direttamente richieste

2. **Context evidences**
   - definizioni
   - measurement bases
   - concetti strettamente collegati
   - standard contigui necessari a evitare errori interpretativi

Questa distinzione consentirà di aumentare il contesto disponibile senza perdere il controllo sulla priorità logica delle fonti.


---

## 14. Source hierarchy metadata-driven

L'evoluzione successiva del layer Advanced RAG introduce una gerarchia delle evidenze basata su metadata reali del corpus, anziché solo su similarità vettoriale.

### 14.1 Doppio asse della gerarchia

La gerarchia è costruita su due assi distinti:

#### A. Legal tier
Esprime la forza giuridica o il ruolo normativo della fonte nel contesto UE.

Esempi:
- `eu_modifying_act`
- `eu_consolidated_reference`
- `other_or_unknown`

#### B. Semantic tier
Esprime la funzione logico-contabile della fonte.

Esempi:
- `target_standard`
- `official_interpretation`
- `framework_concept`
- `related_or_support`

### 14.2 Razionale

Una singola gerarchia lineare sarebbe fuorviante, perché una fonte può avere:
- alta rilevanza giuridica ma funzione descrittiva limitata;
- alta utilità interpretativa ma non essere la fonte primaria da privilegiare come base della risposta.

Per questo il sistema combina:
- stato giuridico della fonte;
- ruolo contabile della fonte;
- relazione con lo standard target della query.

### 14.3 Applicazione pratica

#### Change analysis / transition-disclosure
Priorità tipica:
1. atto modificativo UE
2. testo consolidato UE vigente
3. paragrafi dello standard target
4. interpretazioni ufficiali solo se necessarie
5. supporto laterale

#### Rule interpretation / numeric
Priorità tipica:
1. testo consolidato UE vigente dello standard target
2. paragrafi definitori / recognition / measurement del target
3. standard strettamente collegati come context
4. interpretazioni o supporti secondari

### 14.4 Esempio metodologico: IAS 36 e IAS 38

IAS 38.110/111 non è rumore puro rispetto a IAS 36: costituisce un collegamento normativo reale in materia di impairment delle attività immateriali. Tuttavia, in una query generale sul valore recuperabile di una CGU:
- `IAS 36` deve restare `core`
- `IAS 38.110/111` deve tendere a essere `context`

Questa distinzione evita sia l'esclusione eccessiva di fonti collegate, sia la promozione indebita di fonti non principali a base della risposta.


---

## 15. LLM evidence classifier

Il layer Advanced RAG include una fase opzionale di classificazione locale delle evidenze basata su LLM servito tramite Ollama.

### 15.1 Finalità
L'obiettivo del classificatore non è sostituire la gerarchia normativa o metadata-driven, ma fornire un secondo giudizio semantico locale sulle evidenze candidate.

Le classi previste sono:
- `core`
- `context`
- `exclude`

### 15.2 Modalità operative
- `off`: classificatore disattivato
- `shadow`: il classificatore produce etichette e motivazioni, ma non modifica la selezione finale
- `assist`: il classificatore può assistere in modo conservativo il bucket assignment `core/context`, senza sostituire la source policy normativa

### 15.3 Razionale metodologico
Questa soluzione consente di:
- ridurre progressivamente le euristiche rigide;
- introdurre un livello di giudizio semantico locale;
- mantenere comunque un controllo forte da parte della source policy normativa.

### 15.4 Principio di governance
Nel project work, la decisione finale sulla priorità normativa resta al sistema di policy esplicita. Il classificatore LLM ha inizialmente funzione osservativa e comparativa.

### 15.5 Vincolo di governance operativo
Anche in modalità `assist`, il classificatore locale non promuove automaticamente una evidenza da `context` a `core` contro la logica conservativa del sistema. Il suo ruolo è ridurre rumore residuo e aiutare il bucket assignment senza alterare impropriamente la gerarchia normativa.

---

## 16. Analysis pool adattivo e threshold ladder

Per corpus normativi molto estesi, il sistema non limita l'analisi al solo `top_k` finale. Prima dello split `core/context`, viene costruito un `analysis_pool` più ampio.

### 16.1 Parametri principali
- `analysis_pool_target`: ampiezza obiettivo del bacino di analisi
- `min_candidate_floor`: soglia minima di candidati ritenuta accettabile
- `threshold_fallback_ladder`: ladder di soglie degradabili per evitare eccessiva scarsità di fonti

### 16.2 Razionale
Nel caso IAS/IFRS, il testo consolidato UE può superare ampiamente il volume di un singolo standard o di una sola modifica regolamentare. Per quesiti interpretativi o numerici complessi, una selezione troppo stretta rischia di comprimere eccessivamente il contesto rilevante.

Il sistema adotta quindi una sequenza:
1. retrieval iniziale ampio
2. reranking metadata-driven
3. selezione di un `analysis_pool`
4. pruning conservativo
5. split `core/context`
6. eventuale assistenza del classifier locale

### 16.3 Effetto atteso
Questa architettura consente di:
- evitare risposte basate su un numero troppo ridotto di evidenze;
- mantenere più contesto nei quesiti rule/numeric;
- conservare tracciabilità delle soglie effettivamente usate.

---

## 17. Benchmark smoke e telemetria architetturale

Lo smoke benchmark del project work non serve solo a verificare che il sistema “funzioni”, ma anche a osservare il comportamento architetturale della pipeline.

### 17.1 Segnali tracciati
Per ciascun case vengono tracciati almeno:
- `question_type`
- `source_preference`
- `target_standards`
- `analysis_pool_count`
- `analysis_pool_target`
- `threshold_effective`
- `core_evidences_count`
- `context_evidences_count`
- `classifier_items_count`
- `case_total_ms`
- `query_len_original`
- `query_len_embedded`
- `query_was_truncated`
- `retrieval_query_strategy`

### 17.2 Telemetria di run
Il benchmark smoke produce:
- artifact applicativi in `debug_dump/benchmark_runs/smoke_*/`
- run telemetry in `telemetry/benchmark_smoke/run_*.json`

### 17.3 Utilità metodologica
Questa osservabilità rende il benchmark utile anche come base empirica per:
- confronti tra configurazioni del classifier;
- analisi del costo computazionale locale;
- discussione metodologica in appendice tecnica.

## 18. Query compaction per prompt lunghi

Per prompt estesi, in particolare case study numerici o tracce esercitative, il sistema non usa necessariamente l'intera query testuale nei moduli embedding-based.  
Viene invece costruita una embedding query compattata, finalizzata a:
- rientrare nei limiti tecnici dell'endpoint embeddings;
- mantenere il focus sugli standard target;
- preservare i segnali semantici rilevanti per routing e retrieval.

La query completa resta comunque disponibile per la fase di prompting finale e per la generazione della risposta.

### 18.1 Implicazione benchmark
Nel benchmark finale, la query compattata usata dai moduli embedding-based viene esposta come metadato tecnico. Questo consente di distinguere i limiti infrastrutturali da quelli metodologici del sistema.

### 18.2 Limite residuo sui casi numerici
La query compaction risolve il problema tecnico dei prompt troppo lunghi per l'endpoint embeddings, ma non equivale di per sé a una piena capacità di risoluzione numerico-contabile del caso. Nei case study numerici, il sistema può quindi risultare:
- corretto nel grounding normativo;
- ancora incompleto nell'esecuzione del calcolo end-to-end.

### 18.3 Uso del benchmark su subset selezionati
Per finalità di regression, diagnosi e isolamento dei failure mode, il benchmark può essere eseguito anche su sottoinsiemi selezionati di casi, senza compromettere la comparabilità metodologica della suite complessiva.
