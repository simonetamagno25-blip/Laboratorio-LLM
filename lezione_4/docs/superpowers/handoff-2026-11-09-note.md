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
10. `4c71b04` (2026-11-13, dopo la prova manuale) CLI: prima di `Conferma>` si scarta il testo
    scritto in anticipo (solo se l'input è un terminale: `termios.tcflush` su POSIX,
    `FlushConsoleInputBuffer` su Windows; con il pipe nulla); dopo ogni domanda e dopo la conferma
    compare `(attendi: il modello sta rispondendo...)`. Test: ordine scarta → `Conferma>`, avviso
    nell'output, pipe non toccato, terminale POSIX vero con `os.openpty` (saltato su Windows).
11. `fd80de0` README: avviso di attesa, conferma senza testo anticipato, orari UTC nei log del
    container.

## Verifiche eseguite
- Test automatici: `.\.venv\Scripts\python -m pytest -v` → **301 passati, 16 saltati** (prove LM
  Studio), anche dopo il commit delle correzioni (2026-11-13). Dopo `4c71b04`: **305 passati, 17
  saltati** in locale (in più il test POSIX), **306 passati, 16 saltati** nel container; avvio con
  input da pipe ok in Docker e in locale (l'avviso compare). Prove reali LM Studio non rieseguite
  (prompt invariato).
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

## Prova manuale del 2026-11-13

**Docker con TTY** (prima di `4c71b04`): aggiunta ok, elenco ok, conferma con `no` ok, Ctrl+C
durante `Conferma>` ok (`Arrivederci.`, nota rimasta), nota ritrovata in un secondo
`docker compose run` (volume ok). Conferma con `sì` **non provata**: il modello impiega 20–40 s,
l'utente ha riscritto «Elimina la nota sul saldatore» perché non vedeva nulla, e quella riga,
rimasta nel terminale, è diventata la risposta a `Conferma>` → eliminazione annullata (esito sicuro,
ma con un `si` scritto in anticipo avrebbe eliminato). Corretto con `4c71b04`.

**Locale** (dopo `4c71b04`, PowerShell): conferma con `si` ok, nota 1 eliminata (log
`eliminazione della nota 1 confermata`, archivio `note.sqlite3` verificato vuoto). Poi **difetto
aperto**:

```text
Tu> che note ho
(attendi: il modello sta rispondendo...)
Assistente> Note salvate: 1
Nota 1 (2026-11-13 16:32): il saldatore va pulito
```

Nessuna riga `chiamata strumento` nel log: il modello **non ha chiamato `elenca_note`** e ha
ricopiato il risultato di uno strumento rimasto nella cronologia, mostrando una nota già eliminata.

Dopo `4c71b04` restano da provare: la prova del testo anticipato (scrivere `si` senza Invio
durante «attendi...», a `Conferma>` deve essere sparito e l'Invio deve annullare), in locale e in
Docker con TTY; l'intero giro in Docker con TTY.

## Da fare
1. **Difetto aperto — risposta sulle note presa dalla cronologia invece che dall'archivio.**
   Partire con `superpowers:systematic-debugging`:
   - riprodurlo con la prova reale (aggiungi → elenca → elimina con sì → elenca: il secondo
     elenco deve chiamare `elenca_note` e non mostrare la nota) e capire quanto è frequente;
   - ipotesi: il prompt (`assistente/grafo.py`, righe 43–67) impone lo strumento per
     aggiungere ma non per elencare/cercare («usa cerca_note … o elenca_note» non dice «sempre» né
     «non rispondere dalla cronologia»); nella cronologia restano i `ToolMessage` con l'elenco
     vecchio, che il modello ricopia;
   - correzioni possibili da valutare con l'utente: regola esplicita nel prompt («per qualsiasi
     domanda sulle note chiama sempre elenca_note o cerca_note: la cronologia può essere
     superata») più una prova reale nuova per questo caso; non cambiare la cronologia senza
     discuterne.
2. Ripetere la prova manuale (vedi sopra), poi aggiornare la voce 10 della checklist del README.
3. PR `feat/note` → `dev` e merge, solo su richiesta.
4. Poi l'esercizio **Meteo da API pubblica** (server MCP su Open-Meteo).

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
