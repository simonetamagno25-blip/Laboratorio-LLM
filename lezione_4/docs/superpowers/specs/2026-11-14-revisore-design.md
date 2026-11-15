# Step 2 · Revisore: la risposta è coerente con la domanda? — specifica

Data: 2026-11-14 · Branch: `feat/agente-web` · Fonte: `LLM_Lez_6.pdf`, step 2 (Intermedio).
Parte dallo step 1 (router) funzionante.

## Intento
Dopo la risposta finale dell'agente, un secondo uso dello stesso modello (prompt di sistema diverso)
verifica che la risposta risponda davvero alla domanda dell'utente: tutte le parti richieste,
nessuna deviazione dal tema. Una risposta incompleta o fuori tema torna all'agente con il motivo,
finché non è coerente o si raggiunge il limite di revisioni.

## Obiettivi
- Nodo `revisore` che riceve la domanda dell'utente e la risposta proposta dall'agente.
- Output strutturato: `coerente` (booleano) e `motivo`.
- Se non coerente, il motivo entra nella cronologia come indicazione per l'agente e si torna
  all'agente.
- Limite di revisioni nello stato: al limite si restituisce l'ultima risposta e lo si segnala nei log.

## Non obiettivi
- Verificare la correttezza dei fatti o dei risultati degli strumenti: il revisore giudica solo la
  coerenza tra domanda e risposta.
- Rivedere il rifiuto del router o il messaggio di limite degli strumenti (testi fissi).
- Streaming, persistenza, interfaccia: step successivi.

## Anti-obiettivi
- Una risposta coerente che gira all'infinito o che viene rifiutata per un guasto di formato del
  revisore.
- Indicazioni del revisore scambiate per domande dell'utente dal router nei turni successivi.
- Un turno che non termina: il limite di ricorsione deve coprire le revisioni.

## Decisioni (prese da chi implementa, su indicazione dell'utente di procedere senza fermarsi)
| Tema | Decisione | Motivo |
|---|---|---|
| Limite | `MAX_REVISIONI` nel `.env`, intero ≥ 1, default `2` | Configurabile come `MAX_PASSAGGI_STRUMENTI`; 2 dà una seconda possibilità senza raddoppiare troppo la latenza |
| Output non valido del revisore | fail-open: la risposta è approvata, con un `WARNING` | Coerente con il router: un guasto di formato non deve bloccare una risposta |
| Indicazione nella cronologia | `HumanMessage` con `name="revisore"` e testo «Indicazione del revisore: …» | Gemma via LM Studio accetta i messaggi di sistema solo all'inizio; il nome distingue l'indicazione dalle domande vere |
| Contesto del revisore | ultimi turni (come il router) + domanda + risposta proposta | Le domande brevi di seguito («e a New York?») si capiscono solo con il contesto |
| Bozze rifiutate | restano nella cronologia; il router le esclude dal testo da classificare | Il PDF chiede che il motivo entri nella cronologia; l'utente vede solo la risposta finale |
| Revisore facoltativo nel grafo | parametro `revisore=None`; senza, `agente → END` come prima | I test esistenti restano validi |

## Approcci considerati
1. **Revisore come nodo dopo l'agente, con ritorno all'agente (scelto).** È il grafo del PDF.
2. Revisore dentro il nodo agente (seconda chiamata nello stesso nodo): meno nodi ma il flusso non
   è più riconoscibile nel grafo e i log non separano i due ruoli. Scartato.
3. Indicazione come `SystemMessage` a metà cronologia: più pulita sul piano semantico, ma il
   template di Gemma la rifiuta o la sposta. Scartato.

## Progetto

### Configurazione (`assistente/config.py`)
- Nuovo campo `max_revisioni: int` (ultimo del dataclass), da `MAX_REVISIONI`, default `2`;
  intero ≥ 1, altrimenti `ErroreConfigurazione` → codice di uscita 2.

### Revisore (`assistente/revisore.py`, modulo nuovo)
- `DecisioneRevisore(BaseModel)`: `coerente: bool`, `motivo: str`.
- `prompt_revisore() -> str`: compito (giudicare se la risposta risponde a tutte le parti della
  domanda e resta in tema, senza riscriverla), criteri (risposta che dice di non sapere o che
  spiega un errore di uno strumento = coerente se pertinente), motivo in una frase.
