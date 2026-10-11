# Prima versione React/TypeScript di IPF Mapper

Questa consegna è una prima versione funzionale della migrazione per fasi, non la sostituzione integrale e certificata di tutte le funzioni M1–M7.2. I dati originali e il client Python sono conservati. L'assessment è stato scritto prima del porting.

## Architettura e file

| Percorso | Responsabilità |
| --- | --- |
| `src/domain/model.ts` | Schemi Zod, tipi strict, catalogo, gerarchia tipi, firme, proprietà e VA/NVA/NNVA |
| `src/domain/commands.ts` | Comandi immutabili, undo/redo, membership, vincoli e history |
| `src/domain/graph.ts` | Proiezioni dei flow/INPUT/OUTPUT/dipendenze, SCC per cicli |
| `src/domain/validation.ts` | Regole modulari: riferimenti, firme, cardinalità, proprietà, ownership, flow, gruppi, loop, decisioni |
| `src/domain/analysis.ts` | Durate con unità esplicite, KPI strutturali, confronto per UID e ricette configurate a tre valori |
| `server/database.ts` | Adapter legacy → dominio, backup, migrazioni additive, repository e transazioni SQLite |
| `server/index.ts` | API locale, validazione richieste, protezione origin/host, lettura storico e servizio build |
| `src/state/useEditor.ts` | Stato persistito/history separato da selection/drag, autosave serializzato, conflitti e recovery |
| `src/services/api.ts` | Contratti runtime, richieste e JSON UTF-8 |
| `src/components/EditorCanvas.tsx` | Proiezione visuale, lane viewport-aware, gruppi, relazioni, movimento e navigazione XYFlow |
| `src/components/ProcessNode.tsx` | Rendering memoizzato per tipo, proprietà e criticità rosse |
| `src/components/Inspector.tsx` | Proprietà applicabili dal catalogo, ownership, membership e classificazione |
| `src/components/AnalysisPanel.tsx` | Metriche, validazione, confronto e stati configurati |
| `src/components/ParameterForm.tsx` | Modifica esplicita dei parametri di policy, senza soglie nel codice |
| `src/components/ExecutionDetails.tsx` | Osservazioni e correzioni storiche in sola lettura |
| `src/App.tsx`, `src/main.tsx`, `src/styles.css`, `index.html` | Composizione workspace, dialoghi, shortcut, design tokens e layout responsive |
| `tests/` | Suite dominio, SQLite e flussi browser su fixture isolate |
| `package.json`, `package-lock.json`, `tsconfig.json`, `vite.config.ts`, `vitest.config.ts`, `playwright.config.ts`, `.gitignore`, `.node-version` | Toolchain riproducibile, build strict e runner |
| `legacy/IPF_Mapper_M7.2/` | Tutto il pacchetto originale preservato |
| `docs/`, `README.md` | Decisioni, conservazione, istruzioni e limiti |

React Flow è adottato per interazioni mature e per il rendering React. Non sono ricostruiti da zero minimap, selection, resize, handles, zoom e pan. React gestisce la composizione; Zod valida dati esterni; Express espone SQLite di Node 24. Le librerie e alternative sono motivate nell'assessment. Nessun mega-store: il dominio è un documento canonico, history è distinta, React Flow gestisce lo stato transitorio, selection è locale al workspace, recovery è locale al browser. Non si interpreta la geometria come dipendenza business.

## Stato delle funzionalità

| Capacità | Stato e limiti |
| --- | --- |
| Aprire dati M7.2 | Implementato sull'intero database demo incluso; path esterno configurabile, DB personale non fornito |
| Metamodello e proprietà | Cataloghi e gerarchie del DB, relazioni tipizzate e proprietà applicabili; unknown values non eliminati |
| Lane | Funzioni/participant/subtipi dinamici, viewport e contenuto; label leggibili; resize dell'area |
| Azioni, informazioni, mezzi, decisioni | Create/edit/move/delete/duplicate, proprietà e classificazione; DECISION deriva da ACTION |
| Relazioni e flow | Handle, editor di flow SOURCE/TARGET/VIA/CARRIES/LT, INPUT invertito solo visualmente, reconnect |
| Gruppi | Create/drop/render/persist, proprietà, resize, membership, nested groups, move, collapse, group/ungroup; cicli vietati |
| Navigazione | Pan background/Space/middle, wheel/zoom, fit, minimap, focus/search, viewport persistito |
| Productivity | Selezione multipla, snapping, align/distribute, copy/paste, undo/redo, lock e pannelli collassabili |
| Persistenza | Transazioni, backup, snapshot immutabili, clone, autosave, dirty state, recovery e conflitti 409 |
| Import/export | JSON canonico nello stesso processo; apertura SQLite via servizio locale; altri formati non implementati |
| Validazione | Riferimenti, firme, cardinalità, proprietà, ownership, nodi isolati, informazioni orfane, flow incompleti, cicli e decisioni senza esiti sufficienti |
| Analisi AS-IS/TO-BE | Aggiunti/eliminati/modificati per identità, ownership, mezzi, flow, membership, relazioni, tempi/proprietà, classificazioni e metriche strutturali |
| Parametri e policy | Valori persistiti modificabili; ricette M7.1 di confronto/completed valutate senza policy nel codice |
| Regole | Libreria con creazione, modifica e rimozione di regole di stato: confronto e prerequisito completato; compilazione AST compatibile, definizioni precedenti preservate. Espressioni generali/derivazioni avanzate restano legacy |
| Libreria processi | Libreria progetti ricercabile, creazione di workspace/processo vuoto e prima revisione AS-IS, apertura e clone delle revisioni |
| Esecuzioni | Lettura istanze, osservazioni e correzioni; inserimento, snapshot di esecuzione e analisi runtime completa restano Python |
| Analisi avanzata | Niente lead time/saving arbitrario, inferenza di parallelismo da layout, bottleneck senza evidenza, heatmap o worker non verificati |

