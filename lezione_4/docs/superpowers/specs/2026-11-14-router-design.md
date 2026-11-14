# Step 1 · Router: conversazione o fuori ambito — specifica

Lezione 6, «Esercitazioni di laboratorio: evolvere l'agente» (`LLM_Lez_6.pdf`, pagina 4).
Branch: `feat/lezione-6`, creato da `feat/note`.

## Intento
L'agente ha un ambito dichiarato. Prima dell'agente un nodo LLM decide se la domanda rientra
nell'ambito: le domande fuori ambito ricevono un rifiuto **senza raggiungere l'agente**. Il router
non sceglie gli strumenti: se servono, li sceglie l'agente come prima.

## Obiettivi
- Ambito descritto in configurazione (variabile `AMBITO_AGENTE`), non nel codice.
- Nodo `router` con output strutturato: `categoria` (`conversazione` | `fuori_ambito`) e `motivo`.
- Arco condizionale: `conversazione` → `agente`; `fuori_ambito` → `rifiuto` → `END`.
- Evidenze verificabili nei log e nei test (vedi «Evidenze»).

## Non obiettivi
- Revisore, riassunto, resource, prompt (step 2–5): non anticiparli.
- Il router non vede l'elenco degli strumenti e non decide se usarli.
- Nessuna correzione del difetto aperto sulle note (handoff del 2026-11-09): è un lavoro separato.

## Anti-obiettivi
- Domande del laboratorio o del corso rifiutate in modo sistematico, oppure follow-up come
  «e a Tokyo?» rifiutati perché il router non vede il contesto.
- Il nodo agente che viene eseguito comunque per una domanda fuori ambito.
- Un guasto di formato del router che blocca domande valide.

## Decisioni prese con l'utente
| Tema | Decisione |
|---|---|
| Branch | nuovo `feat/lezione-6` creato da `feat/note` |
| Dove sta l'ambito | variabile `AMBITO_AGENTE` nel `.env`, **obbligatoria**: se manca, il programma esce con codice 2, come per le altre variabili obbligatorie |
| Ampiezza dell'ambito | strumenti del laboratorio (ora e date, calcoli e conversioni, giorni e scadenze, materiale del laboratorio, note personali), saluti e domande sull'assistente, **più** spiegazioni sui temi del corso (deep learning, LLM, agenti, MCP, LangGraph). Così lo step 5 (`spiega "Model Context Protocol"`) passa dal router senza cambiare l'ambito |
| Output del router non valido | **fail-open**: la domanda passa all'agente, con un `WARNING` nei log. Se LM Studio non è raggiungibile il turno fallisce, come oggi |

## Approcci considerati
1. **Nodo LLM con output strutturato `json_schema`** (scelto). Si usa
   `ChatOpenAI.with_structured_output(DecisioneRouter, method="json_schema", include_raw=True)`
   sullo stesso modello di LM Studio, senza `bind_tools`. LM Studio impone lo schema in fase di
   generazione, quindi anche un modello piccolo produce JSON valido. `include_raw=True` restituisce
   l'errore di parsing invece di sollevarlo, ed è quello che serve per il fail-open.
2. Output strutturato con tool calling (`method="function_calling"`). È una buona alternativa se
   `json_schema` non funzionasse con il modello caricato, ma il modello potrebbe rispondere in testo
   invece di chiamare lo strumento. Resta il piano B, da usare solo se la prova reale fallisce.
3. Classificazione con parole chiave o regole. Scartata: il PDF chiede un nodo LLM, e le regole non
   capiscono i follow-up.

## Progetto

### Configurazione (`assistente/config.py`)
- Nuovo campo `ambito: str` di `Configurazione`, letto con `_obbligatoria(env, "AMBITO_AGENTE")`.
- `.env.example` riceve una riga `AMBITO_AGENTE=...` con il testo concordato. Il testo è scritto
  come descrizione («ora e date nei vari fusi orari, calcoli, …»), perché serve sia al prompt del
  router sia al messaggio di rifiuto.
- In Docker passa con `env_file: .env`: `docker-compose.yml` non cambia.

### Router (`assistente/router.py`, modulo nuovo)
- `DecisioneRouter` (Pydantic) ha due campi: `categoria: Literal["conversazione", "fuori_ambito"]`
  e `motivo: str`.
- `prompt_router(ambito) -> str` è il prompt di sistema del router. Contiene:
  - il compito: classificare la domanda, senza rispondere;
  - l'ambito;
  - l'indicazione che saluti, ringraziamenti, domande sull'assistente e follow-up di argomenti
    in ambito dei turni precedenti sono `conversazione`, mentre il seguito di una domanda fuori
    ambito resta `fuori_ambito` (modifica dopo la revisione finale del branch);
  - nessun riferimento agli strumenti.
- `testo_da_classificare(messaggi) -> str` costruisce un solo testo con gli ultimi 3 turni
  precedenti (solo domande dell'utente e risposte finali dell'assistente, senza chiamate a
  strumenti e senza `ToolMessage`, ogni messaggio troncato a 300 caratteri) e la domanda corrente,
  cioè l'ultimo `HumanMessage`.
- `messaggio_rifiuto(ambito) -> str` restituisce una frase fissa seguita da «Posso aiutarti con:
  {ambito}».

### Modello (`assistente/modello.py`)
- `crea_router(config) -> Runnable` usa lo stesso `ChatOpenAI` (stessi parametri, `temperature=0`)
  con `.with_structured_output(DecisioneRouter, method="json_schema", include_raw=True)`.