- `testo_da_revisionare(messaggi) -> str`: turni precedenti (stessa regola del router, senza
  strumenti e senza indicazioni del revisore), la domanda corrente e la risposta proposta (ultimo
  `AIMessage` senza tool call).
- `indicazione(motivo) -> HumanMessage`: `name="revisore"`, testo «Indicazione del revisore: la
  risposta precedente non risponde del tutto alla domanda (<motivo>). Rispondi di nuovo alla domanda
  dell'utente tenendone conto.»
- `e_indicazione(messaggio) -> bool`.

### Router (`assistente/router.py`)
- `testo_da_classificare` ignora le indicazioni del revisore e le bozze che le precedono: la domanda
  corrente è l'ultimo `HumanMessage` che non è un'indicazione.

### Modello (`assistente/modello.py`)
- `crea_revisore(config)`: come `crea_router`, con `DecisioneRevisore` (stesso involucro che rende
  fail-open gli errori di formato). Helper comune `_strutturato(config, schema)`.

### Grafo (`assistente/grafo.py`)
- Nuovo campo di stato `revisioni: int` (rifiuti del revisore nel turno; letto con default 0).
- Nuovi parametri keyword di `costruisci_grafo`: `revisore=None`, `max_revisioni=2`.
- Con il revisore, `instrada_dopo_modello` manda la risposta finale a `revisore` invece che a `END`.
- `nodo_revisore`:
  - coerente → `INFO revisore: coerente=sì motivo=<m> -> fine`, fine del turno;
  - non coerente e `revisioni < max_revisioni` → aggiunge l'indicazione, `revisioni + 1`,
    `INFO revisore: coerente=no motivo=<m> -> agente (revisione <n> di <max>)`, torna ad `agente`;
  - non coerente e limite raggiunto → `WARNING revisore: limite di <max> revisioni raggiunto, si
    restituisce l'ultima risposta`, fine del turno con l'ultima risposta;
  - output non valido → `WARNING revisore: output non valido (<errore>), la risposta è approvata`.
- `limite_ricorsione(max_passaggi, max_revisioni=0)` = `3 * max_passaggi + 2 * (max_revisioni + 1) + 6`.

### CLI e avvio
- `Sessione` passa `revisioni: 0` a ogni domanda; mostra solo l'ultima risposta (come oggi).
- `__main__` passa `revisore=crea_revisore(config)` e `max_revisioni=config.max_revisioni`.

## Evidenze

### Test automatici (senza LM Studio)
- Risposta coerente: revisore finto `coerente=True` → una sola chiamata all'agente e al revisore.
- Risposta parziale: revisore finto no → sì; l'indicazione con il motivo è nella cronologia prima
  della seconda chiamata all'agente; risposta finale = seconda risposta.
- Limite: revisore finto che rifiuta sempre → esattamente `max_revisioni + 1` revisioni, risposta
  finale = ultima risposta, `WARNING` del limite.
- Fail-open: output non valido → risposta approvata con `WARNING`.
- Rifiuto del router e limite degli strumenti: il revisore non viene chiamato.
- Router nel turno successivo: indicazione e bozza non compaiono nel testo da classificare.
- Conferma delle note con il revisore: la ripresa passa dal revisore una sola volta.
- Limite di ricorsione: caso peggiore (strumenti, conferma, revisioni al massimo) senza
  `GraphRecursionError`.
- Configurazione `MAX_REVISIONI` (default, valori non validi).

### Prove reali con LM Studio (`--lmstudio`, separate)
- Risposta coerente approvata al primo passaggio: «Che ore sono a Tokyo?».
- Revisore reale su risposta parziale: domanda in due parti, prima risposta dell'agente forzata
  parziale (involucro di prova sul modello reale), il revisore reale la rifiuta con un motivo e
  l'agente reale produce la risposta completa.
- Prova manuale dalla CLI con `LOG_LEVEL=INFO` su una domanda in due parti.

## Lasciato a chi implementa
Formulazione esatta del prompt del revisore, nomi degli helper di test.