## Differenze e UX
Il canvas è principale, con sidebar richiudibile, inspector contestuale, analisi in drawer, toolbar compatta, navigazione per ricerca e minimap. Lane colorate e marker/bordi/edge rossi mantengono l'identità IPF. Proprietà sono generate dal catalogo invece di essere duplicate in form PySide. Le funzioni hanno una rappresentazione generale e i gruppi usano la stessa abstraction dei node type; membership è una relazione, non una gerarchia DOM persistita. L'azione INPUT conserva il contratto originale. UTF-8 viene mantenuto per sorgenti/HTML/API/SQLite/file; non si applicano sostituzioni ad hoc.

## Test e limiti di evidenza
Le suite e i comandi sono nel README. Test di dominio: catalogo, adapter reale, serializzazione, comandi, classificazioni, grafi, validazione e policy parametrica. Test SQLite: integrità storica, migrazione ripetibile, snapshot immutabili, clone, rollback, conflitti, restore di membership e path errati. Test Playwright: aprire/modificare/ricaricare, gruppi/drop, TO-BE/confronto, handles, drag, pan/zoom, resize/collapse. I test desktop non GUI sono stati eseguiti separatamente; i test Qt restano non eseguiti perché PySide6 manca. I controlli non certificano ogni processo possibile né la scala massima di 20000 elementi accettata dallo schema.

## Debito e prossime fasi
1. Validare una copia del database personale e confronto semantico col client Python sul deployment effettivo.
2. Portare il motore completo di espressioni/derivazioni, editor di espressioni avanzate e validation specifica delle loro AST con test di equivalenza Python/TS.
3. Portare creazione snapshot di execution, osservazioni e correzioni, analisi degli intervalli, waiting, repeat/rework, parallelismo osservato e storico/scenario.
4. Allargare test di reconnect, nested groups, recovery conflittuale, accessibilità, dispositivi touch e benchmark su processi grandi. Il rendering è memoizzato e viewport-cullato, ma non c'è una promessa di performance basata su benchmark non eseguiti.
5. Layout automatico ELK come comando annullabile, pannelli ridimensionabili/docking solo se utili, audit log persistente anziché sola history in memoria, report e heatmap supportati da evidenze.
6. Se serve multiutenza: autenticazione/ACL, controllo concorrenza anche sul legacy, cataloghi con codici ambigui per workspace e politica di deployment. Non esporre il server locale in rete come se fosse già un servizio SaaS.

La configurazione cloud salvata prepara Node e dipendenze/build/test e registra come riavviare i servizi. Un salvataggio della bozza non equivale a pubblicazione né a verifica di ripristino in un nuovo task.

Esiti e perimetro della verifica effettivamente eseguita: [VERIFICATION.md](VERIFICATION.md).

Schermate della nuova implementazione: [editor](editor.png) e [analisi](analysis.png).

## Correzioni UX e parità dopo revisione
- Selezione e mano sono modalità distinte. La mano non trascina nodi, gruppi o lane. Lane come sfondo, coordinate sincronizzate allo zoom e gutter indipendente per etichette; ultimo sfondo copre l’altezza disponibile.
- Vista iniziale al 100%, panoramica esplicita e ritorno al 100%; dimensioni dei controlli e del testo aumentate. Navigazione per categorie richiudibili e ricerca.
- Riutilizzo del preset grafico JSON originale Python solo sui dati RFQ con coordinate baseline ancora intatte. Il preset è una proiezione visuale e non cambia le coordinate persistite; modifiche manuali prevalgono.
- Icone SVG dei mezzi sui flussi, libreria delle icone (Mail, ERP, Database, telefono, Teams, portale, lettera, cloud, corriere, cartella, altro) e scelta nell’inspector. Gli elementi Mezzo possono essere focalizzati dalla navigazione; i flussi mostrano sempre l’icona del canale associato.
- Libreria gruppi persistente SQLite: salvataggio di un gruppo con membri, sottogruppi e relazioni interne; inserimento con nuove identità e codici indipendenti. Le regole e i collegamenti esterni non fanno parte del template.
- Gestione regole di stato nelle revisioni draft. Le modifiche producono nuove definizioni/espressioni, senza alterare le revisioni pubblicate; rimozione della membership conserva i record storici. Le operazioni sulle regole riaprono il documento salvato e ripartono con una nuova history locale.
- Apertura dell’ultimo progetto usato conservata sul browser; revisioni nel selettore limitate al processo corrente.

Schermate aggiornate: [panoramica](overview.png), [progetti](projects.png), [editor regole](rules.png), [elenco regole](rules-list.png), [icone](icons.png).
