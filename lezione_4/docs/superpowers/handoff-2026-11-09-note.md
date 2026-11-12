# Handoff — note persistenti

Data: 2026-11-09, aggiornato il 2026-11-13 · Branch: `feat/note` (da `dev`, solo locale, niente push) · `main` non toccato.

## Stato
Esercizio intermedio **Note persistenti** quasi concluso. Specifica
(`specs/2026-11-09-note-persistenti-design.md`) e piano (`plans/2026-11-09-note-persistenti.md`)
approvati e committati. Esecuzione «diretta» (senza sotto-agenti per passo), revisione finale fatta.

Commit sul branch, dopo il piano (`044e8f0`):
1. `9507e03` archivio SQLite (`assistente/note.py`, `assistente/testo.py` condiviso con il catalogo)
2. `109b69e` quattro tool e `PERCORSO_DB_NOTE`
3. `5cf8280` nodo `conferma_eliminazione` con `interrupt()` e `InMemorySaver`
4. `4ce864a` CLI: `Conferma> `, un `thread_id` nuovo per domanda
5. `8ef6814` avvio: archivio prima del server MCP, codice di uscita 5
6. `bd27de6` volume Docker `note` su `/app/note`
7. `aab57ea` prove reali LM Studio e prompt/descrizioni rinforzati
8. `db9e663` correzione dei due rilievi della revisione finale, con test:
   - C1: due `elimina_nota` con lo stesso id nello stesso messaggio → un «sì» eliminava due note.
     Ora la prima chiamata si riconosce per posizione, la conferma registra id **e** numero, e allo
     strumento arriva il numero già controllato.
   - I1: file dell'archivio in sola lettura non rilevato all'avvio → ora `PRAGMA user_version = 1`
     in `apri_archivio` fallisce e l'assistente esce con codice 5.
9. `4eda18e` README (note personali, variabili, grafo, diagnosi codice 5, sezione «Test» con le
   prove reali, voce 10 della checklist) e CLAUDE.md (volume e `docker compose down -v`).

## Verifiche eseguite
- Test automatici: `.\.venv\Scripts\python -m pytest -v` → **301 passati, 16 saltati** (prove LM
  Studio), anche dopo il commit delle correzioni (2026-11-13).
- Docker (prima delle correzioni della revisione): nota aggiunta da pipe e ritrovata in un secondo
  `docker compose run` separato (volume ok); eliminazione con conferma da pipe ok; dopo
  `docker compose down` il volume `lezione_4_note` resta.
- Docker (2026-11-13, dopo le correzioni): `docker compose build` ok; test nel container **301
  passati, 16 saltati**; avvio con `"/esci"` sul volume esistente ok (codice 0), volume presente
  dopo `docker compose down`.
- LM Studio (`google/gemma-4-e2b`), prompt finale, suite completa
  `.\.venv\Scripts\python -m pytest --lmstudio -m lmstudio -v -s`: **15/16** (23 minuti).
  Tutte e 6 le prove delle note passate; fallita `test_catalogo_ricerca_poi_dettaglio`, che
  ripetuta 3 volte passa 2/3. Le correzioni della revisione non cambiano prompt né descrizioni:
  le prove reali non sono state rieseguite dopo.

- Confronto `test_catalogo_ricerca_poi_dettaglio` (2026-11-13, `google/gemma-4-e2b`, script fuori
  dalla repository, varianti alternate): prompt e strumenti attuali **5/6**, senza paragrafo delle
  note e senza i quattro strumenti delle note **6/6**. Nei casi superati entrambe le varianti cercano
  con `categoria=sensori` e poi chiamano `dettaglio_articolo`; l'unico fallimento si ferma dopo la
  ricerca. Nessuna prova che le note abbiano peggiorato la prova: variabilità del modello.

## Da fare
1. Prova manuale (utente): sessione interattiva con conferma, in locale e in Docker con TTY,
   compreso Ctrl+C durante `Conferma> ` (voce 10 della checklist del README, poi aggiornarla).
2. PR `feat/note` → `dev` e merge, solo su richiesta.
3. Poi l'esercizio **Meteo da API pubblica** (server MCP su Open-Meteo).

## Rilievi minori non corretti (revisione finale)
- `numero` enorme (`10**20`) → `OverflowError` di SQLite: il turno fallisce, nulla eliminato.
- `InMemorySaver` conserva i thread di ogni domanda per tutta la sessione (memoria che cresce).
- `.dockerignore`: `*.sqlite3` vale solo alla radice del contesto; servirebbe `**/*.sqlite3`.
- `e_un_si` non normalizza l'Unicode: un «sì» scomposto vale come rifiuto (direzione sicura).

## Osservazioni sul modello
- Senza istruzioni esplicite rispondeva «Ho annotato» **senza** chiamare `aggiungi_nota`; ora il
  prompt elenca «annota», «prendi nota», «segna», «segnati», «ricordami». Con «Segnati che …» il
  modello a volte scrive la chiamata come testo invece di eseguirla.
- Per eliminare chiedeva lui «Vuoi eliminare?» prima di chiamare `elimina_nota` (conferma doppia;
  con input da pipe la riga successiva veniva letta come risposta alla conferma → annullata, in
  modo sicuro). Ora il prompt dice di chiamare subito `elimina_nota` e di non chiedere conferma.
- Le prove reali complete richiedono 23–29 minuti: avvisare prima di rilanciarle.

## Note
- Scelte prese durante l'esecuzione (dettagli nel ledger di lavoro, non versionato):
  numero di nota non valido mai passato allo strumento (Pydantic convertirebbe `True` in 1);
  grafo con checkpointer solo quando c'è l'archivio; `costruisci_grafo` rifiuta `elimina_nota`
  senza archivio.
- `gh` non è installato: PR e merge con l'API di GitHub e le credenziali salvate da Git.
- Docker Desktop va avviato prima delle prove Docker.
