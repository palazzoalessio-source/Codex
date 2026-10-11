# M7.1 — 4 ottobre 2026

Base: M7 Visual Workspace Hotfix fornita dall’utente. Conservata la correzione controller/canvas e la suite M1–M7.

## Workspace visuale

- Auto-fit calcolato sulla viewport disponibile, apertura/reload, resize; zoom/pan manuali e Adatta.
- Sidebar e inspector collassabili; logo leggibile; inspector inizialmente chiuso.
- Form per tipo: Function senza performer, Action con assegnazione, Information/Means con proprietà pertinenti.
- Inspector editabile con nome, codice versionato, descrizione, T/C, tipo criticità, severità, nota multilinea, performer e proprietà applicabili; indicatore modifiche non salvate.
- Libreria Means con icone vettoriali coerenti Mail, ERP, Database, Phone, Teams, Web Portal, Generic e custom con Generic iniziale. Icona sulla transizione e label opzionale.
- Collega guidato dalla grammatica; INPUT visualizzato Information → Action; Information Flow con editor completo. Nessuna firma Information → Information inventata.
- Gruppi collassabili, inclusi gruppi annidati; flow esterni mantenuti; marker criticità.

## Dominio e dati

- Salvataggi composti atomici; rifiuto di firme/cross-workspace illegali; controllo cicli containment.
- Copia revisione con definizioni e proprietà indipendenti, parametri e layout; protezione delle definizioni pubblicate.
- Rules reale: parametri per revisione, editor di regole di stato, mapping TRUE/FALSE/UNKNOWN tramite ExpressionEngine, RuleEngine e ActiveStateResolver.
- Execution reale: snapshot pubblicato, istanze, osservazioni storiche, valori correnti scelti per timestamp, correzione esplicita per rework.
- Analysis reale: BindingEngine, grafi potenziale/attivo/realizzato e AnalysisEngine; dipendenze, branching, candidati/overlap osservati, sequenza, attese, iteration/rework, UNKNOWN. Vista Scenario distinta da Storico.
- Motori M1–M5 mantenuti; business policy nel seed JSON e nel database.

## Demo

- Database dedicato con marcatore e seed idempotente; copia iniziale prepopolata inclusa.
- Engineering, Procurement, Supplier, Management, Logistics, Expediting; 16 attività, 9 informazioni, 7 mezzi, 2 gruppi e 17 Information Flow.
- Supplier A/B paralleli, Technical Alignment condizionale, ritorno alla specifica e revisione offerta; T/C, LT e criticità.
- MANAGEMENT_APPROVAL_THRESHOLD=500000, PO COST=620000; 10 regole configurate.
- DEMO PROJECT #001: 12 istanze, timestamp sintetici, osservazioni e una relazione runtime esplicita; evidenza di rework distinta dalla semplice ripetizione.
- Reset Demo sostituisce soltanto il database demo identificato. Test di conservazione byte per byte del database utente.

## Verifiche

**77/77 test passati, 0 errori, 0 test saltati.** Eseguiti test regressivi e di integrazione per workflow GUI/controller, seed, policy 500k → 750k, isolamento delle revisioni, flow, tipi, collapse, criticality, osservazioni e runtime analysis. Risultati definitivi e conteggi in `verification/verification.json` e `verification/tests.txt`.

Verificati syntax/import di tutti i moduli applicativi, `PRAGMA foreign_key_check` senza violazioni e `PRAGMA integrity_check = ok`.

PySide6 Essentials 6.11.2 disponibile: eseguiti widget test e rendering Qt **offscreen**, con font Windows caricati esplicitamente, e ispezionate le schermate di canvas, inspector, Rules, Execution, Analysis e form. Corretto durante la verifica il ciclo di vita delle etichette grafiche e il taglio orizzontale dei campi inspector.

Non è stata eseguita una sessione manuale su tutte le combinazioni Windows/DPI/monitor. Il launcher richiede Python e installa le dipendenze alla prima esecuzione; non è un file EXE autonomo. Le durate previste T/C e LT sono etichette di durata, mentre attese e sequenze osservate derivano dai timestamp.

L’editor Rules visuale copre regole di stato e prerequisiti; gli alberi di espressione M2 arbitrari preesistenti restano leggibili/valutabili. Il fit mantiene le proporzioni: su processi molto estesi è disponibile lo zoom.
