# Step 7 · Back-end: API e salvataggio delle chat — specifica

Data: 2026-11-14 · Branch: `feat/lezione-6` · Fonte: `LLM_Lez_6.pdf`, step 7.
Parte dallo step 6 (agente come servizio HTTP) funzionante.

## Intento
Il back-end è l'unico punto di contatto del front-end: gestisce le chat, le salva in PostgreSQL e
inoltra le domande all'agente. Le conversazioni restano disponibili dopo il riavvio e il front-end
non conosce l'agente.

## Operazioni
| Operazione | Endpoint | Comportamento |
|---|---|---|
| Creare una chat | `POST /api/chat` | `201`, restituisce l'identificativo (titolo iniziale «Nuova chat») |
| Elencare le chat | `GET /api/chat` | titolo e data dell'ultimo messaggio, la più recente prima |
| Leggere una chat | `GET /api/chat/{id}` | messaggi in ordine cronologico, con gli strumenti usati |
| Inviare un messaggio | `POST /api/chat/{id}/messaggi` | chiama l'agente con cronologia e riassunto della chat, salva domanda e risposta e restituisce la risposta |
| Confermare un'eliminazione | `POST /api/chat/{id}/conferma` | risposta sì/no alla conferma chiesta dall'agente |
| Eliminare una chat | `DELETE /api/chat/{id}` | `204`, rimuove la chat e i suoi messaggi |
| Stato | `GET /api/stato` | back-end, database e agente raggiungibili |

## Decisioni (prese da chi implementa, su indicazione dell'utente di procedere senza fermarsi)
| Tema | Decisione | Motivo |
|---|---|---|
| Framework | FastAPI (già adottato allo step 6), pacchetto `backend/` separato dall'agente | OpenAPI generato (`/api/docs`, `/api/openapi.json`); un container per componente allo step 9 |
| Database | PostgreSQL con `psycopg[binary]==3.3.9` (dipendenza nuova), una connessione per operazione | Richiesto dal PDF; driver sincrono e senza ORM, coerente con il codice del progetto |
| Schema | tabelle `chat` (titolo, date, cronologia dell'agente in `jsonb`, riassunto, conferma in attesa) e `messaggio` (`ON DELETE CASCADE`), create all'avvio con `CREATE TABLE IF NOT EXISTS` | Nessuna migrazione da gestire in un progetto didattico |
| Cronologia dell'agente | il back-end conserva per ogni chat la cronologia e il riassunto restituiti dall'agente e li rimanda al turno dopo | L'agente è senza stato (step 6) |
| Titolo | le prime parole della prima domanda (al massimo 60 caratteri) | Elenco leggibile senza chiedere un titolo all'utente |
| Agente non raggiungibile | `503` con «Agente non raggiungibile su <url>: la domanda non è stata salvata, riprova»; nessun messaggio salvato | Niente domande orfane nella chat; il front-end tiene il testo per riprovare |
| Errore dell'agente (es. LM Studio spento) | `502` con il messaggio dell'agente; nessun messaggio salvato | Stesso comportamento, causa diversa e leggibile |
| Ordine di salvataggio | domanda e risposta nella stessa transazione, dopo la risposta dell'agente | Nessuna transazione aperta durante la chiamata (anche minuti) al modello locale |
| Avvio a database pronto | il back-end riprova la connessione fino a `ATTESA_DATABASE` secondi (default 30) prima di creare lo schema | Richiesto dallo step 9; utile anche in locale |
| Test | archivio in memoria con la stessa interfaccia per i test dell'API; test dell'archivio PostgreSQL attivati con `--postgres` e `POSTGRES_TEST_URL` | Test ripetibili senza database; prova reale separata, come per LM Studio |
| CORS | origini consentite da `ORIGINI_CONSENTITE` (default `http://localhost:8300`) | Il front-end in locale gira su un'altra porta |

## Configurazione (`backend/config.py`)
`DATABASE_URL` (obbligatoria), `AGENTE_URL` (default `http://localhost:8100`), `BACKEND_HOST`
(default `127.0.0.1`), `BACKEND_PORTA` (default `8200`), `ORIGINI_CONSENTITE`, `ATTESA_DATABASE`.

## Evidenze
- Test automatici con l'agente simulato (`httpx.MockTransport`) e l'archivio in memoria: tutte le
  operazioni, conferma, agente non raggiungibile (503, niente salvato), errore dell'agente (502),
  chat inesistente (404), OpenAPI disponibile.
- Test dell'archivio PostgreSQL (`--postgres`): stesse prove dell'archivio in memoria, più chat
  ancora presenti con una nuova connessione/istanza (riavvio).
- Prova reale: back-end + agente + LM Studio + PostgreSQL in Docker; una chat con uno strumento,
  riavvio del back-end, chat ancora presente.
