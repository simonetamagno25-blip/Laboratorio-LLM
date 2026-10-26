# Assistente del laboratorio — specifica

Data: 2026-10-26
Stato: approvata dall'utente il 2026-10-26

## 1. Intento

Il progetto del corso «Deep Learning e LLM: costruire chatbot e agenti» parte con
un'applicazione Python da terminale. Mette insieme gli elementi di base di un agente:

- un grafo LangGraph esplicito, in cui stato, nodi e instradamento si riconoscono leggendo il codice;
- un modello locale servito da LM Studio sull'host;
- la cronologia della conversazione, che dura quanto la sessione;
- un primo strumento, l'orologio, richiesto dal modello con il tool calling ed eseguito davvero dal programma.

L'applicazione resta volutamente piccola, perché le prossime lezioni ci aggiungeranno altro.
Il grafo deve quindi essere leggibile ed estendibile, non completo.

Il progetto si chiude con successo quando sono vere tre cose:

- in una sessione reale con LM Studio, alla domanda sull'ora il modello richiede lo strumento,
  il log mostra la chiamata e la risposta finale riporta l'ora restituita dallo strumento;
- la stessa prova riesce anche avviando l'applicazione con Docker Compose;
- i test automatici passano senza modello attivo.

## 2. Obiettivi, non obiettivi, anti-obiettivi

**Obiettivi**
- Conversazione da terminale con un modello di LM Studio, mantenendo il contesto fra i turni della stessa sessione.
- Strumento orologio con fuso orario esplicito.
- Ciclo modello → strumento → modello nel grafo, con un limite al numero di passaggi.
- Chiamate agli strumenti visibili nei log.
- Avvio locale e con Docker Compose, configurazione solo da variabili d'ambiente.
- Test automatici che non richiedono un modello, più istruzioni per le prove reali.

**Non obiettivi, per ora**
- Altri strumenti, MCP, RAG, workflow, interfacce web o grafiche.
- Persistenza della cronologia: alla chiusura si perde.
- Streaming della risposta, più sessioni o più utenti.
- Containerizzare LM Studio.

**Anti-obiettivi**: cose che renderebbero il lavoro un fallimento anche se «funziona».
- Un grafo nascosto dietro scorciatoie prefabbricate, come un agente ReAct già pronto,
  per cui non si vede dove si decide se eseguire lo strumento.
- Un identificativo del modello scritto nel codice o inventato.
- Test «verdi» con un modello finto presentati come prova che il modello reale sa usare lo strumento.
- Un ciclo strumento senza limite, che può girare all'infinito.
- Credenziali, `.env`, ambienti virtuali o cache finiti in Git.

## 3. Vincoli

Valgono quelli del `CLAUDE.md`. In sintesi:

- Python, codice sincrono, moduli piccoli.
- LM Studio raggiunto tramite la sua API compatibile con OpenAI.
- Indirizzo del server e identificativo del modello solo da variabili d'ambiente.
  L'identificativo è uno di quelli restituiti da `GET /v1/models`.
- File `.env.example` senza credenziali; il `.env` reale resta fuori da Git.
- Dipendenze motivate e con versioni fissate.
- Comandi documentati anche per PowerShell.
- Conventional Commits in italiano, incrementi piccoli e verificati, push solo su richiesta.

