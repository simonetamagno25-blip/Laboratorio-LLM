# Assistente del laboratorio

Progetto del corso «Deep Learning e LLM: costruire chatbot e agenti».
La cartella del progetto è `lezione_4/`. Struttura, dipendenze e comandi sono nel `README.md`.

## Obiettivo
Un'applicazione da terminale in Python che conversa con un modello locale e:
- organizza il flusso in un grafo LangGraph esplicito (stato, nodi, instradamento riconoscibili);
- usa un modello servito da LM Studio, che resta sul computer host;
- conserva la cronologia della conversazione per la durata della sessione (nessuna persistenza);
- offre uno strumento orologio con fuso orario esplicito, richiesto dal modello tramite tool calling
  ed eseguito davvero dal programma;
- si avvia anche con Docker Compose;
- (lezione 7) recupera i passaggi pertinenti a una domanda da un corpus di documenti, con la loro
  fonte, tramite un indice vettoriale ripetibile (RAG: ingestion e ricerca).

## Confini
- Implementare solo i requisiti concordati. Altri strumenti e workflow arriveranno
  nelle lezioni successive: non anticiparli.
- RAG per gradi: nella lezione 7 solo ingestion, ricerca e valutazione del retrieval, senza
  modello generativo. La ricerca diventa uno strumento dell'agente solo nella lezione 8.
- Niente interfacce grafiche, servizi cloud o framework non concordati.
- Lavorare solo dentro `lezione_4/`. La repository contiene altre lezioni:
  non leggerle per copiarne il codice e non modificarle.
- Lavorare nel branch corrente; nessun branch o worktree nuovo se non richiesto.

## Scelte tecniche
- Python, codice sincrono e moduli piccoli, con una separazione semplice tra
  grafo, collegamento al modello, strumenti e interfaccia da terminale.
- LM Studio sull'host, raggiunto tramite la sua API compatibile con OpenAI.
- Indirizzo del server e identificativo del modello solo da variabili d'ambiente.
  L'identificativo è quello restituito dal server (`GET /v1/models`), mai inventato.
- Un file di configurazione di esempio senza credenziali; il file reale resta fuori da Git.
- Docker Compose per l'applicazione; LM Studio non va containerizzato.
- Dipendenze motivate, concordate e con versioni fissate.
- Comandi documentati anche per PowerShell (Windows).

## RAG (lezione 7)
- L'ingestion è uno script separato, eseguito quando il corpus cambia; non è uno strumento
  dell'agente. L'agente (dalla lezione 8) userà soltanto la ricerca.
- Modello di embedding di LM Studio letto dalla configurazione, lo stesso per documenti e domande;
  la collezione registra il modello usato e un modello diverso viene bloccato (si reindicizza).
- Qdrant come servizio di Docker Compose, con volume persistente; mai containerizzare LM Studio.
- Ingestion ripetibile: ID dei punti stabili (derivati da fonte e posizione del chunk) e upsert;
  dopo due esecuzioni il numero di punti è lo stesso.
- Ogni chunk porta nel payload testo e metadati sufficienti a citarne la fonte (documento,
  capitolo, posizione).
- Corpus scaricato in `dati/`, fuori da Git, come le slide delle lezioni.
- Test senza servizi: embedder finto e Qdrant in memoria. Ingestion reale, ricerca su LM Studio
  e valutazione con domande a fonte attesa sono prove separate, attivate esplicitamente.
- Il retrieval si valuta su domande con fonte attesa (posizione e score della fonte); «funziona»
  non è un'evidenza. Un parametro per volta, stesse domande prima e dopo.

## Metodo: Superpowers
- Usare le skill di Superpowers per brainstorming, specifica, piano, implementazione e verifica.
- Non scrivere codice prima che io abbia approvato la specifica e poi il piano.
- Salvare specifica e piano in `lezione_4/docs/superpowers/`.
- Procedere per incrementi piccoli, ciascuno verificato prima del commit.

