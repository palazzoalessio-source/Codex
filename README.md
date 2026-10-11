# IPF Mapper · React / TypeScript

Prima versione della migrazione architetturale da Python/PySide M7.2. Modellazione, editor e analisi condividono un dominio TypeScript indipendente dalla UI. Il pacchetto originale completo, incluso il database, rimane in `legacy/IPF_Mapper_M7.2`.

Richiede **Node 24+**. Le versioni delle dipendenze sono congelate in `package-lock.json`.

```bash
cd <cartella-del-progetto>
npm ci
npm run dev
```

Frontend Vite: porta 5173; API locale: porta 3001. Se occupate, l’avvio sceglie porte libere e stampa l’indirizzo esatto da aprire. Il proxy e le origini consentite seguono le porte effettive. `npm run build` verifica TypeScript strict e genera la build; `npm start` serve API e build sulla porta 3001. I servizi ascoltano esclusivamente sul loopback. Non è un deployment pubblico o multiutente.

## Database e dati personali

Lo ZIP contiene **il demo**, non il database personale. Il primo avvio crea `.local/demo-working.db` copiando integralmente `legacy/IPF_Mapper_M7.2/resources/demo_m71.db`. Se la copia esiste, viene riutilizzata senza reset o reseeding. Il database originale è protetto anche da un controllo sul realpath.

Per lavorare su un database M7.2 personale già trasferito sulla macchina:

```bash
IPF_DB_PATH=/percorso/assoluto/ipf_mapper.db npm run dev
```

Il percorso deve esistere: un errore non crea un database vuoto. L'app scrive nel database scelto dopo averne completato un **backup SQLite coerente** in `.local/backups`, anche in presenza di WAL. Usa un percorso scrivibile; chiudi il client desktop durante la sessione di modifica. Il backup precede le migrazioni additive. Non aprire direttamente il file originale del pacchetto. Database precedenti alle tabelle M7.2 richieste vengono rifiutati senza migrazioni distruttive; aggiornarne prima una copia con il client legacy.

Migrazioni: proprietà `VALUE_CLASSIFICATION` applicabile alle azioni (default in lettura `UNCLASSIFIED`); tipo `DECISION` derivato da ACTION; tabelle `web_revision_version` per conflitti e `web_entity_ui` per lock e `web_group_template` per gruppi riutilizzabili. Nessun DROP, reset o eliminazione di record storici. Snapshot PUBLISHED/ARCHIVED sono immutabili. Clone copia definizioni/proprietà, membership delle relazioni/regole, parametri e layout; le identità rimangono stabili. La cancellazione dall'editor rimuove membership dalla revisione e conserva i record originali. I salvataggi sono transazionali; conflitti HTTP 409 non sovrascrivono altri salvataggi. La modifica contemporanea tramite il client Python non aggiorna il contatore web: non usare i due editor contemporaneamente sullo stesso file.

## Utilizzo

- Seleziona una revisione dalla libreria. Copia revisione crea un nuovo DRAFT AS-IS o TO-BE, mantenendo identità e dati di partenza.
- Trascina elementi sul canvas oppure usa i pulsanti della libreria; un gruppo viene creato come vero elemento persistito.
- Collega gli handle: azione → azione crea un Information Flow con source, target, informazione, mezzo e lead time. Information → Action proietta INPUT mantenendo nel database la firma Action INPUT Information.
- Inspector: nome, codice, descrizione, proprietà del catalogo, performer, gruppo, lock e VA/NVA/NNVA. Applica proprietà registra un comando annullabile; cambi di performer aggiornano la lane.
- Pan sullo sfondo; Space + drag; Shift per box selection, Ctrl/Cmd per selezione multipla; zoom, fit e minimap. Griglia attiva anche lo snapping. La larghezza delle lane segue viewport e contenuto.
- Selezione multipla: allinea, distribuisci, raggruppa. Separa gruppo libera i membri senza cancellarli. Gruppi supportano resize, move dei membri, gerarchia e collapse; i flow esterni si proiettano sul gruppo chiuso.
- Ctrl/Cmd+Z: undo; Ctrl/Cmd+Shift+Z o Ctrl+Y: redo; Ctrl/Cmd+D: duplica; Ctrl/Cmd+C/V: copia/incolla della selezione; Delete: rimuovi; Ctrl/Cmd+S: salva.
- Autosave dopo inattività e recovery locale. Una recovery di versione diversa va esportata e confrontata; non viene applicata automaticamente. Gli errori restano visibili e le modifiche locali recuperabili.
- JSON esporta il documento canonico UTF-8. Importa applica un documento valido dello **stesso processo** alla revisione DRAFT attuale. Non è un importatore universale di database o di altri formati legacy. I processi SQLite M7.2 vengono aperti dal servizio Node.
- Analisi mostra indicatori, classificazioni, validazione modulare e confronto tra revisioni. In Stati & regole puoi modificare i parametri salvati e ricalcolare le ricette configurate. Lo storico mostra istanze, osservazioni e correzioni originali in sola lettura.

## Verifica

```bash
npm test
npm run build
npm run test:e2e
```

Vitest usa copie temporanee del database. Playwright usa esclusivamente `.local/e2e.db`, una fixture eliminabile ricreata a ogni esecuzione, e avvia i propri servizi: prima arresta gli eventuali servizi di sviluppo sulle porte 3001/5173. Non modifica `.local/demo-working.db` né il database personale. In questo cloud Chromium è `/usr/bin/chromium`; altrove passa `IPF_CHROMIUM_PATH` con il percorso del tuo browser Chromium compatibile. Il flag `--no-sandbox` del runner riguarda il browser di test nel container.

Per i test originali di dominio, da `legacy/IPF_Mapper_M7.2`, eseguire i moduli `ipf.tests.test_milestone1` fino a `test_milestone71` (senza suffisso GUI). La discovery completa richiede PySide6, perché il test M7.2 GUI lo importa senza skip. La nuova app non dipende da PySide.

Vedi [assessment](docs/ASSESSMENT.md), [stato della migrazione](docs/MIGRATION_REPORT.md) e [verifiche dei dati](docs/DATA_SAFETY.md) per perimetro, evidenze e debito residuo.

### Lavorare su un nuovo progetto
Apri **Progetti → Nuovo progetto**, inserisci il nome del progetto e del processo e scegli **Crea progetto vuoto**. Aggiungi funzioni, attività e informazioni dalla libreria. **Regole** apre la gestione delle regole di stato, con confronti o attività prerequisito e stati configurabili. **Mezzi e icone** apre la scelta visuale del mezzo, disponibile anche nelle proprietà. **Libreria gruppi** salva gruppi riutilizzabili con membri e relazioni interne.

**Seleziona** modifica gli elementi o seleziona una regione; **Mano** sposta esclusivamente la vista. **100%** ripristina una scala leggibile; **Adatta processo** mostra la panoramica completa. Le categorie della navigazione sono richiudibili e la ricerca apre solo i risultati corrispondenti.

### Porta occupata o pagina che non si apre
Avvia una sola volta con `npm run dev`, lascia il terminale aperto e apri l’indirizzo stampato dopo **IPF Mapper pronto**. Una porta occupata viene gestita automaticamente; non occorre terminare altre applicazioni. Per preferire altre porte su PowerShell:

```powershell
$env:IPF_PORT = "3010"
$env:IPF_WEB_PORT = "5180"
npm run dev
```

Per la build completa: `npm run build`, poi `npm start`. Anche questo avvio sceglie una porta libera.
