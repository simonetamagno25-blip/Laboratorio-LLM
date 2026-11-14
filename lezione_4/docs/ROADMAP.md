# Roadmap — Esercitazioni della lezione 6: evolvere l'agente

Fonte di verità: `LLM_Lez_6.pdf` («Esercitazioni di laboratorio: evolvere l'agente»).
Uno step alla volta, nell'ordine; ogni step parte dal precedente funzionante, verificato
con le evidenze richieste e registrato con un commit.

Per ogni step: specifica e piano approvati → test automatici (modello simulato) →
prova reale con LM Studio → README aggiornato → commit.

Punto di partenza: agente delle lezioni 4 e 5 (grafo `modello` ⇄ `strumenti`, conferma
dell'eliminazione delle note, server MCP `convertitore_mcp` via stdio, servizio HTTP
`scadenze_api`), 305 test automatici verdi.

## Step 1 · Router: conversazione o fuori ambito (Base)
- [ ] Specifica e piano approvati
- [ ] Ambito dell'agente in configurazione, non nel codice
- [ ] Nodo router con output strutturato: `categoria` (conversazione / fuori ambito) e `motivo`
- [ ] Arco condizionale: conversazione → agente; fuori ambito → rifiuto → fine
- [ ] Il router non valuta gli strumenti
- Evidenze
  - [ ] Domanda in ambito: log con categoria, motivo e passaggio all'agente
  - [ ] Domanda fuori ambito: rifiuto, nessuna esecuzione del nodo agente nei log
  - [ ] Test con risposte del router simulate per entrambi i percorsi
- [ ] Prova reale con LM Studio · [ ] README · [ ] Commit
- **Evidenza minima:** domanda fuori ambito rifiutata senza passare dall'agente

## Step 2 · Revisore: la risposta è coerente con la domanda? (Intermedio)
- [ ] Specifica e piano approvati
- [ ] Nodo revisore con domanda dell'utente e risposta proposta
- [ ] Output strutturato: `coerente` (sì/no) e `motivo`
- [ ] Se non coerente, il motivo entra nella cronologia come indicazione per l'agente
- [ ] Limite di revisioni nello stato; al limite si restituisce l'ultima risposta, segnalato nei log
- Evidenze
  - [ ] Domanda in due parti con risposta parziale: rifiuto motivato e nuova risposta completa
  - [ ] Risposta coerente approvata al primo passaggio
  - [ ] Limite rispettato con un revisore simulato che rifiuta sempre
- [ ] Prova reale con LM Studio · [ ] README · [ ] Commit
- **Evidenza minima:** risposta incompleta corretta dopo la revisione, entro il limite

## Step 3 · Riassunto della cronologia (Avanzato)
- [ ] Specifica e piano approvati
- [ ] Soglia configurabile (numero di messaggi o stima dei token)
- [ ] Nodo riassunto all'inizio del turno: comprime i vecchi, conserva gli ultimi N
- [ ] Il riassunto è un campo dello stato aggiornato, non accumulato
- [ ] Il taglio non separa mai una richiesta di tool dal relativo `ToolMessage`
- Evidenze
  - [ ] Log con numero di messaggi prima e dopo il riassunto
  - [ ] Informazione del primo turno (es. nome dell'utente) usata dopo la compressione
  - [ ] Sotto la soglia il nodo non chiama il modello
- [ ] Prova reale con LM Studio · [ ] README · [ ] Commit
- **Evidenza minima:** informazione del primo turno ancora usata dopo la compressione

## Step 4 · Resource: preferenze dell'utente
- [ ] Specifica e piano approvati
- [ ] Resource `utente://preferenze`: lingua, fuso orario predefinito, stile (sintetico/dettagliato)
- [ ] Letta dall'host a inizio sessione e messa in cima al prompt di sistema
- [ ] La resource non compare tra i tool di `bind_tools`
- [ ] Resource non disponibile: valori predefiniti, segnalati nei log
- Evidenze
  - [ ] «Che ore sono?» usa il fuso predefinito senza chiederlo (prova con America/New_York)
  - [ ] Cambiando lingua o stile nel file, la sessione successiva risponde di conseguenza
  - [ ] Lettura della resource nei log, separata dalle chiamate ai tool
- [ ] Prova reale con LM Studio · [ ] README · [ ] Commit
- **Evidenza minima:** preferenze applicate; modifica del file senza modifica del codice

## Step 5 · Prompt: comandi riusabili nella CLI
- [ ] Specifica e piano approvati
- [ ] Prompt `spiega(argomento, livello)` e `riassumi_conversazione(stile)`
- [ ] Comando `/prompts` con nome, descrizione e argomenti
- [ ] Comando `/prompt nome argomento=valore`: messaggi aggiunti alla cronologia e inviati al grafo
- [ ] Validazione rispetto a `prompts/list`: argomenti obbligatori mancanti o sconosciuti bloccano
      la richiesta senza chiamare il modello
- Evidenze
  - [ ] `/prompt spiega argomento="Model Context Protocol" livello=base`: risposta adeguata al livello
  - [ ] `riassumi_conversazione` riassume i turni della sessione corrente
  - [ ] Log con prompt richiamato, argomenti e messaggi ottenuti dal server
- [ ] Prova reale con LM Studio · [ ] README · [ ] Commit
- **Evidenza minima:** /prompts e /prompt funzionanti, con argomenti validati

## Step 6 · L'agente come servizio HTTP
- [ ] Specifica e piano approvati
- [ ] Modulo dell'agente separato dall'interfaccia; la CLI diventa client dell'API
- [ ] Endpoint: messaggio e cronologia → risposta e strumenti usati
- [ ] Endpoint di stato: agente, server MCP e modello raggiungibili
- [ ] Agente senza stato: cronologia e riassunto arrivano dal chiamante e tornano aggiornati
- Evidenze
  - [ ] Chiamata HTTP con una domanda che usa un tool: risposta e traccia nei log
  - [ ] Modello o strumenti non disponibili: codice e messaggio di errore comprensibili
  - [ ] Test dell'API con il grafo simulato; documentazione OpenAPI consultabile
- [ ] Prova reale con LM Studio · [ ] README · [ ] Commit
- **Evidenza minima:** stessa risposta dalla CLI e dall'API

## Step 7 · Back-end: API e salvataggio delle chat
- [ ] Specifica e piano approvati
- [ ] Creare una chat (restituisce l'identificativo)
- [ ] Elencare le chat (titolo e data dell'ultimo messaggio)
- [ ] Leggere una chat (messaggi in ordine cronologico)
- [ ] Inviare un messaggio (salva la domanda, chiama l'agente, salva e restituisce la risposta)
- [ ] Eliminare una chat (con i suoi messaggi)
- [ ] Salvataggio in PostgreSQL
- Evidenze
  - [ ] Documentazione OpenAPI generata e consultabile
  - [ ] Agente non raggiungibile: errore chiaro e comportamento documentato
  - [ ] Test con l'agente simulato; chat ancora presenti dopo il riavvio
- [ ] Prova reale con LM Studio · [ ] README · [ ] Commit
- **Evidenza minima:** chat persistenti dopo il riavvio; OpenAPI consultabile

## Step 8 · Front-end: interfaccia di chat
- [ ] Specifica e piano approvati
- [ ] Chiamate generate dal documento OpenAPI del back-end
- [ ] Elenco, creazione ed eliminazione delle chat
- [ ] Vista dei messaggi e invio di una nuova domanda
- [ ] Stato di attesa ed errori comprensibili
- [ ] Indirizzo del back-end da configurazione
- Evidenze
  - [ ] Conversazione completa dal browser, con uso di uno strumento
  - [ ] Chat creata dall'interfaccia ancora presente dopo il riavvio
  - [ ] Con l'agente spento l'interfaccia mostra l'errore senza bloccarsi
- [ ] Prova reale con LM Studio · [ ] README · [ ] Commit
- **Evidenza minima:** conversazione completa dal browser, errori mostrati

## Step 9 · Docker Compose: un container per componente
- [ ] Specifica e piano approvati
- [ ] Quattro servizi in `compose.yaml`: tre Dockerfile + PostgreSQL ufficiale
- [ ] Browser → front-end; API → back-end (porta o proxy); agente non esposto
- [ ] Volume per PostgreSQL; credenziali in `.env` fuori da Git; back-end a database pronto
- [ ] Agente → LM Studio con `host.docker.internal`; server MCP stdio nel suo container
- Evidenze
  - [ ] `docker compose up` avvia i quattro servizi; `docker compose ps` li mostra attivi
  - [ ] Chat dal browser con uno strumento, visibile nei log dell'agente
  - [ ] Dopo `down` e `up` le chat sono ancora presenti
- [ ] Prova reale con LM Studio · [ ] README · [ ] Commit
- **Evidenza minima:** quattro container avviati con un comando; agente non esposto

## Facoltativo · Streaming della risposta (dopo lo step 9, se manca)
- [ ] Agente: testo emesso man mano, con gli eventi degli strumenti
- [ ] Back-end: inoltro del flusso (es. Server-Sent Events), salvataggio del messaggio completo
- [ ] Front-end: testo mostrato mentre arriva, indicazione degli strumenti in uso
- [ ] Decisione documentata: con il revisore, bozza in diretta oppure solo risposta approvata
