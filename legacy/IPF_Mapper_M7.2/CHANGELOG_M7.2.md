# M7.2 — Correzione UI sul riferimento approvato

Baseline unica: IPF_Mapper_M7.1.zip. La prima anteprima M7.2 è stata respinta: questa build sostituisce quell’interfaccia.

- Sidebar da 142 px a tutta altezza, icone vettoriali e selezione Canvas evidenziata.
- Breadcrumb, toolbar su una riga, controlli zoom raggruppati e ricerca canvas.
- Proporzioni di corsie, card e pannelli ricostruite sul riferimento 1768 × 832 (area applicazione, escluse le annotazioni rosse).
- Libreria mezzi compatta: sette tessere nella prima riga, quattro nella seconda, icona sopra label piccola, bordi sottili e nessuna cornice aggiuntiva attorno al glifo.
- Inspector a destra a tutta altezza: campi su righe compatte, tab Generale/Avanzate/Note funzionanti, collegamenti ricavati dai dati.
- Minimap navigabile, legenda disegnata con simboli reali e statistiche su due colonne.
- Lane Supplier A/B parallele, card Action azzurre con performer e T/C; Information lilla/document-shaped; badge rossi con !; riquadro tratteggiato per la vista parallela.
- Posizioni del demo e badge dei mezzi definite in reference_layout.json, esclusivamente nella presentation. Le posizioni iniziali del database non vengono riscritte; dopo un trascinamento prevale la posizione salvata dall’utente.
- Il rombo Offerta ok? è un’annotazione della vista del riferimento, con tooltip esplicito: non crea decisioni, regole o flussi nel dominio.

## Verifiche reali
80 test passati, nessun skip/fallimento/errore; comprendono tutta la suite esistente (77 test) e 3 test mirati M7.2. Import di tutti i moduli applicativi e compilazione Python OK. Foreign key check vuoto; SQLite integrity_check = ok. Snapshot e policy 500000/750000 verificati dal controllo di release.

I test mirati controllano zoom/ricerca/minimappa, visibilità e dimensioni dei campi inspector, griglia dei mezzi, invarianza delle posizioni del modello quando si applica la proiezione visiva e persistenza dei trascinamenti. Gli screenshot Qt offscreen delle otto viste/dialoghi sono stati realmente generati. Canvas e inspector sono stati ispezionati visivamente. Prove e log in verification_reference/.

Tutti i file di dominio, database, repository, services, engines, app/controller e risorse sono invariati byte per byte rispetto alla baseline. Vedi BUILD_PROVENANCE_M7.2.json.

## Limiti di verifica e contenuto
Nessuna approvazione visiva dell’utente è implicata dal nome dello ZIP. Rendering verificato offscreen su Windows; nessuna prova manuale sul PC aziendale o su altri DPI. Reset Demo mantiene il codice originale e la separazione tra database; il dialogo di conferma non è stato cliccato manualmente.

L’immagine contiene informazioni e conteggi diversi dalla baseline: questa build conserva 16 Action, 9 Information, 6 funzioni, 7 mezzi e 17 flow. Non falsifica durata, performer, criticità, revisione o collegamenti per sostituirli con quelli illustrativi del mockup. Revisiona offerta e Specifica revisionata restano visibili perché appartengono alla baseline; Piano consegna e Report expediting restano Information. Restano quindi differenze nei contenuti del diagramma, nei percorsi effettivi e nei valori dell’inspector. Non è dichiarata una verifica pixel per pixel.

## Avvio
Installare requirements.txt e avviare main.py o run_windows.bat. Nessuna nuova dipendenza. Per ripetere le verifiche: python verify_release.py --out verification_reference.
