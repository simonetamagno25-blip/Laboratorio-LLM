# Step 3 · Riassunto della cronologia — specifica

Data: 2026-11-14 · Branch: `feat/agente-web` · Fonte: PDF delle esercitazioni, step 3 (Avanzato).
Parte dagli step 1 (router) e 2 (revisore) funzionanti.

## Intento
Con un modello locale il contesto è limitato e ogni turno aggiunge messaggi. All'inizio del turno un
nodo LLM sostituisce i messaggi più vecchi con un riassunto e mantiene intatti gli ultimi turni, così
la conversazione resta utilizzabile su molti turni senza perdere le informazioni importanti.

## Obiettivi
- Soglia configurabile, in numero di messaggi, oltre la quale si riassume.
- Nodo `riassunto` all'inizio del turno: comprime i messaggi vecchi e conserva gli ultimi N.
- Il riassunto è un campo dello stato (`riassunto`) che viene aggiornato, non accumulato.
- Il taglio non separa mai una richiesta di tool dal relativo `ToolMessage`.

## Non obiettivi
- Persistenza del riassunto tra sessioni: la cronologia resta in memoria.
- Stima dei token: si usa il numero di messaggi (vedi Decisioni).

## Anti-obiettivi
- Una chiamata al modello sotto la soglia.
- Un taglio che lascia un `ToolMessage` senza la sua richiesta, o una richiesta senza risposta.
- Un riassunto che cresce a ogni compressione aggiungendo testo invece di essere riscritto.
- Un turno bloccato perché il riassunto è fallito.

## Decisioni (prese da chi implementa, su indicazione dell'utente di procedere senza fermarsi)
| Tema | Decisione | Motivo |
|---|---|---|
| Misura della soglia | numero di messaggi: `SOGLIA_RIASSUNTO` (default `20`) | Deterministica e testabile; la stima dei token dipende dal tokenizer del modello |
| Messaggi conservati | `MESSAGGI_CONSERVATI` (default `6`), intero ≥ 1 e minore della soglia | Il PDF chiede di conservare gli ultimi N |
| Punto di taglio | l'inizio di turno (domanda vera dell'utente) più recente che conserva almeno N messaggi | Un turno contiene sempre richiesta e risposta degli strumenti: tagliare tra turni non le separa mai, e nemmeno bozze e indicazioni del revisore |
| Dove va il riassunto | in coda al prompt di sistema dell'agente | Gemma accetta un solo messaggio di sistema, all'inizio |
| Riassunto fallito | `WARNING` e nessuna compressione; il turno prosegue | Il riassunto è un'ottimizzazione: non deve bloccare la domanda |
| Domande sulla conversazione («Come mi chiamo?») | `AMBITO_AGENTE` di esempio include «presentazioni e domande sulla conversazione in corso» | Senza, il router le rifiuterebbe e l'evidenza del nome non sarebbe raggiungibile |
| Cronologia nella CLI | `Sessione` conserva anche il riassunto e lo ripassa a ogni turno | Il grafo è senza stato tra i turni (thread nuovo per ogni domanda) |

## Approcci considerati
1. **Nodo `riassunto` prima del router, con `RemoveMessage` e campo `riassunto` (scelto).**
2. Riassunto fatto dalla CLI fuori dal grafo: il flusso non sarebbe più riconoscibile nel grafo.
   Scartato.
3. Riassunto inserito come messaggio nella cronologia: si accumula e si confonde con i turni.
   Scartato: il PDF chiede un campo dello stato.

## Progetto

### Configurazione
- `soglia_riassunto: int = 20` da `SOGLIA_RIASSUNTO`; `messaggi_conservati: int = 6` da
  `MESSAGGI_CONSERVATI`; interi ≥ 1, `messaggi_conservati < soglia_riassunto`, altrimenti
  `ErroreConfigurazione`.

### Riassunto (`assistente/riassunto.py`, modulo nuovo)
- `punto_di_taglio(messaggi, conservati) -> int`: indice della domanda vera più recente tale che
  restino almeno `conservati` messaggi; `0` se non si può tagliare.
- `prompt_riassunto() -> str`: riscrivere un unico riassunto in italiano che unisce il riassunto
  precedente e i nuovi messaggi, conservando nomi, preferenze, fatti dichiarati dall'utente,
  richieste e risultati importanti; niente invenzioni.
- `testo_da_riassumere(riassunto_precedente, messaggi) -> str`: riassunto precedente (se c'è) e i
  messaggi come righe `Utente:`, `Assistente:`, `Strumento <nome>:`; senza bozze rifiutate e
  indicazioni del revisore, senza le richieste di strumento vuote.

### Grafo
- Stato: `riassunto: NotRequired[str]`.
- `costruisci_grafo(..., riassuntore=None, soglia_riassunto=20, messaggi_conservati=6)`.
- `nodo_riassunto`:
  - sotto o uguale alla soglia: nessuna chiamata, `DEBUG riassunto: <n> messaggi, soglia <s>: nessun riassunto`;
  - sopra la soglia: chiama il modello, restituisce `riassunto` nuovo e `RemoveMessage` per i
    messaggi tagliati; `INFO riassunto: <prima> messaggi prima, <dopo> dopo (<k> riassunti)`;
  - nessun punto di taglio: `INFO riassunto: <n> messaggi ma nessun turno da comprimere`;
  - errore del modello: `WARNING riassunto: non riuscito (<errore>), cronologia invariata`.
- `START → riassunto → router` (o `agente` senza router).
- `nodo_agente` aggiunge il riassunto in coda al prompt di sistema.
- `limite_ricorsione` aggiunge un passo.

### CLI e avvio
- `Sessione.riassunto` (stringa) passato e aggiornato a ogni turno.
- `__main__` passa `riassuntore=crea_riassuntore(config)` (il modello senza strumenti) e i due valori.

## Evidenze

### Test automatici (senza LM Studio)
- Sotto la soglia il riassuntore finto non viene chiamato.
- Sopra la soglia: messaggi prima/dopo nei log, cronologia ridotta, riassunto nello stato e nel
  prompt di sistema dell'agente.
- Il riassunto successivo riceve il riassunto precedente e lo sostituisce.
- Il taglio non separa mai una tool call dal `ToolMessage` (anche con un turno lungo pieno di strumenti).
- Errore del riassuntore: cronologia invariata e turno completato.
- Sessione: il riassunto passa da un turno all'altro.
- Configurazione delle due variabili.

### Prove reali con LM Studio
- «Mi chiamo Giulia» al primo turno, poi altri turni fino a superare una soglia bassa, poi «Come mi
  chiamo?»: la risposta contiene «Giulia» e i log mostrano la compressione.
