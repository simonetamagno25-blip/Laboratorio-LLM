# Handoff — ripresa dopo la lezione 6

Data: 2026-11-15 · Branch: `feat/lezione-6` (57 commit sopra `feat/note`), inviato su
`origin/feat/lezione-6` su richiesta dell'utente. `main` e `dev` non toccati; nessuna PR né merge.

Il dettaglio di cosa è stato fatto, con le verifiche e la revisione finale, è in
`handoff-2026-11-15-lezione-6.md`. Questo file serve a riprendere il lavoro.

## Stato
- Step 1–9 della lezione 6 completati e verificati (ROADMAP: tutto spuntato tranne lo streaming
  facoltativo).
- Test automatici: 503 passati, 37 saltati (`.\.venv\Scripts\python -m pytest -q`); nel container
  stesso esito.
- Albero di lavoro pulito; `LLM_Lez_6.pdf` resta fuori da Git di proposito.
- `.env` locale (non versionato) contiene `AMBITO_AGENTE` aggiornato e `POSTGRES_*` con una password
  generata: chi riparte da un clone deve copiare `.env.example` e scegliere le proprie credenziali.
- Alla chiusura della sessione lo stack Docker era attivo (`docker compose ps`: 4 servizi). Le chat
  di prova (id 1 vuota, id 2 «Ciao, mi chiamo Giulia…») stanno nel volume `dati_postgres`.

## Come riprendere
1. `git status` e `git log --oneline -5` sul branch `feat/lezione-6`.
2. LM Studio con `google/gemma-4-e2b` e server su `:1234`; caricare `.env` (comando nel CLAUDE.md).
3. Applicazione completa: `docker compose up -d --build`, poi `http://localhost:8080`.
   Oppure in locale: `python -m assistente.servizio`, `python -m assistente` (vedi README «Avvio»).

## Decisioni da rivedere con l'utente
Dallo step 2 in poi l'utente ha chiesto di procedere senza fermarsi: specifiche e piani sono stati
approvati da chi implementava. Le scelte sono nelle tabelle «Decisioni» di `specs/2026-11-14-*.md`;
le principali da confermare:
- resource e prompt nel server `convertitore_mcp` (nel PDF «orologio»);
- servizio scadenze dentro il container dell'agente, per avere quattro servizi in `compose.yaml`;
- front-end senza framework (HTML/JS, client generato dall'OpenAPI);
- la domanda non viene salvata se l'agente fallisce (il PDF descrive «salva, chiama, salva»).

## Da fare, in ordine suggerito
1. Prove manuali ancora aperte (README, «Checklist manuale»): voci 5–8 e 10 con la CLI client
   (errori, Ctrl+C, conferma interattiva) e voce 20 nel browser (eliminazione di una chat, Sì/No su
   una nota).
2. LM Studio spento con l'agente HTTP, dal vivo (oggi coperto solo dai test: 503 con messaggio).
3. Prova reale completa in un'unica esecuzione (`pytest --lmstudio -m lmstudio -v -s`, lunga).
4. Rilievi minori della revisione non corretti: turni sospesi senza scadenza nell'agente; strumenti
   usati riconosciuti per id della tool call; chat eliminata durante un turno → 500; invii
   concorrenti sulla stessa chat; `/stato` usa l'elenco degli strumenti MCP caricato all'avvio.
5. Difetto aperto da `feat/note`: «elenco delle note preso dalla cronologia».
6. Facoltativo: streaming della risposta (agente → back-end con SSE → front-end); va decisa e
   documentata la scelta con il revisore (bozza in diretta o solo risposta approvata).
7. PR o merge verso `dev` solo su richiesta dell'utente.

## Attenzioni per chi lavora sul codice
- Nei comandi `python - <<'EOF'` dentro Git Bash, `\n` nelle stringhe è diventato un a capo vero
  più volte: per il codice con sequenze di escape usare Write/Edit.
- Per i commit usare `git commit -- <percorsi>`: un `git rm` già in staging è finito per errore in un
  commit non correlato (corretto prima del push).
- Pytest raccoglie le funzioni importate il cui nome inizia con `test` (`testo_da_classificare`,
  `testo_da_riassumere`): nei test importare il modulo.
- Dopo una modifica alle rotte del back-end: `python -m frontend.genera_api`, altrimenti
  `tests/test_frontend.py` fallisce.