**Cartella del progetto**: `lezione_4/` (decisione dell'utente). Il `CLAUDE.md` di `lezione_4/`
nomina ancora `assistente-laboratorio/`. Va aggiornato perché indichi `lezione_4/` come radice
del progetto e `lezione_4/docs/superpowers/` per specifica e piano.

**Stato rilevato il 2026-10-26**
- Branch `main`. `lezione_4/` non è ancora tracciata e contiene solo `CLAUDE.md`.
- Sul computer host ci sono Python 3.10.0 (`python`) e 3.14.10 (`py`), Docker 29.6.1 e Compose v5.2.0.
- LM Studio risponde su `http://localhost:1234`. `GET /v1/models` restituisce `google/gemma-4-e2b`
  e `text-embedding-nomic-embed-text-v1.5`. Il secondo è un modello di embedding e non va usato per la chat.

## 4. Comportamento

### 4.1 Sessione da terminale
- All'avvio l'applicazione legge la configurazione. Se manca una variabile obbligatoria si ferma
  con un messaggio che dice quale variabile manca.
- Mostra un breve messaggio di benvenuto e poi un prompt (`Tu> `). Ogni riga non vuota è una domanda.
- La risposta finale appare come `Assistente> ...`.
- Si esce con `/esci`, con Ctrl+C o con fine input (Ctrl+D, o Ctrl+Z e Invio su Windows),
  sempre senza traceback.
- Le righe vuote vengono ignorate. Non ci sono altri comandi.
- La cronologia, cioè tutti i messaggi dei turni precedenti, viene passata al modello a ogni turno.
  Alla chiusura si perde.
- Se LM Studio non è raggiungibile o risponde con un errore, la sessione mostra un messaggio
  comprensibile (per esempio «LM Studio non raggiungibile su …») e resta aperta.
  Il turno fallito non viene aggiunto alla cronologia.

### 4.2 Strumento orologio
- Nome: `ora_corrente`. Parametro obbligatorio: `fuso_orario`, un nome IANA come `Europe/Rome`.
- Restituisce un testo con data e ora in ISO 8601 con scostamento, più il nome del fuso,
  per esempio `2026-10-26T17:05:12+01:00 (Europe/Rome)`.
- Con un fuso non valido restituisce al modello un messaggio d'errore leggibile
  (`Fuso orario non valido: 'Marte/Base'`), senza sollevare eccezioni che chiudono la sessione.
  Così il modello può correggersi o spiegarlo all'utente.
- L'istante si legge da un orologio iniettabile, in modo che i test lo controllino.
- **Domanda senza luogo**: la variabile `FUSO_ORARIO_PREDEFINITO` (predefinita `Europe/Rome`)
  viene scritta nel prompt di sistema. Il modello riceve l'istruzione di usarla quando l'utente
  non indica un luogo, e di usare sempre lo strumento per data e ora invece di inventarle.
  Il fuso arriva comunque come parametro esplicito della chiamata.
  *(Scelta mia: l'utente ha detto «fallo» alla mia proposta.)*

### 4.3 Grafo

Lo stato contiene:
- `messages`: la lista dei messaggi, con il reducer standard di LangGraph che li accoda;
- `passaggi_strumenti`: un contatore dei giri di strumenti fatti nel turno corrente.

Nodi:
- `modello`: invia al modello, con lo strumento collegato, il prompt di sistema più `messages`
  e accoda la risposta.
- `strumenti`: esegue ogni chiamata a strumento presente nell'ultima risposta, accoda i risultati
  come messaggi di tipo strumento e incrementa `passaggi_strumenti`.
- `limite_raggiunto`: rimuove dallo stato l'ultima risposta del modello, quella con chiamate
  a strumento rimaste senza risultato, e accoda una risposta fissa che spiega che il limite
  di passaggi è stato superato e che la domanda non ha avuto una risposta completa.
  La cronologia resta così valida per il turno successivo: ogni chiamata a strumento rimasta
  ha il suo risultato. *(Scelta mia.)*

Instradamento dopo `modello`, scritto come funzione con nome proprio:
- nessuna chiamata a strumento → `END`;
- chiamate presenti e `passaggi_strumenti < MAX_PASSAGGI_STRUMENTI` → `strumenti`;
- chiamate presenti e limite raggiunto → `limite_raggiunto` → `END`.

Dopo `strumenti` si torna sempre a `modello`.

Altre regole:
- Il contatore riparte da zero a ogni domanda dell'utente.
  `MAX_PASSAGGI_STRUMENTI` vale 3 per impostazione predefinita.
- Come seconda protezione si imposta anche il `recursion_limit` di LangGraph a un valore coerente.
- Se il modello chiede uno strumento sconosciuto, il nodo `strumenti` restituisce un messaggio
  d'errore come risultato e non solleva eccezioni.
- Nodi e instradamento sono scritti a mano, senza `create_react_agent`, `ToolNode` o
  `tools_condition`, perché si vedano nel codice.
- Il grafo può esporre la propria struttura, per esempio in formato Mermaid, per la documentazione.
  È facoltativo.

### 4.4 Log
- Si usa il `logging` standard su stderr. Il livello viene da `LOG_LEVEL`, predefinito `INFO`.
- A livello `INFO` ogni chiamata a strumento produce una riga con nome e argomenti
  e una con il risultato. Anche il raggiungimento del limite produce una riga.
- A livello `DEBUG` si possono aggiungere i passaggi del grafo.
- Le risposte normali non si ripetono nei log, perché appaiono già nel terminale.

## 5. Configurazione

Variabili d'ambiente, documentate in `.env.example`:

| Variabile | Obbligatoria | Default | Note |
|---|---|---|---|
| `LMSTUDIO_BASE_URL` | sì | — | in locale `http://localhost:1234/v1`; in Docker `http://host.docker.internal:1234/v1` |
| `LMSTUDIO_MODEL` | sì | — | `google/gemma-4-e2b`, come restituito da `GET /v1/models`; resta comunque configurabile |
| `FUSO_ORARIO_PREDEFINITO` | no | `Europe/Rome` | validato all'avvio |
| `MAX_PASSAGGI_STRUMENTI` | no | `3` | intero ≥ 1 |
| `LOG_LEVEL` | no | `INFO` | |

LM Studio non richiede chiavi. Il client OpenAI però ne vuole una, quindi si passa un valore
segnaposto fisso nel codice, che non è una credenziale. Il `.env.example` contiene i valori per
l'esecuzione locale, con un commento che spiega quali cambiare per Docker.

## 6. Docker
- Un `Dockerfile` basato su un'immagine Python slim, per esempio `python:3.12-slim`
  (versione da fissare nel piano), con le dipendenze installate dai requisiti fissati.
- `docker-compose.yml` con un solo servizio, `assistente`:
  - `env_file: .env`;
  - `stdin_open: true` e `tty: true`, perché l'applicazione è interattiva;
  - `extra_hosts: ["host.docker.internal:host-gateway"]`, così l'host è raggiungibile anche su Linux;
  - `LMSTUDIO_BASE_URL` sovrascritto verso `host.docker.internal`.
- Comando documentato per la sessione: `docker compose run --rm assistente`.
- I test devono poter girare anche nel container.
- Sull'host, LM Studio deve servire su un'interfaccia raggiungibile dal container.
  Il README spiega come verificarlo, per esempio l'opzione di LM Studio per la rete locale.

## 7. Test e verifiche

**Test automatici (pytest), senza modello**: girano con un modello finto che restituisce
risposte preparate, comprese risposte con chiamate a strumenti. Coprono:
- strumento: istante fisso → testo atteso in più fusi, ora legale e ora solare comprese;
  fuso non valido → messaggio d'errore;
- instradamento: senza chiamate → fine; con chiamate → `strumenti`; al limite → `limite_raggiunto`;
- grafo completo: domanda → chiamata allo strumento → esecuzione reale con orologio fisso
  → risposta finale. Si verifica che il risultato dello strumento arrivi al modello
  nel secondo invio;
- limite: un modello che chiede sempre lo strumento si ferma dopo `MAX_PASSAGGI_STRUMENTI` giri;
- cronologia: due turni consecutivi, e il secondo invio al modello contiene i messaggi del primo;
- log: la chiamata allo strumento compare nei log (`caplog`);
- configurazione: variabile obbligatoria mancante → errore chiaro; fuso predefinito non valido → errore.

**Prove reali, separate e attivate esplicitamente**
- Un test marcato (per esempio `lmstudio`) escluso dall'esecuzione predefinita e attivato
  con un'opzione esplicita. Interroga il LM Studio configurato con una domanda sull'ora e verifica
  che il modello abbia chiesto davvero `ora_corrente`.
- Il README contiene una checklist manuale per la sessione reale, in locale e in Docker:
  domanda sull'ora senza luogo, domanda con un luogo, domanda di seguito che usa la cronologia,
  fuso inesistente, LM Studio spento.

**Modello obbligato e rischio noto**: il modello da usare è `google/gemma-4-e2b` (decisione
dell'utente). Non si propongono né si scaricano altri modelli. Non è dimostrato che questo modello
gestisca bene il tool calling tramite LM Studio: solo la prova reale lo dirà.

Si può migliorare l'uso dello strumento con interventi che restano nei confini concordati e non
cambiano il modello, per esempio la chiarezza del prompt di sistema e della descrizione dello strumento.
Se la prova reale continua a fallire, il resoconto riporta il fallimento così com'è, con i log,
e il primo criterio di successo risulta non soddisfatto.

## 8. Struttura indicativa

```
lezione_4/
  CLAUDE.md
  README.md
  .env.example
  .gitignore            # .env, .venv/, __pycache__/, .pytest_cache/, ...
  .dockerignore
  Dockerfile
  docker-compose.yml
  requirements.txt      # dipendenze di esecuzione, versioni fissate
  requirements-dev.txt  # pytest
  pyproject.toml        # solo configurazione di pytest (marker, percorsi), se serve
  src/assistente/
    __main__.py         # python -m assistente
    config.py           # lettura e validazione delle variabili d'ambiente
    modello.py          # costruzione del client verso LM Studio
    strumenti.py        # ora_corrente e registro degli strumenti
    grafo.py            # stato, nodi, instradamento, compilazione
    cli.py              # ciclo di lettura e risposta, cronologia di sessione
  tests/
  docs/superpowers/specs/ e plans/
```

## 9. Decisioni prese da me (da verificare)
1. **Dipendenze**:
   - `langgraph` per il grafo;
   - `langchain-openai` per parlare con l'API di LM Studio compatibile con OpenAI
     e collegare lo strumento al modello;
   - `tzdata`, perché i fusi IANA funzionino anche su Windows e nell'immagine slim;
   - `pytest` solo per lo sviluppo.

   Le versioni esatte si fissano nel piano, dopo averle controllate.
2. **Cronologia** tenuta dall'interfaccia da terminale come lista di messaggi passata al grafo
   a ogni turno. Non si usa un checkpointer: è il meccanismo più semplice da leggere e non
   anticipa la persistenza.
3. **Limite**: 3 giri di strumenti per domanda, configurabile.
4. **Fuso predefinito** `Europe/Rome`, comunicato al modello nel prompt di sistema.
5. **Python 3.12** nel container. In locale si sviluppa e si verifica con `py` (3.14.10),
   non con `python` 3.10, che è a fine vita. Le versioni fissate devono installarsi sia su
   3.12 sia su 3.14; il piano lo controlla prima di fissarle. Se una dipendenza non
   funziona su 3.14, il piano lo segnala e si sceglie con l'utente.
6. Prompt di sistema e messaggi all'utente in italiano.

## 10. Lasciato a chi implementa
- I nomi interni oltre a quelli indicati, il testo esatto del prompt di sistema e dei messaggi.
- Come costruire il modello finto per i test.
- Il formato esatto delle righe di log, purché contengano nome, argomenti e risultato.
- Il valore preciso del `recursion_limit`, purché sia coerente con il limite di passaggi.
