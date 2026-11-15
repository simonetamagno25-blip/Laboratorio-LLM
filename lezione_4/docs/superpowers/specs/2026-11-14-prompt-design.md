# Step 5 · Prompt: comandi riusabili nella CLI — specifica

Data: 2026-11-14 · Branch: `feat/agente-web` · Fonte: `LLM_Lez_6.pdf`, step 5.
Parte dagli step 1–4 funzionanti.

## Intento
Il server MCP espone due prompt generici. La CLI li elenca e permette all'utente di richiamarli: un
prompt richiamato passa dal grafo come qualsiasi altra domanda (riassunto, router, agente, strumenti,
revisore). MCP non prevede un comando standard: i comandi li definisce la CLI.

## Obiettivi
- Prompt `spiega(argomento, livello)` e `riassumi_conversazione(stile)` nel server.
- Comando `/prompts`: nome, descrizione e argomenti di ogni prompt.
- Comando `/prompt nome argomento=valore …`: i messaggi ottenuti dal server si aggiungono alla
  cronologia e vanno al grafo.
- Controllo nell'host rispetto a `prompts/list`: argomenti obbligatori mancanti o sconosciuti bloccano
  la richiesta senza chiamare il modello.

## Decisioni (prese da chi implementa, su indicazione dell'utente di procedere senza fermarsi)
| Tema | Decisione | Motivo |
|---|---|---|
| Server | gli stessi `convertitore_mcp` (come per la resource) | Unico server MCP del progetto |
| Argomenti | `spiega`: `argomento` obbligatorio, `livello` facoltativo (`base` default; `base`/`intermedio`/`avanzato`). `riassumi_conversazione`: `stile` facoltativo (`sintetico` default; `sintetico`/`dettagliato`) | Il PDF mostra `livello="base"` come default |
| Valori fuori elenco | li rifiuta il server (errore spiegato nella CLI, nessuna chiamata al modello) | L'elenco dei valori non è nello schema di `prompts/list`: lo conosce solo il server |
| Sintassi | `/prompt nome chiave=valore`, valori con spazi tra virgolette (`shlex`) | È l'esempio del PDF: `argomento="Model Context Protocol"` |
| Elenco | `prompts/list` richiesto a ogni `/prompts` e `/prompt` | Il server è la fonte di verità; costo trascurabile |
| Messaggi | ruolo `user` → `HumanMessage`, `assistant` → `AIMessage`; solo contenuti di testo | Sono gli unici ruoli dei prompt MCP |

## Progetto

### Server (`convertitore_mcp/server.py`)
- `@server.prompt()` `spiega(argomento: str, livello: str = "base")` → testo dell'istruzione; livello
  fuori elenco → `ValueError`.
- `@server.prompt()` `riassumi_conversazione(stile: str = "sintetico")` → istruzione di riassumere i
  turni della conversazione corrente nello stile richiesto.

### Client (`assistente/client_mcp.py`)
- `elenca_prompt() -> list[InfoPrompt]` (`nome`, `descrizione`, `argomenti`: nome, descrizione,
  obbligatorio). Log `INFO prompts/list: <nomi>`.
- `ottieni_prompt(nome, argomenti) -> list[tuple[ruolo, testo]]`. Log
  `INFO prompts/get <nome> <argomenti>: <n> messaggi` e, a livello INFO, il testo di ogni messaggio.
  Errori → `ErroreMCP`.

### Comandi (`assistente/comandi.py`, modulo nuovo)
- `interpreta_comando_prompt(riga) -> (nome, argomenti)`; errori di sintassi → `ErroreComando`.
- `valida(nome, argomenti, elenco) -> None`: prompt sconosciuto, argomenti sconosciuti, obbligatori
  mancanti → `ErroreComando` con un messaggio comprensibile.
- `descrivi_prompt(elenco) -> str`: testo di `/prompts`.
- `in_messaggi(coppie) -> list[BaseMessage]`.

### CLI
- `Sessione.chiedi_messaggi(messaggi)`: come `chiedi`, ma con i messaggi del prompt.
- `esegui_ciclo(..., prompt=None)`: `/prompts` e `/prompt …` usano il client MCP; gli errori di
  comando o del server sono mostrati senza chiamare il modello. La conferma delle note funziona
  anche per i prompt (stesso ciclo).

## Evidenze

### Test automatici (senza LM Studio)
- Server reale via stdio: `prompts/list` con nomi, descrizioni e argomenti; `prompts/get` con i testi;
  livello fuori elenco → errore.
- Comandi: interpretazione con virgolette, argomenti sconosciuti, obbligatori mancanti, prompt
  sconosciuto, sintassi errata.
- CLI con grafo finto: `/prompts` stampa l'elenco; `/prompt` valido aggiunge i messaggi alla
  cronologia e chiama il grafo; `/prompt` non valido non chiama il modello.

### Prove reali con LM Studio
- `/prompt spiega argomento="Model Context Protocol" livello=base`: passa dal router e la risposta è
  di livello base (lettura a occhio, stampata).
- Dopo due domande, `/prompt riassumi_conversazione` riassume i turni della sessione.
- Log con prompt richiamato, argomenti e messaggi ottenuti dal server.
