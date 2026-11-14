# Step 6 · L'agente come servizio HTTP — specifica

Data: 2026-11-14 · Branch: `feat/lezione-6` · Fonte: `LLM_Lez_6.pdf`, step 6.
Parte dagli step 1–5 funzionanti.

## Intento
Finora l'agente era un'applicazione da terminale. Per servire un'interfaccia web deve esporre
un'API: riceve la conversazione e restituisce la risposta. Lo stesso grafo risponde sia alla CLI sia
alle chiamate HTTP, senza duplicare la logica: la CLI diventa un client dell'API.

## Obiettivi
- Modulo dell'agente separato dall'interfaccia; la CLI diventa client dell'API.
- Endpoint che riceve messaggio e cronologia e restituisce risposta e strumenti usati.
- Endpoint di stato: agente, server MCP e modello raggiungibili.
- Agente senza stato: cronologia e riassunto arrivano dal chiamante e tornano aggiornati.

## Decisioni (prese da chi implementa, su indicazione dell'utente di procedere senza fermarsi)
| Tema | Decisione | Motivo |
|---|---|---|
| Framework | FastAPI `0.163.0` (dipendenza nuova, versione fissata) servito da uvicorn `0.54.0` (già installato con `mcp`, ora fissato) | Il PDF chiede la documentazione OpenAPI: FastAPI la genera da sola (`/docs`, `/openapi.json`); è compatibile con Starlette 1.10 già presente |
| Codice sincrono | endpoint `def` (FastAPI li esegue in un thread pool) | Il grafo e il client MCP restano sincroni come nel resto del progetto |
| Avvio | `python -m assistente.servizio` avvia l'agente HTTP (porta `AGENTE_PORTA`, default `8100`; host `AGENTE_HOST`, default `127.0.0.1`); `python -m assistente` è la CLI che chiama `AGENTE_URL` (default `http://localhost:8100`) | Due processi distinti come chiede il PDF |
| Cronologia sulla rete | messaggi LangChain serializzati con `messages_to_dict` / `messages_from_dict` | Conserva tool call, `ToolMessage`, nomi e indicazioni del revisore senza inventare un formato |
| Conferma delle note | unica eccezione all'assenza di stato: la conferma in sospeso resta nell'agente (checkpointer in memoria) fino alla risposta; l'API restituisce `tipo="conferma"` con `id_conferma`, e `POST /conferma` riprende il turno | Il grafo si ferma con `interrupt()`; serializzare il checkpoint verso il client complicherebbe molto l'API per un caso raro |
| Prompt MCP | `GET /prompts` e `POST /prompts/{nome}` espongono `prompts/list` e `prompts/get`; il controllo degli argomenti resta nella CLI | Il client MCP vive nell'agente; la CLI li richiama come prima |
| Errori | modello non raggiungibile → `503` con il messaggio di `descrivi_errore`; errore del modello → `502`; richiesta non valida → `422` (FastAPI); conferma sconosciuta → `404` | Codici HTTP comprensibili, messaggio in italiano nel campo `detail` |
| Stato | `GET /stato`: `agente` sempre `ok`, `server_mcp` `ok`/`non disponibile` (lista degli strumenti), `modello` `ok`/`non raggiungibile` (`GET /models` di LM Studio, timeout breve); `200` se tutto ok, `503` altrimenti | Una chiamata sola per la diagnosi |

## Progetto

### `assistente/agente.py` (modulo nuovo)
- `Agente(grafo, recursion_limit)`: `turno(nuovi, cronologia, riassunto) -> Esito` e
  `conferma(id_conferma, si) -> Esito`. `Esito` è una risposta (testo, strumenti usati, cronologia,
  riassunto) oppure una conferma (domanda, `id_conferma`).
- Gli strumenti usati sono le tool call del turno con il loro risultato (`ToolMessage`).
- Riusa la logica di `Sessione`, che diventa un sottile adattatore per la CLI locale nei test.

### `assistente/servizio.py` (modulo nuovo)
- `crea_app(agente, stato_mcp, controlla_modello, base_url) -> FastAPI` con:
  - `POST /conversazione` `{messaggio | messaggi, cronologia, riassunto}` → `RispostaAgente`;
  - `POST /conferma` `{id_conferma, conferma}` → `RispostaAgente`;
  - `GET /stato`; `GET /prompts`; `POST /prompts/{nome}` `{argomenti}` → messaggi.
- `python -m assistente.servizio`: stesso avvio di oggi (catalogo, archivio, MCP, preferenze,
  grafo), poi uvicorn. Log `servizio agente in ascolto su <host>:<porta>`.

### CLI (`python -m assistente`)
- `SessioneRemota(url)` con la stessa interfaccia di `Sessione` (`chiedi`, `chiedi_messaggi`,
  `conferma`, `cronologia`, `riassunto`), basata su `httpx`.
- `PromptRemoti(url)` con `elenca_prompt` e `ottieni_prompt`.
- Errori HTTP mostrati con il `detail` dell'agente; agente non raggiungibile → «Agente non
  raggiungibile su <url>. È avviato `python -m assistente.servizio`?».

## Evidenze

### Test automatici (senza LM Studio)
- API con grafo simulato (`TestClient`): risposta con strumenti usati e cronologia aggiornata;
  cronologia e riassunto ricevuti e restituiti; conferma delle note via `/conferma`; errore di
  connessione del modello → 503 con messaggio; `/stato` con modello giù → 503; `/openapi.json` e
  `/docs` disponibili; prompt.
- CLI remota contro l'app di test (trasporto httpx verso l'app): stesso comportamento della CLI locale.

### Prove reali
- Agente avviato con LM Studio: chiamata HTTP con una domanda che usa uno strumento, risposta e
  traccia nei log; stessa domanda dalla CLI: stessa risposta (stesso strumento e stesso risultato).
- LM Studio spento: `/stato` e `/conversazione` restituiscono 503 con messaggio comprensibile.