- `crea_modello` resta invariato. La costruzione di `ChatOpenAI` va in un helper condiviso, così
  agente e router usano parametri identici.

### Grafo (`assistente/grafo.py`)
- Il nodo `modello` si chiama ora **`agente`**, così i log e il diagramma parlano la lingua del PDF.
  La funzione `instrada_dopo_modello` mantiene il suo nome.
- Nuovi parametri keyword di `costruisci_grafo`: `router: Runnable | None = None` e
  `ambito: str = ""`. Se `router` è presente servono `ambito` non vuoto (altrimenti `ValueError`) e
  il percorso `START → router`. Senza `router` il grafo resta `START → agente` come oggi, così i test
  esistenti non cambiano.
- Lo stato riceve `categoria: NotRequired[str]` e `motivo: NotRequired[str]`, scritti dal router.
- `nodo_router`:
  1. invoca il router con `[SystemMessage(prompt_router(ambito)), HumanMessage(testo_da_classificare(...))]`;
  2. se `parsed` è valido usa categoria e motivo; altrimenti scrive un `WARNING` con l'errore di
     parsing e prosegue con `categoria="conversazione"` e un motivo che segnala il fail-open;
  3. scrive `INFO router: categoria=<c> motivo=<m> -> <agente|rifiuto>`;
  4. non aggiunge messaggi alla cronologia.
- `instrada_dopo_router(stato)` restituisce `"agente"` per `conversazione` e `"rifiuto"` per
  `fuori_ambito`.
- `nodo_rifiuto`:
  - aggiunge `AIMessage(messaggio_rifiuto(ambito))` senza chiamare alcun modello;
  - scrive `INFO rifiuto: domanda fuori ambito, agente non eseguito`.
- `nodo_agente` scrive `INFO agente: chiamata al modello` a ogni esecuzione: è la riga che deve
  mancare nei log per le domande fuori ambito.
- `limite_ricorsione` aumenta di 2 (router e rifiuto) e il commento va aggiornato.
- Interrupt della conferma: la ripresa con `Command(resume=...)` riparte dal nodo fermo, quindi il
  router non viene rieseguito e il flusso delle note non cambia.

### Avvio (`assistente/__main__.py`)
- Costruisce `crea_router(config)` e lo passa a `costruisci_grafo(..., router=..., ambito=config.ambito)`.

### Cronologia
- Una domanda rifiutata resta nella cronologia della sessione, insieme al messaggio di rifiuto.
  È così che il turno si chiude come gli altri.

## Evidenze
| Evidenza del PDF | Dove si verifica |
|---|---|
| Domanda in ambito: log con categoria, motivo e passaggio all'agente | test simulato con `caplog` (riga `router: ... -> agente` seguita da `agente: chiamata al modello`) e log reale della CLI con `LOG_LEVEL=INFO` |
| Domanda fuori ambito: rifiuto, nessuna esecuzione del nodo agente | test simulato: modello dell'agente con 0 chiamate e nessuna riga `agente:` nei log; prova reale: stessa verifica sui messaggi e sui log |
| Test con risposte del router simulate per entrambi i percorsi | `tests/test_router.py` e i nuovi casi in `tests/test_grafo.py` con un `RouterFinto` |

### Test automatici (senza LM Studio)
- Configurazione: `AMBITO_AGENTE` obbligatoria (mancante o vuota → errore).
- `testo_da_classificare`: ultimi 3 turni, esclusione di chiamate a strumenti e `ToolMessage`,
  troncamento, domanda corrente in fondo.
- Percorso in ambito: router finto → `conversazione` → agente eseguito → risposta dell'agente.
- Percorso fuori ambito: router finto → `fuori_ambito` → messaggio di rifiuto, agente mai chiamato.
- Fail-open: router finto con `parsed=None` → agente eseguito e `WARNING` nei log.
- Log di entrambi i percorsi.
- Domanda in ambito che usa uno strumento: il ciclo agente ⇄ strumenti funziona dietro al router.
- Conferma dell'eliminazione delle note con il router davanti: pausa e ripresa senza rieseguire il
  router.
- `costruisci_grafo` con `router` e `ambito` vuoto → `ValueError`.

### Prove reali con LM Studio (`--lmstudio`, separate)
- In ambito con strumento: «Che ore sono adesso a Tokyo?» → `conversazione`, chiamata a
  `ora_corrente`.
- Fuori ambito: «Dammi la ricetta della carbonara» → `fuori_ambito`, nessuna esecuzione dell'agente.
- Tema del corso: «Che cos'è LangGraph?» → `conversazione`.
- Follow-up: «Che ore sono a Tokyo?» poi «e a New York?» → il secondo turno è `conversazione`.
- Seguito fuori ambito: «Dammi la ricetta della carbonara» poi «e quella dell'amatriciana?» → il
  secondo turno è `fuori_ambito`.
- Prova manuale dalla CLI con `LOG_LEVEL=INFO`: una domanda in ambito e una fuori ambito, con i log
  da mostrare come evidenza.
- Le prove reali esistenti (23–29 minuti) passeranno dal router tramite `grafo_completo`. Le rilancio
  tutte solo su richiesta; di default eseguo solo le nuove.

## Lasciato a chi implementa
- Formulazione esatta del prompt del router e della frase di rifiuto, entro i vincoli sopra.
- Se `json_schema` non funziona con il modello caricato, passare a `function_calling` e segnalarlo
  nel resoconto.
