# IPF Mapper M7.1 — Usable Visual Workspace

Build derivata da `ipf_mapper_milestone7_visual_workspace_hotfix.zip`.
Python 3.10+; verificata con Python 3.12.14 e PySide6 Essentials 6.11.2 su Windows.

## Avvio Windows

1. Estrai **tutto** lo ZIP in una cartella scrivibile.
2. Apri `run_windows.bat`. Al primo avvio crea `.venv` e installa le dipendenze da `requirements.txt` (serve Internet).
3. Si apre **DEMO — Procurement RFQ AS-IS**, già popolato. Il database demo iniziale è incluso nel pacchetto.

Il launcher richiede un’installazione Python 3.10 o successiva. Non è un eseguibile autonomo.
Avvio alternativo: `python -m pip install -r requirements.txt`, quindi `python main.py`.

I dati utente restano in `%USERPROFILE%\.ipf_mapper\ipf_mapper.db`.
Il demo usa `%USERPROFILE%\.ipf_mapper\demo_m71.db`, separato e identificato da un marcatore.
Per una directory diversa: `run_windows.bat --data-dir "D:\IPFData"`.
Libreria IPF mostra l’origine DEMO o I tuoi IPF. **Nuovo IPF crea sempre dati nel database utente**.

## Percorso di prova consigliato

1. Osserva il canvas: auto-fit all’apertura, reload e resize; rotella per zoom, pulsante centrale per pan. Adatta / Ctrl+0 torna al fit.
2. Menu / Ctrl+B nasconde la sidebar; Proprietà / Ctrl+I nasconde l’inspector. L’inspector è inizialmente chiuso per lasciare spazio al processo.
3. Seleziona un nodo o un elemento dal menu sopra il canvas. Modifica nome, codice, descrizione, performer, T/C, criticità, severità o nota e salva. Le proprietà offerte dipendono dal tipo. Ctrl+S salva; cambiare selezione/schermata salva le modifiche valide.
4. Doppio clic su Supplier A / Supplier B espande o collassa il gruppo. I flow esterni vengono proiettati sul gruppo collassato, senza cambiare le relazioni di dominio.
5. Aggiungi una Function: non presenta un campo performer. Aggiungi una Action e assegnale una Function. Cambiare performer aggiorna anche la riga visuale dell’attività.
6. Aggiungi un Means dalla libreria visuale oppure inserisci un nome personalizzato: riceve l’icona Generic. Le stesse icone compaiono sulle transizioni; Label mezzi è opzionale.
7. Collega supporta le firme del catalogo, comprese Action → Information (OUTPUT) e Information → Action (INPUT). Nel database INPUT mantiene la firma Action INPUT Information. Action → Action apre l’editor Information Flow. Information → Information è rifiutato perché il catalogo corrente non definisce una firma valida.
8. Information Flow consente source, target, information già esistente, means e lead time. Per modificarlo seleziona la linea oppure il flow dall’elenco elementi. Means e LT sono della transizione; T/C è dell’attività.
9. Apri Rules, modifica `MANAGEMENT_APPROVAL_THRESHOLD` da 500000 a 750000 e salva. In Analysis, scenario della revisione aperta, **Approva PO passa da REQUIRED a OPTIONAL**, con PO = 620000. Cerca “Approva” per filtrare gli stati.
10. In Analysis scegli Storico: regole dello snapshot. L’approvazione torna REQUIRED perché DEMO PROJECT #001 ha conservato la configurazione 500000. Cambiare `TECHNICAL_ISSUE` a false rende Technical Alignment NOT_APPLICABLE nello scenario.
11. Execution mostra istanze, osservazioni e relativi timestamp. Seleziona un’istanza per lo storico; aggiungi nuove istanze/osservazioni, oppure registra una correzione esplicita fra due istanze dello stesso elemento.
12. Analysis → Processo mostra il parallelismo osservato Supplier A/B, attese, ITERATION su Analizza offerte e REWORK su A · Prepara offerta. Il monitoraggio senza timestamp produce UNKNOWN. I candidati di parallelismo hanno come ambito le attività del modello; non sono prove di esecuzione parallela.
13. Reset Demo ripristina solo il demo dopo conferma. Il caricamento ordinario non duplica né sovrascrive le modifiche al demo.

## Revisioni, regole ed esecuzioni

Le modifiche si salvano nella revisione DRAFT. Copia revisione crea definizioni indipendenti e copia proprietà, parametri, regole e layout. Le revisioni pubblicate restano immutabili.

“Execution da snapshot” valida, copia e pubblica uno snapshot; il draft resta modificabile. Le nuove istanze sono legate alle definizioni dello snapshot. L’analisi Scenario usa i fatti runtime con parametri/proprietà della revisione aperta; l’analisi Storico usa il modello eseguito.

Rules permette di creare, modificare e rimuovere regole configurate per APPLICABILITY, REQUIREMENT ed ENABLEMENT, mediante confronti fra parametri/proprietà/costanti o un prerequisito COMPLETED. Valutazione ed espressioni sono affidate ai motori esistenti M1–M5. Le regole M2 già presenti sono elencate e valutate; l’editor visuale di M7.1 è dedicato alle regole di stato, non a ogni possibile albero di espressione M2.

Le soglie e tutte le specificità procurement si trovano nel seed `ipf/app/demo_rfq.json` e nei dati salvati. I motori non contengono la policy procurement.

## Verifica ripetibile

Dopo il primo avvio, `run_tests.bat` esegue la suite e `verify_release.py`: syntax/import, database temporanei, FK/integrity check e screenshot Qt.
In alternativa: `python -m unittest discover -s ipf/tests -v` oppure `python verify_release.py`.

Il pacchetto include `verification/tests.txt`, `verification/verification.json` e le schermate effettivamente renderizzate. I test Qt vengono esplicitamente saltati se PySide6 manca; non sono sostituiti da rendering simulato.

Questa build è destinata alla validazione del dominio: i risultati automatici sono evidenze su casi definiti, non una certificazione della correttezza di ogni processo reale.
