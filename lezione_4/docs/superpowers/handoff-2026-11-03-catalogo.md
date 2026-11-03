# Handoff — catalogo locale

Data: 2026-11-03 · Branch attuale: `feat/note` (da `dev`, solo locale, ancora vuoto) · `main` non toccato.

## Stato
- PR #1 `feat/strumenti-mcp` → `dev` aperta e unita (commit `351a73d`).
- Esercizio intermedio **Catalogo locale** completato: PR #2 `feat/catalogo` → `dev` unita
  (commit `b67e44d`). Dettagli in `specs/2026-11-03-catalogo-locale-design.md`,
  `plans/2026-11-03-catalogo-locale.md` e README (sezione «Catalogo del laboratorio»).
  - Tool locali `cerca_articoli` e `dettaglio_articolo` su `assistente/dati/catalogo.json`
    (20 articoli, 6 categorie), validato all'avvio; file non valido → «Catalogo non valido», codice 4.
  - Test automatici: 234 passati, 10 saltati (prove LM Studio).
  - LM Studio (`google/gemma-4-e2b`): 10/10 prove reali; risposte del catalogo lette a occhio.
  - Docker Compose: build, test nel container, domanda sul catalogo da pipe.
  - Revisione finale fatta; corretto il caso del file non UTF-8.

## Da fare
1. Esercizio intermedio **Note persistenti** (aggiunta, elenco, eliminazione su SQLite; tool con
   effetti e conferme). Si riparte dal brainstorming, poi specifica e piano da approvare.
   Accordi già presi:
   - meccanismo: tool locale con `sqlite3` della libreria standard (nessuna dipendenza nuova);
   - la conferma prima dell'eliminazione va nel grafo LangGraph, non nello strumento;
   - in Docker serve un volume per il file del database;
   - la specifica deve chiarire che «nessuna persistenza» del CLAUDE.md riguarda la cronologia,
     non le note.
2. Poi l'esercizio avanzato **Meteo da API pubblica**: server MCP che chiama un servizio HTTP
   esterno (proposta: Open-Meteo, senza chiave); timeout, errori di rete, dati esterni.
3. Prova manuale non ancora fatta: sessione interattiva con le domande del catalogo, in locale e in
   Docker con TTY.

## Rilievi minori non corretti (catalogo)
- Parole brevi nelle ricerche a più parole («sensore dell'umidità») danno un falso «nessun articolo».
- `\d` nel formato del codice accetta cifre non ASCII.
- Con sola categoria e nessun risultato il messaggio mostrerebbe `per ""` (oggi impossibile con i dati).
- Il dettaglio non riconosce il trattino tipografico (`SEN–004`).
- Chiavi duplicate nello stesso oggetto JSON non rilevate.
- Restano aperti anche i rilievi minori dell'handoff del 2026-11-02 (MCP, API, calcolatrice).

## Osservazioni sul modello
- Senza un «usa sempre … prima di rispondere» non chiama `cerca_articoli` per domande come
  «Avete stampanti 3D?» o «Dov'è il sensore di umidità?».
- Ogni frase nuova nel prompt può peggiorare altri strumenti: con la frase del catalogo rifiutava
  «5 kg in metri» senza chiamare `converti_unita`. Dopo ogni modifica del prompt rieseguire tutte
  le prove reali.
- Le prove reali sono lente (circa 7 minuti per tutte e 10).

## Note
- `gh` non è installato: PR e merge si fanno con l'API di GitHub usando le credenziali salvate da Git.
- Docker Desktop va avviato prima delle prove Docker.
- Flusso Git concordato: un branch `feat/<nome>` da `dev` per ogni esercizio; dopo ogni commit
  si avvisa e si fa il push solo su conferma.
