# Step 9 · Docker Compose: un container per componente — specifica

Data: 2026-11-14 · Branch: `feat/agente-web` · Fonte: `LLM_Lez_6.pdf`, step 9.
Parte dagli step 6–8 funzionanti.

## Intento
Un solo comando avvia l'intera applicazione, pronta all'uso dal browser: front-end, back-end,
agente e database hanno ciascuno il proprio container; LM Studio resta sull'host.

## Obiettivi
- Quattro servizi in `compose.yaml`: tre con il proprio Dockerfile (`frontend/Dockerfile`,
  `backend/Dockerfile`, `Dockerfile` dell'agente) e PostgreSQL con l'immagine ufficiale.
- Il browser raggiunge il front-end; le chiamate `/api` arrivano al back-end tramite il proxy di
  nginx; agente, back-end e database non sono pubblicati.
- Volume per i dati di PostgreSQL; credenziali in `.env` escluso da Git; back-end avviato a database
  pronto.
- L'agente raggiunge LM Studio con `host.docker.internal`; il server MCP stdio parte nel suo container.

## Decisioni (prese da chi implementa, su indicazione dell'utente di procedere senza fermarsi)
| Tema | Decisione | Motivo |
|---|---|---|
| File | `compose.yaml` sostituisce `docker-compose.yml` | Nome indicato dal PDF |
| Servizio scadenze | gira nel container dell'agente (`SCADENZE_INTERNO=1`, thread nello stesso processo su una porta libera di 127.0.0.1) | È uno strumento dell'agente, come il server MCP stdio; così i servizi restano quattro |
| CLI | servizio `assistente` con profilo `cli`: non parte con `up`, si usa con `docker compose run --rm assistente` | La CLI resta disponibile senza essere un quinto container sempre attivo |
| Immagini | `postgres:17.6-alpine`, `nginx:1.29.1-alpine`, `python:3.12.15-slim` (versioni fissate) | Riproducibilità |
| Porta | front-end su `FRONTEND_PORTA_HOST` (default `8080`) | Unico punto d'ingresso dal browser |
| Database pronto | `healthcheck` con `pg_isready` e `depends_on: condition: service_healthy`; il back-end riprova comunque la connessione | Doppia garanzia all'avvio |
| Credenziali | `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` nel `.env`; `.env.example` con valori segnaposto | Nessuna credenziale in Git |

## Evidenze
- `docker compose up -d --build` avvia i quattro servizi; `docker compose ps` li mostra attivi.
- Chat dal browser con uno strumento, visibile nei log dell'agente (`docker compose logs agente`).
- Dopo `docker compose down` e `docker compose up -d` le chat sono ancora presenti.
- `docker compose ps` non mostra porte pubblicate per agente, back-end e database.
