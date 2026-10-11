# Assessment e percorso di migrazione

Il pacchetto M7.2 originale è conservato in `legacy/IPF_Mapper_M7.2`. Il README della release descrive ancora M7.1. Il database incluso è il **demo**, non il database personale (desktop: `~/.ipf_mapper/ipf_mapper.db`). SHA-256 originale: `ebc1fa9d166d13b2c3b8d3ee2dbc53e94229eabb60f5ead25a1e06b8b36b96a7`. Integrità SQLite OK, nessuna violazione FK.

## Mappa
- `domain/`: identità/definizioni, gerarchia tipi, grammatica delle relazioni, espressioni, stati a tre valori e analisi.
- `repositories/sqlite/`: cataloghi, revisioni, proprietà tipizzate, istanze e osservazioni.
- `app/controller.py`, `app/workspace.py`: orchestrazione, editor, clone, snapshot, proprietà, regole e analisi.
- `ui/`: canvas QGraphicsScene, widget, form, icone e layout Qt. Si sostituisce con React; non si traduce.
- `resources/demo_m71.db`: dati concreti, 2 revisioni e storico. `database/schema.sql` e migrazioni 0002/0003 descrivono il metamodello.

## Scelte e alternative
React Flow / XYFlow include selection, handles, reconnect, zoom, pan, minimap, resizer e group nodes; è la scelta per un editor React. Konva/Fabric sono canvas generici e richiederebbero implementare tali interazioni; D3 è utile per visualizzazioni, non fornisce un editor completo. ELK offre routing/ports più sofisticati, Dagre layout gerarchici più semplici: nessuno dei due viene imposto ai layout manuali esistenti. Un futuro auto-layout sarà un comando annullabile.

React 19 + TypeScript strict + Vite; Zod valida i contratti runtime; dominio puro fuori dalla UI. Una history di documenti immutabili copre i comandi editor; selection e transient drag restano in React Flow, viewport nel documento, recovery in localStorage. Zustand/Redux non sono necessari per questo perimetro e non vengono aggiunti per principio. Node 24 `node:sqlite` evita addon nativi e accede al database attraverso API locale Express. SQLite nel browser, Electron e Tauri non sono necessari per la prima versione locale. Distribuzione multiutente richiederà autenticazione, ACL, isolamento database e deployment dedicato.

## Dati e rischi
Gli ID stabili devono sopravvivere ai confronti; le definizioni pubblicate non si modificano; INPUT resta Action → Information nel dominio e si proietta in direzione inversa sul canvas. Information Flow è un'entità reificata con SOURCE/TARGET/VIA/CARRIES, non una semplice freccia. CONTAINS e PERFORMER sono relazioni, non coordinate. L'assenza di dipendenza non prova parallelismo eseguito. Tempi aggregati delle attività non equivalgono al lead time di processo. Proprietà sconosciute e storico non devono essere rimossi dai salvataggi.

## Fasi
A. Discovery e fingerprint DB prima del codice. B. Contratti e scelte sopra. C. Adapter del DB, dominio, validazione, metriche e confronto. D. Editor, lane, flow e inspector. E. Gruppi e proprietà generali. F. Confronto revisioni, VA/NVA/NNVA e valutazione delle ricette di stato. G. Verifica browser, recovery, tastiera e documentazione dei limiti. Il motore completo di espressioni/derivazioni e l'editor di osservazioni runtime rimangono legacy finché non sono portati e verificati con equivalenza semantica.