## Test e verifiche
- Test automatici ripetibili che non richiedono un modello attivo (grafo, cronologia,
  instradamento, strumento con istante controllato).
- Prove reali con LM Studio e con Docker tenute separate e attivate esplicitamente.
- Una risposta simulata non dimostra che il modello locale sappia usare lo strumento.
- Nel resoconto indicare che cosa è stato eseguito, con quale esito, e che cosa resta da provare.

## Git
- Conventional Commits in italiano, per esempio `feat(grafo): ...`, `test(strumenti): ...`,
  `docs: ...`.
- Prima di ogni commit: `git status`, controllo del diff, staging selettivo dei soli file pertinenti.
- Mai versionare credenziali, `.env`, ambienti virtuali, cache o pesi dei modelli.
- Push soltanto su mia richiesta.

## Documentazione
- Tenere aggiornato il README con configurazione, avvio, test e diagnosi, riportando solo
  comandi verificati.
- Aggiornare questo file quando cambiano convenzioni stabili (struttura, comandi di test,
  regole di lavoro), non per annotare l'avanzamento.

## Struttura (agente, back-end e front-end)
- `assistente/`: grafo (riassunto → router → agente ⇄ strumenti → revisore), agente HTTP
  (`assistente/servizio.py`, FastAPI) e CLI client (`python -m assistente`);
- `convertitore_mcp/`: server MCP (tool `converti_unita`, resource `utente://preferenze`, prompt
  `spiega` e `riassumi_conversazione`); `scadenze_api/`: servizio HTTP di giorni e scadenze;
- `backend/`: API delle chat per il front-end, PostgreSQL; `frontend/`: interfaccia di chat
  (HTML/JS, `api.js` generato da `frontend/openapi.json`);
- `compose.yaml`: front-end, back-end, agente, database (CLI con il profilo `cli`);
- `rag/` (lezione 7): ingestion, ricerca e valutazione del retrieval, separati dall'agente;
  `dati/`: corpus scaricato, non versionato.

## Comandi
Da PowerShell, dalla cartella `lezione_4/` (comandi verificati; dettagli nel `README.md`):
- ambiente: `py -m venv .venv` poi `.\.venv\Scripts\python -m pip install -r requirements-dev.txt`;
- caricare `.env` nella sessione:
  `Get-Content .env | Where-Object { $_ -match '^\s*[^#\s][^=]*=' } | ForEach-Object { $k, $v = $_ -split '=', 2; Set-Item "env:$($k.Trim())" $v.Trim() }`;
- in locale, ognuno in una finestra: `.\.venv\Scripts\python -m scadenze_api`,
  `.\.venv\Scripts\python -m assistente.servizio` (agente, porta 8100), poi la CLI
  `.\.venv\Scripts\python -m assistente`; back-end `.\.venv\Scripts\python -m backend` (serve
  `DATABASE_URL`) e front-end `.\.venv\Scripts\python -m frontend` (porta 8300);
- applicazione completa in Docker: `docker compose up -d --build`, browser su `http://localhost:8080`,
  `docker compose ps`, `docker compose logs agente`; alla fine `docker compose down` (chat e note
  restano nei volumi; `docker compose down -v` le cancella);
- CLI in Docker con input da pipe: `"Quanto fa 2 + 2?", "/esci" | docker compose run --rm -T assistente`;
- test automatici: `.\.venv\Scripts\python -m pytest -v`; test nel container:
  `docker compose run --rm assistente python -m pytest -v`;
- client del front-end dopo una modifica al back-end: `.\.venv\Scripts\python -m frontend.genera_api`;
- archivio PostgreSQL reale: `POSTGRES_TEST_URL` impostata e
  `.\.venv\Scripts\python -m pytest tests/test_backend_archivio.py --postgres -v`;
- prova reale con LM Studio: `.\.venv\Scripts\python -m pytest --lmstudio -m lmstudio -v -s`
  (a gruppi con `-k router`, `-k revisore`, `-k "riassunto or preferenze or prompt_"`).
