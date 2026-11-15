# Assistente del laboratorio

Assistente del laboratorio che conversa con un modello locale servito da LM Studio, usabile dal
terminale o dal browser. Il flusso è un grafo LangGraph esplicito. Il modello chiede gli strumenti con
il tool calling e il programma li esegue davvero. L'agente è un servizio HTTP senza stato; la CLI e il
back-end (che salva le chat in PostgreSQL per il front-end) gli passano la cronologia a ogni turno.
Le note personali restano salvate in un file SQLite.

Gli strumenti sono collegati con tre meccanismi diversi, per confrontarli:

| Strumento | Meccanismo | Dove gira il codice |
|---|---|---|
| `ora_corrente` (fuso orario esplicito) | tool locale | `assistente/strumenti.py` |
| `calcola` (calcolatrice sicura, senza `eval`) | tool locale | `assistente/calcolatrice.py` |
| `cerca_articoli`, `dettaglio_articolo` (catalogo del laboratorio) | tool locale | `assistente/catalogo.py`, dati in `assistente/dati/catalogo.json` |
| `aggiungi_nota`, `elenca_note`, `cerca_note`, `elimina_nota` (note personali, eliminazione con conferma) | tool locale | `assistente/note.py`, dati in un file SQLite |
| `converti_unita` (unità come elenco chiuso) | server MCP via stdio | `convertitore_mcp/`, avviato dall'assistente come sottoprocesso |
| `giorni_tra_date`, `calcola_scadenza` | API HTTP | servizio `scadenze_api/`, chiamato con `httpx` da `assistente/client_api.py` |

Per il modello sono tutti normali strumenti: cambia solo dove viene eseguito il codice.

Prima dell'agente un router classifica ogni domanda come `conversazione` o `fuori_ambito`
rispetto all'ambito scritto in `AMBITO_AGENTE`: le domande fuori ambito ricevono un rifiuto
senza che l'agente venga eseguito. Dopo la risposta finale dell'agente un revisore controlla che
risponda a tutte le parti della domanda: se non è coerente la rimanda all'agente con il motivo, al
massimo `MAX_REVISIONI` volte. All'inizio del turno, oltre `SOGLIA_RIASSUNTO` messaggi, i turni vecchi
sono sostituiti da un riassunto. Le preferenze dell'utente (lingua, fuso orario, stile) arrivano da
una resource MCP e i prompt MCP si richiamano dalla CLI con `/prompt`.

I comandi sono PowerShell (Windows) e vanno lanciati dalla cartella `lezione_4/`.

## Requisiti

- LM Studio con il modello `google/gemma-4-e2b` caricato e il server avviato (porta 1234).
- Python, usato con `py` (verificato con 3.14).
- Docker Desktop, per l'avvio con Compose (e, in locale, per un PostgreSQL di prova).
- Node.js (facoltativo): esegue i test JavaScript del front-end; senza, quel test è saltato.

## Configurazione

```powershell
Copy-Item .env.example .env
```

Il file `.env` non va in Git. Le variabili sono:

