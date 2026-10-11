# Conservazione dei dati

Fonte originale: `legacy/IPF_Mapper_M7.2/resources/demo_m71.db`, 577536 byte. SHA-256 verificato prima e dopo l'implementazione:

`ebc1fa9d166d13b2c3b8d3ee2dbc53e94229eabb60f5ead25a1e06b8b36b96a7`

Encoding del database originale: UTF-8. `PRAGMA integrity_check`: `ok`; `PRAGMA foreign_key_check`: nessuna riga. Revisione DRAFT 1 e snapshot PUBLISHED 2 dello stesso processo. Il documento di revisione 1 contiene 57 entità, 97 relazioni e 10 regole. Le soglie procurement sono nei dati, non nei motori.

## Strategia
1. Preservare i byte del pacchetto originale. Creare solo una copia demo di lavoro se assente; non reseedare copie esistenti.
2. Per un file fornito attraverso `IPF_DB_PATH`, verificare esistenza, schema minimo, integrità e FK. Nessun database vuoto sostitutivo.
3. Completare il backup tramite l'API SQLite `backup` prima delle migrazioni. Non copiare solamente il file principale di un database WAL attivo.
4. Migrazioni transazionali additive e idempotenti. Non alterare tabelle legacy, definizioni delle colonne, vincoli o record esistenti. La classificazione assente si interpreta come UNCLASSIFIED, senza retroaggiornare tutti i record.
5. Validare documenti esterni tramite Zod e grammatica del catalogo. Salvare in transazione con rollback e versionamento ottimistico. Definizioni condivise ricevono copia prima di modifiche; record storici e proprietà di relazioni non modificate rimangono intatti.
6. Non eliminare entity_identity/entity_definition/relation_definition durante delete: cambia solo la membership della revisione. Questo permette undo dopo il salvataggio e conserva lo storico.

## Evidenze automatiche
I test confrontano l'intero documento dello snapshot pubblicato, i dati di esecuzione con osservazioni/correzioni, nodi di espressioni e definizioni delle regole prima e dopo modifiche a nomi, classificazioni e layout. Verificano rollback a metà salvataggio, clone indipendente, restore di membership, rifiuto di conflitti e rifiuto di percorsi mancanti. Nessuna assertion viene disabilitata per far passare i controlli.

UTF-8 viene verificato in JSON, SQLite e browser con `È`, `—`, apostrofo tipografico, virgolette e testo giapponese. I dati non sono riparati con sostituzioni arbitrarie. Eventuali valori già corrotti in un database personale devono essere identificati e corretti con una migrazione documentata separata, conservando il valore originale; non sono presenti nella fixture analizzata.

## Limiti
Il database personale non è allegato, quindi non è stato possibile validarne i record reali. Non è stata testata l'apertura della copia migrata nella GUI desktop PySide, assente nell'ambiente; lo schema legacy rimane invariato e le suite di dominio Python passano. DECISION è un nuovo sottotipo: la GUI Python potrebbe mostrarlo come tipo generico. La concorrenza ottimistica copre i client web; il client Python non aggiorna il contatore web. Un deployment condiviso e una migrazione di database anteriori a M7.2 richiedono lavoro dedicato.
