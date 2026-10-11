# Verifica eseguita · 11 ottobre 2026

| Controllo | Esito |
| --- | --- |
| Installazione congelata `npm ci` | Passata con cache scrivibile `/workspace/.npm-cache` |
| `npm run build` | TypeScript strict e build Vite passati; bundle separati React/canvas/validation/app |
| `npm test` | **27/27 passati**: 17 dominio, 10 database |
| `npm run test:e2e` | **7/7 passati** su Chromium di sistema, fixture SQLite isolata |
| Test Python originali non GUI | **67/67 passati** |
| Discovery Python completa | Non verde: 10 test GUI skipped e import del modulo M7.2 GUI fallito per PySide6 assente |
| Integrità DB originale | `ok`, FK senza violazioni, UTF-8 |
| Preservazione del pacchetto | **79 file originali identici byte per byte** allo ZIP allegato |
| SHA-256 DB originale | `ebc1fa9d166d13b2c3b8d3ee2dbc53e94229eabb60f5ead25a1e06b8b36b96a7` |
| Configurazione cloud | `install_script` e `start_skill` salvati; pubblicazione richiesta, non effettuata dall'agente |
| Avvio nell'istanza corrente | Demo di lavoro, catalogo, documento completo e HTML verificati; UI aperta in Chromium senza errori JavaScript |

I flussi browser hanno verificato: dati legacy, Unicode e classificazione VA salvati/ricaricati; creazione gruppi e undo/redo; clone TO-BE e confronto per identità; drag-and-drop dalla libreria; collegamento dagli handle e Information Flow persistito; drag del nodo, pan e zoom salvati; resize/collapse di gruppo mantenuti al reload; modifica della soglia configurata con ricalcolo REQUIRED → OPTIONAL e snapshot pubblicato identico.

Le correzioni emerse dai test sono nel codice: callback di selezione stabilizzati per evitare un ciclo React/XYFlow; lane label senza intercettazione dei controlli; inserimento con evitamento delle sovrapposizioni; viewport escluso dalla history dei comandi. Un test di grafi verifica anche una catena/ciclo di 20001 vertici senza overflow ricorsivo; non è un benchmark del rendering a tale scala.

Tutti i controlli della nuova app hanno eseguito casi effettivi; non sono stati disabilitati assert o sostituiti test falliti con verifiche vuote. I test Qt non fanno parte della prova della UI React e rimangono non eseguiti. Il database personale, non fornito, il ripristino in un nuovo task cloud, le funzioni dichiarate legacy e il deployment multiutente non sono verificati.

## Aggiornamento UX, progetti, regole e librerie
30 test unitari/integrativi: aggiunti isolamento dei progetti vuoti, input Unicode, authoring/compilazione delle regole e conservazione delle AST e snapshot precedenti, conflitti, rimozione non distruttiva, template da gruppi reali con identità indipendenti. 9 percorsi Playwright includono mano sopra un nodo, cursori distinti, coordinate invariate dopo pan/zoom, sfondi continui, progetto vuoto/reload, modifica regole, icona del mezzo, salvataggio/inserimento di template. Il resize attende la stabilità del controllo prima del trascinamento, dopo l’animazione di focus.

Compatibilità con il motore Python originale: tre nuove AST generate dal backend web (confronto booleano, confronto numerico, attività prerequisito completata) sono state caricate e valutate con `AppController.evaluate_states` su una copia isolata del database. Tutti e tre i risultati coincidono con la valutazione TypeScript. Questa prova riguarda quei tre casi, non l’intero motore di espressioni/derivazioni.

## Correzione dell’avvio con porte occupate
Build strict e Vite passate; **32/32** test unitari/integrativi e **9/9** percorsi browser passati. Due regressioni di avvio verificano porte API/web entrambe occupate, selezione automatica, proxy con origine effettiva e rifiuto di origini esterne; il bind fallito dell’API termina con codice 1 senza dichiarare disponibilità. Verificato anche `npm start` con frontend compilato e API rispondenti su una porta alternativa. I servizi usano un launcher Node senza comandi shell specifici di sistema.