| Variabile | Obbligatoria | Default |
|---|---|---|
| `LMSTUDIO_BASE_URL` | sì | in locale `http://localhost:1234/v1` |
| `LMSTUDIO_MODEL` | sì | `google/gemma-4-e2b` |
| `FUSO_ORARIO_PREDEFINITO` | no | `Europe/Rome` |
| `MAX_PASSAGGI_STRUMENTI` | no | `3` |
| `LOG_LEVEL` | no | `INFO` (valori: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`) |
| `SCADENZE_API_URL` | sì | in locale `http://localhost:8000`; in Docker il servizio gira nel container dell'agente (`SCADENZE_INTERNO=1`, da `compose.yaml`) |
| `SCADENZE_API_PORTA` | no | `8000` (porta del servizio `scadenze_api`) |
| `SCADENZE_API_HOST` | no | `127.0.0.1` (solo questo computer) |
| `PERCORSO_DB_NOTE` | no | `note.sqlite3`; in Docker `/app/note/note.sqlite3`, sul volume `note` (da `compose.yaml`) |
| `MAX_REVISIONI` | no | `2` (quante volte il revisore può rimandare una risposta all'agente in un turno) |
| `SOGLIA_RIASSUNTO` | no | `20` (oltre questo numero di messaggi si riassumono i turni vecchi) |
| `MESSAGGI_CONSERVATI` | no | `6` (messaggi recenti conservati, minore della soglia) |
| `PERCORSO_PREFERENZE` | no | `preferenze.json` (file della resource `utente://preferenze`, relativo alla cartella del progetto) |
| `AGENTE_HOST`, `AGENTE_PORTA` | no | `127.0.0.1`, `8100` (servizio dell'agente; in Docker `0.0.0.0`) |
| `AGENTE_URL` | no | `http://localhost:8100` (indirizzo dell'agente per la CLI e il back-end) |
| `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` | sì per Compose | credenziali di PostgreSQL in Docker; nel `.env`, mai in Git |
| `AMBITO_AGENTE` | sì | il testo di `.env.example` (strumenti del laboratorio, temi del corso, saluti) |

`AMBITO_AGENTE` descrive in una riga, senza virgolette, di che cosa si occupa l'assistente. Il router
la usa per decidere se una domanda è in ambito e il messaggio di rifiuto la riporta all'utente.
Per accettare nuovi argomenti si cambia questa variabile, non il codice. Se manca, l'avvio si ferma
con codice di uscita 2.

Back-end (`python -m backend`): `DATABASE_URL` (obbligatoria), `AGENTE_URL`, `BACKEND_HOST`
(`127.0.0.1`), `BACKEND_PORTA` (`8200`), `ORIGINI_CONSENTITE` (`http://localhost:8300`, separate da
virgola), `ATTESA_DATABASE` (secondi di attesa del database all'avvio, `30`). Front-end
(`python -m frontend`): `BACKEND_URL` (`http://localhost:8200`), `FRONTEND_PORTA` (`8300`).

L'identificativo del modello è quello restituito dal server:

```powershell
Invoke-RestMethod http://localhost:1234/v1/models
```

Nell'elenco `data` serve `google/gemma-4-e2b`. L'altro modello, `text-embedding-nomic-embed-text-v1.5`,
è di embedding e non va usato per la chat.

Ambiente virtuale e dipendenze:

```powershell
py -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements-dev.txt
```

Per caricare `.env` nella sessione PowerShell corrente (serve per l'avvio locale e per la prova reale):

```powershell
Get-Content .env | Where-Object { $_ -match '^\s*[^#\s][^=]*=' } | ForEach-Object { $k, $v = $_ -split '=', 2; Set-Item "env:$($k.Trim())" $v.Trim() }
```

## Avvio

L'applicazione ha quattro componenti (step 6–9 della roadmap):

| Componente | Comando | Porta locale | Ruolo |
|---|---|---|---|
| Agente | `python -m assistente.servizio` | `8100` (`AGENTE_PORTA`) | grafo LangGraph, client MCP e strumenti; API HTTP senza stato, documentazione su `/docs` |
| CLI | `python -m assistente` | — | client da terminale dell'API dell'agente (`AGENTE_URL`) |
| Back-end | `python -m backend` | `8200` (`BACKEND_PORTA`) | chat in PostgreSQL, inoltro delle domande all'agente; documentazione su `/api/docs` |
| Front-end | `python -m frontend` | `8300` (`FRONTEND_PORTA`) | interfaccia di chat nel browser; parla solo con il back-end (`BACKEND_URL`) |

### Con Docker Compose (consigliato)

Un solo comando avvia front-end, back-end, agente e PostgreSQL (`compose.yaml`); LM Studio resta
sull'host. Servono le variabili `POSTGRES_USER`, `POSTGRES_PASSWORD` e `POSTGRES_DB` nel `.env`
(vedi `.env.example`). Verificati:

```powershell
docker compose up -d --build
docker compose ps
```

Poi si apre `http://localhost:8080` nel browser. È pubblicato solo il front-end (`8080`, modificabile
con `FRONTEND_PORTA_HOST`): nginx serve l'interfaccia e inoltra `/api` al back-end; agente, back-end e
database non hanno porte pubblicate. Il server MCP e il servizio delle scadenze girano nel container
dell'agente. Le chat stanno nel volume `dati_postgres`, le note nel volume `note`:
`docker compose down` li conserva, **`docker compose down -v` li cancella**. I log dell'agente, con le
chiamate agli strumenti: `docker compose logs agente`.

La CLI in Docker (profilo `cli`, non parte con `up`) usa l'agente dello stack:

```powershell
docker compose run --rm assistente
```

### In locale (sviluppo)

Ogni componente in una finestra di PowerShell, dopo aver caricato `.env`. Verificati:

```powershell
.\.venv\Scripts\python -m scadenze_api          # servizio di giorni e scadenze
.\.venv\Scripts\python -m assistente.servizio   # agente (avvia da solo il server MCP)
.\.venv\Scripts\python -m assistente            # CLI, client dell'agente
```

Per il back-end serve un PostgreSQL raggiungibile: `DATABASE_URL`, per esempio
`postgresql://utente:password@127.0.0.1:5432/chat` (va impostata nella finestra, non è in `.env.example`).
Poi:

```powershell
.\.venv\Scripts\python -m backend    # usa AGENTE_URL (default http://localhost:8100)
.\.venv\Scripts\python -m frontend   # usa BACKEND_URL (default http://localhost:8200)
```

e si apre `http://localhost:8300`. Il back-end accetta le chiamate del browser dalle origini in
`ORIGINI_CONSENTITE` (default `http://localhost:8300`).

Nella CLI, dopo ogni domanda compare `(attendi: il modello sta rispondendo...)`: una risposta può
richiedere decine di secondi (router, agente, revisore e strumenti sono chiamate separate al modello).
I comandi sono `/esci`, `/prompts` e `/prompt` (vedi «Prompt MCP»). Se l'agente non è attivo la CLI
lo segnala all'avvio e a ogni domanda, e resta aperta.

Sessione con input da pipe (verificata con l'agente locale):

```powershell
"/prompts", "/prompt spiega livello=base", "/esci" | .\.venv\Scripts\python -m assistente
```

Il secondo comando è rifiutato dalla CLI («Argomento obbligatorio mancante: argomento») senza
chiamare il modello.

## Test

Suite normale, senza modello attivo (la prova reale risulta saltata):

```powershell
.\.venv\Scripts\python -m pytest -v
```

La suite comprende anche i test dell'API dell'agente e del back-end (con agente e archivio simulati),
del front-end (contratto OpenAPI allineato, server statico) e, se Node.js è installato, i test
JavaScript del front-end, eseguibili anche da soli:

```powershell
node --test frontend/test/front.test.mjs
```

Archivio delle chat su un PostgreSQL vero, attivato esplicitamente (verificato con un container
`postgres:17.6-alpine` di prova; i dati del database indicato vengono cancellati a ogni test):

```powershell
docker run -d --name pg-test-lab -e POSTGRES_USER=lab -e POSTGRES_PASSWORD=lab -e POSTGRES_DB=lab_test -p 127.0.0.1:55432:5432 postgres:17.6-alpine
$env:POSTGRES_TEST_URL = "postgresql://lab:lab@127.0.0.1:55432/lab_test"
.\.venv\Scripts\python -m pytest tests/test_backend_archivio.py --postgres -v
docker rm -f pg-test-lab
```

Verificato: 16 test superati, compreso «chat presenti dopo il riavvio» (nuova istanza, nuove
connessioni).

Suite nel container (immagine dell'agente, che contiene anche back-end e front-end per i test):

```powershell
docker compose run --rm assistente python -m pytest -v
```

Prova reale con LM Studio, attivata esplicitamente (richiede il server e `.env` caricato):

```powershell
.\.venv\Scripts\python -m pytest --lmstudio -m lmstudio -v -s
```

Solo le prove reali del router (domanda in ambito con strumento, fuori ambito, tema del corso,
domanda di seguito, seguito di una domanda fuori ambito), 5 test, circa 8 minuti:

```powershell
.\.venv\Scripts\python -m pytest --lmstudio -m lmstudio -k router -v -s
```

Verificate con `google/gemma-4-e2b`: 5 superati su 5.

Solo le prove reali del revisore, 2 test, circa 6 minuti:

```powershell
.\.venv\Scripts\python -m pytest --lmstudio -m lmstudio -k revisore -v -s
```

- `test_revisore_risposta_coerente`: «Che ore sono adesso a Tokyo?» è approvata al primo passaggio
  (`revisore: coerente=sì ... -> fine`).
- `test_revisore_risposta_parziale_corretta`: la prima risposta dell'agente è forzata parziale
  (solo l'ora per «Che ore sono a Tokyo e quanto fa 17 * 23?»); il revisore reale la rifiuta con il
  motivo (`coerente=no motivo=La risposta ignora la richiesta di calcolare il prodotto ... -> agente
  (revisione 1 di 2)`) e l'agente reale risponde con 391.

Verificate con `google/gemma-4-e2b`: 2 superati su 2. Osservazione: dopo la prima risposta forzata il
modello calcola 17 * 23 a mente invece di chiamare `calcola`; con «17 per 23» lo aveva letto come una
divisione, perciò la prova usa «17 * 23».

La prova reale completa fa anche una domanda per ogni strumento (ora, calcolo, conversione, giorni lavorativi),
una conversione impossibile, cinque domande sul catalogo (ricerca, dettaglio, ricerca seguita da
dettaglio, nessun risultato, codice inesistente) e sei sulle note (aggiunta, ricerca, elenco,
nessun risultato, eliminazione confermata, eliminazione annullata), in tutto 16 test; avvia da sola
il servizio delle scadenze su una porta libera e il server MCP, e usa un archivio delle note
temporaneo. Le prove controllano quali strumenti vengono chiamati e con quali argomenti; le risposte
finali sono stampate (`-s`) e vanno lette a occhio per verificare che il modello non inventi
articoli o note. Richiede 23–29 minuti.

Verificata con `google/gemma-4-e2b`: 15 test superati su 16. Le sei prove delle note passano;
`test_catalogo_ricerca_poi_dettaglio` non è stabile (ripetuta tre volte passa due): quando fallisce il
modello cerca con `categoria=sensori` e poi non chiama `dettaglio_articolo`. Anche con temperatura 0
il modello non risponde sempre allo stesso modo.

Prove reali degli step 3–5, verificate con `google/gemma-4-e2b`, tutte superate:

```powershell
.\.venv\Scripts\python -m pytest --lmstudio -m lmstudio -k "riassunto or preferenze or prompt_" -v -s
```

- `test_riassunto_conserva_il_nome`: soglia bassa (6 messaggi, 2 conservati); «Ciao, mi chiamo Giulia»,
  poi due domande, poi «Come mi chiamo?» → «Ti chiami Giulia», con nei log
  `riassunto: 7 messaggi prima, 5 dopo (2 riassunti)` e `riassunto: 9 messaggi prima, 5 dopo (4 riassunti)`.
- `test_preferenze_fuso_predefinito_new_york`: con `fuso_orario=America/New_York` nel file,
  «Che ore sono?» chiama `ora_corrente` con `America/New_York`.
- `test_preferenze_lingua_inglese`: con `lingua=inglese` la risposta è in inglese.
- `test_prompt_spiega_livello_base`: `/prompt spiega argomento="Model Context Protocol" livello=base`
  passa dal router (`conversazione`) e dal revisore (`coerente=sì`).
- `test_prompt_riassumi_conversazione`: dopo due domande il riassunto cita Tokyo e il calcolo.

Durante queste prove un'esecuzione è rimasta bloccata per ore: il modello non rispondeva e il
revisore è andato in timeout; ripetuta da sola, la prova è passata.

La prova reale completa (`-m lmstudio` senza `-k`) usa ora il grafo con router, revisore e
preferenze; finora è stata eseguita solo a gruppi (comandi sopra), non tutta insieme.

Una risposta simulata nei test automatici non dimostra che il modello locale sappia usare lo strumento:
solo la prova reale e le sessioni reali lo fanno.

I test che avviano il server MCP vero (`tests/test_server_mcp.py`, `tests/test_client_mcp.py`) usano
anche un piccolo server di prova, `tests/server_mcp_prova.py`, per simulare un server che cade o
che non risponde in tempo.

## Regole degli strumenti

- **Calcolatrice:** numeri, `+ - * / % **`, parentesi e segno. Tutto il resto (nomi, funzioni,
  testo, confronti) è rifiutato con il motivo. Limiti: 200 caratteri, esponente fino a 100,
  risultati fino a 1e100.
- **Convertitore:** lunghezza (`mm cm m km in ft mi`), massa (`g kg t oz lb`), temperatura
  (`C F K`), volume (`ml l`), tempo (`s min h d`). Grandezze diverse o temperature sotto lo zero
  assoluto danno errore.
- **Giorni e scadenze:** date solo `AAAA-MM-GG`. Il giorno di inizio è escluso, quello di fine
  incluso. I giorni lavorativi escludono sabato, domenica e le festività nazionali del file
  `scadenze_api/dati/festivita_it.json` (anni 2026 e 2027; fonte: legge 260/1949 e successive
  modifiche, legge 151/2025 per il 4 ottobre). Il risultato è indicativo e non ha valore normativo.
- **Catalogo:** sola lettura, dal file `assistente/dati/catalogo.json` (vedi sotto).
- **Note:** testo fino a 500 caratteri; elenco e ricerca mostrano al massimo le 20 note più
  recenti. L'eliminazione avviene solo dopo un «sì» dell'utente (vedi sotto).

## Note personali

Le note sono promemoria dell'utente salvati in un file SQLite che resta dopo la chiusura
dell'assistente; la cronologia della conversazione invece dura quanto la sessione della CLI (dal browser le chat sono salvate dal back-end in PostgreSQL). Il file è
`PERCORSO_DB_NOTE` (predefinito `note.sqlite3` nella cartella da cui si avvia l'assistente; la
cartella viene creata se manca). I file `*.sqlite3` sono esclusi da Git e dall'immagine Docker; in
Docker il file sta sul volume `note` (vedi «Avvio»).

Ogni nota ha un numero, che non viene mai riusato dopo un'eliminazione, la data di creazione (nel
fuso `FUSO_ORARIO_PREDEFINITO`) e il testo.

- `aggiungi_nota(testo)`: salva subito, senza conferma.
- `elenca_note()`: tutte le note, in ordine di numero.
- `cerca_note(testo)`: le note che contengono tutte le parole; maiuscole e accenti non contano.
  Se non trova nulla lo dice esplicitamente.
- `elimina_nota(numero)`: prima di eseguirla il grafo si ferma e il terminale mostra la nota presa
  dall'archivio, non dal modello:

  ```text
  Eliminare la nota 3 (2026-11-02 14:05): "il sensore SEN-004 va ricalibrato"? [sì/no]
  Conferma>
  ```

  `sì`, `si` o `s` (maiuscole e spazi non contano) eliminano; qualunque altra risposta, anche una
  riga vuota, lascia la nota com'è. Ctrl+C o la fine dell'input durante la conferma chiudono
  l'assistente senza eliminare. Si elimina una nota alla volta.

  Nel terminale interattivo, prima di `Conferma>` l'assistente scarta quanto è stato scritto mentre
  il modello lavorava: la conferma vale solo per la risposta data dopo aver letto la domanda. Con
  l'input da pipe nulla viene scartato.

Esempi di richieste: «Annota che il saldatore va pulito», «Cosa avevo scritto sul sensore?»,
«Quali note ho?», «Elimina la nota sul sensore».

## Catalogo del laboratorio

Il file `assistente/dati/catalogo.json` è una lista di articoli con i campi `codice`, `nome`,
`categoria`, `descrizione`, `quantita` (intero ≥ 0) e `posizione`. Categorie e prefissi del codice
(formato `AAA-000`):

| Prefisso | Categoria |
|---|---|
| `SCH` | schede |
| `SEN` | sensori |
| `ATT` | attuatori |
| `CAV` | cavi |
| `ALI` | alimentazione |
| `MIS` | strumenti di misura |

Il file viene letto e controllato all'avvio: campi mancanti o in più, testi vuoti, codice fuori
formato o con prefisso diverso dalla categoria, categoria sconosciuta, quantità non intera o
negativa e codici duplicati fermano l'assistente con «Catalogo non valido: ...» (codice di uscita 4).

- `cerca_articoli(testo, categoria)`: tutte le parole del testo devono comparire in nome,
  descrizione o categoria; maiuscole e accenti non contano, singolari e plurali sì. Al massimo
  10 risultati. Se non trova nulla lo dice esplicitamente.
- `dettaglio_articolo(codice)`: scheda completa; spazi, trattini e maiuscole nel codice non contano.

Esempi di domande: «Avete sensori di temperatura?», «Dimmi tutto su SEN-004», «Dov'è il sensore di
umidità?», «Avete stampanti 3D?» (nessun risultato), «Dammi il dettaglio dell'articolo XYZ-999»
(codice inesistente).

## Prompt MCP

Il server MCP espone due prompt, richiamati esplicitamente dall'utente dalla CLI:

| Prompt | Argomenti |
|---|---|
| `spiega` | `argomento` (obbligatorio), `livello` (`base`, `intermedio`, `avanzato`; default `base`) |
| `riassumi_conversazione` | `stile` (`sintetico`, `dettagliato`; default `sintetico`) |

```text
/prompts
/prompt spiega argomento="Model Context Protocol" livello=base
/prompt riassumi_conversazione stile=sintetico
```

`/prompts` mostra nome, descrizione e argomenti (da `prompts/list`). Con `/prompt` la CLI controlla
gli argomenti rispetto a `prompts/list`: un argomento obbligatorio mancante o sconosciuto blocca la
richiesta senza chiamare il modello. Un valore fuori elenco (per esempio `livello=esperto`) lo rifiuta
il server («Prompt non disponibile: … Controlla nome e argomenti con /prompts»). I messaggi ottenuti
(`prompts/get`) entrano nella cronologia e passano dal grafo come una domanda: riassunto, router,
agente, strumenti e revisore. Nei log dell'agente: `prompts/get spiega {...}: 1 messaggi` e il testo
del messaggio.

## Servizi HTTP

**Agente** (`python -m assistente.servizio`, documentazione OpenAPI su `http://localhost:8100/docs`):

| Endpoint | Uso |
|---|---|
| `POST /conversazione` | `{messaggio, cronologia, riassunto}` → `{tipo, risposta, strumenti, cronologia, riassunto}` |
| `POST /conferma` | `{id_conferma, conferma}`: risposta sì/no a un'eliminazione di nota (`tipo="conferma"`) |
| `GET /stato` | agente, strumenti MCP caricati all'avvio e modello raggiungibile (`503` se manca qualcosa) |
| `GET /prompts`, `POST /prompts/{nome}` | `prompts/list` e `prompts/get` del server MCP |

L'agente è senza stato: cronologia e riassunto arrivano dal chiamante e tornano aggiornati. Unica
eccezione: un'eliminazione in attesa di conferma resta nell'agente finché non arriva la risposta.
Errori: LM Studio non raggiungibile `503`, LM Studio in errore `502`, conferma sconosciuta `404`.

**Back-end** (`python -m backend`, documentazione su `http://localhost:8200/api/docs`): `POST /api/chat`
(crea), `GET /api/chat` (elenco con titolo e data dell'ultimo messaggio), `GET /api/chat/{id}`
(messaggi in ordine), `POST /api/chat/{id}/messaggi` (domanda → agente → domanda e risposta salvate),
`POST /api/chat/{id}/conferma`, `DELETE /api/chat/{id}`, `GET /api/stato`. Se l'agente non è
raggiungibile risponde `503` e **non salva la domanda**: il front-end la lascia nel campo per riprovare.

**Front-end:** le chiamate sono generate dal documento OpenAPI del back-end. Se il back-end cambia:

```powershell
.\.venv\Scripts\python -m frontend.genera_api
```

## Checklist manuale

Da eseguire in una sessione reale, in locale e in Docker, controllando anche i log. Le voci 1–9
sono state verificate con `google/gemma-4-e2b`; la 10 in parte (vedi la voce). Le voci 1–11 sono state
verificate con la CLI che eseguiva il grafo nello stesso processo; dallo step 6 la CLI è un client
dell'agente HTTP: la logica del grafo è la stessa, ma **le voci 5–8 e 10 (errori, Ctrl+C, conferma
interattiva) vanno riverificate con la CLI client**. Per la voce 4 con una domanda generica su Marte il
modello non chiama lo strumento: per provare l'errore serve una richiesta esplicita, per esempio
"Usa lo strumento ora_corrente con il fuso orario Marte/Base".

1. Domanda sull'ora senza luogo ("Che ore sono?"): una chiamata a `ora_corrente` con il fuso predefinito
   (`Europe/Rome`) e una risposta con l'ora restituita.
2. Domanda con un luogo ("Che ore sono a Tokyo?"): chiamata con `Asia/Tokyo`.
3. Domanda di seguito ("E a New York?"): chiamata con `America/New_York`, perché la domanda si
   capisce solo con la cronologia.
4. Fuso inesistente (per esempio "Che ore sono su Marte/Base?"): lo strumento restituisce
   `Fuso orario non valido` e il modello lo spiega, senza chiudere la sessione.
5. LM Studio spento: la sessione mostra «LM Studio non raggiungibile su ...» e resta aperta.
6. Ctrl+C durante una risposta e subito dopo l'avvio, in locale e in Docker con TTY
   (`docker compose run --rm assistente`): l'assistente si chiude in modo ordinato, senza traceback.
7. Servizio `scadenze_api` spento durante la sessione: una domanda su giorni o scadenze riceve un
   errore spiegato e l'assistente resta aperto.
8. Dopo l'uscita dall'assistente non resta acceso nessun processo `convertitore_mcp`.
9. Catalogo: le cinque domande di esempio della sezione «Catalogo del laboratorio». Nei log
   compaiono `cerca_articoli` e/o `dettaglio_articolo`; le risposte citano solo articoli, quantità
   e posizioni presenti nel file. Verificata con la prova reale e, in Docker, con
   `"Avete sensori di temperatura?", "/esci" | docker compose run --rm -T assistente`.
10. Note: «Annota che il saldatore va pulito» chiama `aggiungi_nota`; in una sessione nuova «Quali
    note ho?» la ritrova (in Docker grazie al volume `note`). «Elimina la nota sul saldatore» mostra
    la riga `Conferma>`: con `no` la nota resta, con `sì` viene eliminata; Ctrl+C durante
    `Conferma>` chiude l'assistente senza eliminare. Verificata con la prova reale e in Docker con
    input da pipe (aggiunta, ritrovata in una seconda sessione, eliminazione con conferma);
    **da verificare a mano** la sessione interattiva con la conferma, in locale e in Docker con TTY,
    compreso Ctrl+C durante `Conferma>`.
11. Router, con `LOG_LEVEL=INFO`: «Che ore sono a Tokyo?» produce nei log `router: categoria=conversazione
    ... -> agente`, poi `agente: chiamata al modello` e la chiamata a `ora_corrente`; «Dammi la ricetta
    della carbonara» produce `router: categoria=fuori_ambito ... -> rifiuto` e `rifiuto: domanda fuori
    ambito, agente non eseguito`, senza nessuna riga `agente:`, e la risposta elenca l'ambito.
    Verificata in locale con
    `"Che ore sono a Tokyo?", "Dammi la ricetta della carbonara", "/esci" | .\.venv\Scripts\python -m assistente`
    (servizio `scadenze_api` avviato in un'altra finestra); da verificare in Docker.
12. Revisore: una domanda in due parti con risposta parziale viene rimandata all'agente
    (`revisore: coerente=no ... -> agente (revisione 1 di 2)`) e la risposta finale è completa.
    Verificata con la prova reale; da verificare in una sessione interattiva.
13. Riassunto: con `SOGLIA_RIASSUNTO` bassa (per esempio 6) il nome detto al primo turno è ancora
    usato dopo la compressione. Verificata con la prova reale.
14. Preferenze: modificando `preferenze.json` (fuso, lingua, stile) e riavviando l'agente
    (`docker compose restart agente` in Docker) le risposte successive ne tengono
    conto senza cambiare il codice. Verificata con la prova reale (file temporaneo).
15. Prompt: `/prompts`, `/prompt spiega ...`, argomenti mancanti o sconosciuti bloccati. Verificata
    con la CLI client e con la prova reale.
16. Stessa risposta da CLI e API: «Quanto fa 17 * 23?» con una chiamata HTTP a `POST /conversazione`
    e dalla CLI dà la stessa risposta (391). Verificata in locale.
17. Browser (Docker): nuova chat, «Ciao, mi chiamo Giulia. Che ore sono adesso a Tokyo?» → risposta
    con `ora_corrente(fuso_orario=Asia/Tokyo)` sotto il messaggio; nei log dell'agente
    `api: POST /conversazione`, `router: ...`, `chiamata strumento ora_corrente ...`, `revisore: ...`.
    Verificata.
18. Agente spento (`docker compose stop agente`): inviando una domanda il browser mostra «Agente non
    raggiungibile su http://agente:8100: la domanda non è stata salvata…», la domanda resta nel campo e
    l'interfaccia resta usabile. Verificata.
19. Persistenza: dopo `docker compose down` e `docker compose up -d` la chat è ancora nell'elenco con i
    suoi messaggi. Verificata.
20. Eliminazione di una chat dal browser (conferma del browser) e conferma Sì/No di un'eliminazione
    di nota dall'interfaccia: coperte dai test automatici, **da verificare a mano nel browser**.

## Struttura del grafo

```mermaid
flowchart TD
    START([START]) --> riassunto
    riassunto -->|sotto la soglia: nessuna chiamata| router
    riassunto -->|sopra la soglia: turni vecchi riassunti| router
    router -->|conversazione| agente
    router -->|fuori_ambito| rifiuto
    rifiuto --> END([END])
    agente -->|nessuna chiamata a strumento| revisore
    revisore -->|coerente, o limite di revisioni| END
    revisore -->|non coerente + motivo| agente
    agente -->|chiamate e passaggi sotto il limite| strumenti
    agente -->|chiamata a elimina_nota, sotto il limite| conferma_eliminazione
    agente -->|chiamate e limite raggiunto| limite_raggiunto
    conferma_eliminazione -->|sì / no dell'utente| strumenti
    strumenti --> agente
    limite_raggiunto --> END
```

Lo stato ha `messages` (la cronologia), `passaggi_strumenti` (il contatore, azzerato a ogni domanda),
`eliminazioni_confermate` (le chiamate a `elimina_nota` confermate dall'utente), `categoria` e
`motivo` (la decisione del router per la domanda corrente) e `revisioni` (le risposte rimandate
all'agente dal revisore nel turno) e `riassunto` (il riassunto dei turni tolti dalla cronologia). I
limiti sono `MAX_PASSAGGI_STRUMENTI` e `MAX_REVISIONI`.

`riassunto` lavora all'inizio di ogni turno. Sotto `SOGLIA_RIASSUNTO` messaggi non chiama il modello.
Sopra la soglia sostituisce i turni più vecchi con un unico riassunto riscritto (unisce il riassunto
precedente e i nuovi messaggi, non si accumula) e conserva almeno gli ultimi `MESSAGGI_CONSERVATI`
messaggi. Taglia solo all'inizio di un turno, quindi non separa mai una richiesta di strumento dal suo
`ToolMessage`. Il riassunto va in coda al prompt di sistema dell'agente. Se il modello non riesce a
riassumere, il turno prosegue con la cronologia intera (`WARNING`).

Le preferenze dell'utente sono una resource MCP (`utente://preferenze`, file `preferenze.json`):
l'agente la legge una volta all'avvio, prima della prima domanda, e la mette in cima al prompt di
sistema. Lingua e fuso orario sostituiscono quelli predefiniti. Non è uno strumento: il modello non
la chiama e non compare tra i tool. Se non è disponibile si usano i valori predefiniti (`WARNING`).
Modificando il file e riavviando l'agente (le preferenze si leggono all'avvio del servizio; in
Docker `docker compose restart agente`), le risposte si adeguano senza cambiare il codice.
Il codice è in `assistente/grafo.py`; prompt, schema della decisione e messaggio di rifiuto sono in
`assistente/router.py`; quelli del revisore in `assistente/revisore.py`.

`router` chiama lo stesso modello con output strutturato (`json_schema`): riceve l'ambito, gli ultimi
turni della conversazione (solo domande e risposte finali, senza chiamate agli strumenti) e la domanda
corrente, e restituisce `categoria` e `motivo`. Non sceglie gli strumenti: quello resta compito di
`agente`. Se l'output non è valido (vuoto, JSON troncato, categoria fuori schema, risposta interrotta
per lunghezza) la domanda passa comunque all'agente (fail-open), con un `WARNING` nei log; questi casi
sono intercettati in `crea_router` (`assistente/modello.py`). LM Studio irraggiungibile o un errore del
server invece non sono fail-open: il turno fallisce con il messaggio di errore e la cronologia resta
intatta. `rifiuto` risponde con un testo fisso che riporta l'ambito, senza chiamare il modello.

`revisore` chiama lo stesso modello con output strutturato (`coerente` sì/no e `motivo`): riceve gli
ultimi turni, la domanda corrente e la risposta proposta, senza le chiamate agli strumenti. Non
verifica i fatti, solo che ogni parte della domanda abbia una risposta in tema. Se la risposta non è
coerente aggiunge alla cronologia un'indicazione per l'agente (un messaggio con `name="revisore"` che
inizia con «Indicazione del revisore:») e torna ad `agente`. Dopo `MAX_REVISIONI` rimandi restituisce
l'ultima risposta e lo segnala nei log. Un output non valido del revisore approva la risposta
(fail-open). Il rifiuto del router e il messaggio di limite degli strumenti non passano dal revisore.
Nel terminale compare solo la risposta finale; bozze e indicazioni restano nella cronologia, ma il
router e il revisore non le considerano come turni della conversazione.

`conferma_eliminazione` legge la nota dall'archivio e, se esiste, ferma il grafo con `interrupt()`;
il terminale fa la domanda e riprende il grafo con `Command(resume=True/False)`. `strumenti` esegue
`elimina_nota` solo se la chiamata è confermata. Per fermarsi e riprendere il grafo usa un
checkpointer in memoria (`InMemorySaver`) e un thread nuovo per ogni domanda: la cronologia resta
quella della sessione e si aggiorna solo quando il turno finisce bene.

## Diagnosi

**«Server MCP del convertitore non avviato»** (l'assistente esce con codice 3): il server
`convertitore_mcp` non è partito o non ha risposto entro 30 secondi. Controllare che le dipendenze
siano installate (`mcp` è in `requirements.txt`) e che l'assistente venga lanciato dalla cartella
`lezione_4/`.

**«Archivio note non disponibile: ...»** (l'assistente esce con codice 5): il file indicato da
`PERCORSO_DB_NOTE` non si può creare o aprire (cartella non creabile, file non scrivibile, file che
non è un database SQLite). Correggere il percorso o spostare il file non valido.

**«Catalogo non valido: ...»** (l'assistente esce con codice 4): il messaggio indica l'articolo
(posizione nella lista e codice) e il motivo; correggere `assistente/dati/catalogo.json`.

**«Errore: servizio scadenze non raggiungibile su ...»:** in locale il servizio va avviato in
un'altra finestra con `.\.venv\Scripts\python -m scadenze_api` e `SCADENZE_API_URL` deve puntare
alla stessa porta. In Docker l'indirizzo è `http://scadenze:8000`.

**«festività non disponibili per il 2028»:** il file delle festività copre solo il 2026 e il 2027;
per gli altri anni il conteggio dei giorni lavorativi è rifiutato, quello di calendario funziona.

**LM Studio non raggiungibile in locale** ("LM Studio non raggiungibile su ..."):
- il server di LM Studio deve essere avviato;
- `Invoke-RestMethod http://localhost:1234/v1/models` deve rispondere;
- `LMSTUDIO_BASE_URL` deve essere `http://localhost:1234/v1` e `.env` deve essere stato caricato.

**LM Studio non raggiungibile da Docker:**
- nel container l'indirizzo è `http://host.docker.internal:1234/v1`, già impostato da `compose.yaml`;
- in LM Studio, nelle impostazioni del server, può servire attivare l'opzione per servire sulla rete
  locale (Serve on Local Network), così il server non ascolta solo su localhost.
  Non è stata necessaria nella prova su questo computer, ma è il primo controllo se la connessione fallisce.

**Il modello non chiama lo strumento:** l'ora risulta inventata e nei log manca la riga
`chiamata strumento`. Controllare che `LMSTUDIO_MODEL` sia il modello di chat previsto
(`google/gemma-4-e2b`), poi riprovare la prova reale mostrando i log in tempo reale:
`.\.venv\Scripts\python -m pytest --lmstudio -m lmstudio -v -s --log-cli-level=INFO`
(`LOG_LEVEL` agisce solo sull'avvio dell'applicazione, non su pytest).
Il comportamento dipende dal modello: solo la prova reale lo conferma.

**Righe del router nei log** (con `LOG_LEVEL=INFO`):
- `router: categoria=<categoria> motivo=<motivo> -> <agente|rifiuto>`: la decisione per la domanda;
- `agente: chiamata al modello`: l'agente è stato eseguito (manca per le domande rifiutate);
- `rifiuto: domanda fuori ambito, agente non eseguito`;
- `WARNING ... router: output non valido (...), la domanda passa all'agente`: il modello non ha
  restituito una decisione valida e la domanda è trattata come in ambito.

**Righe del revisore nei log** (con `LOG_LEVEL=INFO`):
- `revisore: coerente=sì motivo=<motivo> -> fine`: risposta approvata;
- `revisore: coerente=no motivo=<motivo> -> agente (revisione <n> di <max>)`: risposta rimandata
  all'agente con il motivo;
- `WARNING ... revisore: limite di <max> revisioni raggiunto, si restituisce l'ultima risposta`;
- `WARNING ... revisore: output non valido (...), la risposta è approvata`.

**Risposte lente:** ogni domanda fa almeno tre chiamate al modello (router, agente, revisore) e ogni
rimando del revisore ne aggiunge due. Con `MAX_REVISIONI=1` il caso peggiore si accorcia.

**Una domanda valida viene rifiutata:** leggere il `motivo` nella riga `router:` e allargare
`AMBITO_AGENTE` nel `.env` con l'argomento mancante, poi ricaricare `.env` e riavviare l'assistente.
Il router dipende dal modello: una riformulazione della domanda può dare un esito diverso.

**Variabile mancante:** l'avvio si ferma con «Variabile d'ambiente obbligatoria mancante o vuota: NOME».
In locale caricare `.env` con la riga PowerShell della sezione Configurazione. In Docker verificare
che `.env` esista. Ogni nuova finestra di PowerShell richiede di caricare di nuovo `.env`.

**Ctrl+Z non chiude la sessione nel terminale di VS Code:** il terminale integrato non trasmette Ctrl+Z
come fine dell'input, e il carattere arriva all'assistente come testo. Nella finestra di PowerShell
normale Ctrl+Z e Invio funzionano. Nel terminale di VS Code usare `/esci` o Ctrl+C.

**«LM Studio non ha risposto in tempo su …»:** il modello è occupato (per esempio da un'altra
richiesta) o la risposta è molto lunga; il timeout per chiamata è di 300 secondi. Riprovare quando
LM Studio è libero.

**Righe del riassunto e delle preferenze nei log dell'agente:**
- `riassunto: <n> messaggi prima, <m> dopo (<k> riassunti)`: compressione eseguita;
- `WARNING ... riassunto: non riuscito (...), cronologia invariata`;
- `resources/read utente://preferenze: <n> caratteri` e `preferenze: lingua=... fuso_orario=... stile=...`
  all'avvio, prima di qualsiasi chiamata agli strumenti;
- `WARNING ... preferenze: resource utente://preferenze non disponibile (...)` o `... non valido`:
  si usano i valori predefiniti (per un campo non valido solo quel campo).

**«Agente non raggiungibile su …»** (CLI o front-end): l'agente non è avviato o `AGENTE_URL` punta
altrove. In locale: `.\.venv\Scripts\python -m assistente.servizio`; in Docker:
`docker compose ps` e `docker compose logs agente`. Lo stato completo: `GET /stato` dell'agente o
`GET /api/stato` del back-end (`http://localhost:8080/api/stato` con Docker).

**Il back-end non parte («Database non disponibile»)** (codice di uscita 3): `DATABASE_URL` non è
raggiungibile entro `ATTESA_DATABASE` secondi. In Docker controllare che il `.env` abbia
`POSTGRES_USER`, `POSTGRES_PASSWORD` e `POSTGRES_DB`, e `docker compose logs database`.

**Il front-end mostra «Back-end non raggiungibile»:** in locale `BACKEND_URL` deve puntare al
back-end e il back-end deve consentire l'origine della pagina in `ORIGINI_CONSENTITE`.
