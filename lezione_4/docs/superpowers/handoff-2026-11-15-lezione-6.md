# Handoff — lezione 6, step 1–9

Data: 2026-11-15 · Branch: `feat/lezione-6`, solo locale, niente push · `main` e `dev` non toccati.

## Modo di lavoro
Dopo lo step 1 l'utente ha chiesto di «continuare step a step senza fermarsi». Per gli step 2–9
specifiche e piani sono stati scritti e approvati da chi implementava, scegliendo le opzioni
consigliate. Le decisioni sono nelle tabelle «Decisioni» di ogni specifica in `specs/`. Vanno
rilette dall'utente.

## Cosa c'è
| Step | Specifica | Evidenza minima | Verifica |
|---|---|---|---|
| 1 Router | `specs/2026-11-14-router-design.md` | fuori ambito senza agente | prove reali 5/5, log |
| 2 Revisore | `specs/2026-11-14-revisore-design.md` | risposta parziale corretta entro il limite | prove reali 2/2 |
| 3 Riassunto | `specs/2026-11-14-riassunto-design.md` | nome usato dopo la compressione | prova reale, log prima/dopo |
| 4 Resource | `specs/2026-11-14-preferenze-design.md` | preferenze dal file, senza toccare il codice | prove reali (New York, inglese) |
| 5 Prompt | `specs/2026-11-14-prompt-design.md` | /prompts e /prompt con argomenti validati | prove reali, CLI client |
| 6 Agente HTTP | `specs/2026-11-14-servizio-agente-design.md` | stessa risposta da CLI e API | «17 * 23» → 391 da entrambe |
| 7 Back-end | `specs/2026-11-14-backend-design.md` | chat persistenti, OpenAPI | test PostgreSQL 16/16, down/up in Docker |
| 8 Front-end | `specs/2026-11-14-frontend-design.md` | conversazione dal browser, errori | browser: strumento, agente spento |
| 9 Compose | `specs/2026-11-14-compose-design.md` | 4 container, agente non esposto | `docker compose ps`, browser |

Test automatici: 503 passati, 37 saltati (prove LM Studio e PostgreSQL, attivate con `--lmstudio` e
`--postgres`); archivio su PostgreSQL vero: 18 passati.

## Revisione finale (step 2–9, da `c2736a4` a `fe0e7c8`)
Esito «pronto con correzioni». Corretti:
- C1: conferma scaduta (agente riavviato o ripresa fallita) bloccava la chat per sempre → il back-end
  la libera con un 409 leggibile;
- I1: riassunto vuoto cancellava i turni vecchi → nessuna compressione, `WARNING`;
- I2: l'indicazione del revisore poteva far ripetere azioni con effetti → «completa solo le parti
  mancanti, non ripetere azioni già eseguite»;
- I3: la conferma dopo un ricaricamento non diceva quale nota → domanda salvata e mostrata;
- minori: timeout dell'agente come 504 (non «non raggiungibile»), margine di nginx, checkpoint dei
  turni eliminati, variabili PostgreSQL obbligatorie in Compose, documentazione allineata.
Non corretti (minori, annotati): turni sospesi senza scadenza nell'agente; strumenti usati
riconosciuti per id della tool call; chat eliminata durante un turno → 500; invii concorrenti sulla
stessa chat; `/stato` usa l'elenco degli strumenti MCP caricato all'avvio.

## Dipendenze nuove (versioni fissate)
`fastapi==0.163.0`, `uvicorn==0.54.0` (già presente con `mcp`), `psycopg[binary]==3.3.9`.
Immagini: `postgres:17.6-alpine`, `nginx:1.29.1-alpine`. Node.js è facoltativo, solo per i test JS.

## Correzioni nate dalle prove reali
- Fail-open di router e revisore anche per JSON fuori schema, troncato o con `finish_reason=length`.
- Router: i seguiti di domande fuori ambito restano fuori ambito; le domande sull'utente o sulla
  conversazione («come mi chiamo?», «riassumi…») restano in ambito.
- L'indicazione del revisore ricorda all'agente di usare gli strumenti.
- Timeout del modello portato a 300 s; il timeout non viene più descritto come «non raggiungibile».
- Front-end: i titoli lunghi non allargano la barra laterale.

## Deviazioni dal PDF, motivate nelle specifiche
- Resource e prompt stanno nel server MCP esistente `convertitore_mcp` (nel PDF si chiama «orologio»).
- In `compose.yaml` il servizio scadenze gira nel container dell'agente (`SCADENZE_INTERNO=1`), così
  i servizi restano quattro.
- La conferma delle eliminazioni è l'unico stato tenuto dall'agente (turno sospeso fino alla risposta).

## Da verificare / aperto
- Voci 5–8 e 10 della checklist del README (errori, Ctrl+C, conferma interattiva) con la CLI client.
- Eliminazione di una chat e conferma Sì/No di una nota dal browser (coperte solo dai test).
- Prova reale completa in una sola esecuzione (23–29 minuti o più, ora con router e revisore).
- LM Studio spento con l'agente HTTP: coperto dai test (503 con messaggio), non provato dal vivo.
- Ordine TDD invertito per il back-end (codice prima dei test); compensato con prove di mutazione
  sull'API.
- Resta aperto da `feat/note` il difetto «elenco delle note preso dalla cronologia».
- Facoltativo: streaming della risposta (non fatto).
