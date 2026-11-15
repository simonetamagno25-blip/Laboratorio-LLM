# Roadmap — Esercitazioni della lezione 6: evolvere l'agente

Fonte di verità: `LLM_Lez_6.pdf` («Esercitazioni di laboratorio: evolvere l'agente»).
Uno step alla volta, nell'ordine; ogni step parte dal precedente funzionante, verificato
con le evidenze richieste e registrato con un commit.

Per ogni step: specifica e piano approvati → test automatici (modello simulato) →
prova reale con LM Studio → README aggiornato → commit.

Stato: step 1–9 completati il 2026-11-15 (dettagli e verifiche in `docs/superpowers/handoff-2026-11-15-lezione-6.md`).

Punto di partenza: agente delle lezioni 4 e 5 (grafo `modello` ⇄ `strumenti`, conferma
dell'eliminazione delle note, server MCP `convertitore_mcp` via stdio, servizio HTTP
`scadenze_api`), 305 test automatici verdi.

## Step 1 · Router: conversazione o fuori ambito (Base)
- [x] Specifica e piano approvati
- [x] Ambito dell'agente in configurazione, non nel codice
- [x] Nodo router con output strutturato: `categoria` (conversazione / fuori ambito) e `motivo`
- [x] Arco condizionale: conversazione → agente; fuori ambito → rifiuto → fine
- [x] Il router non valuta gli strumenti
- Evidenze
  - [x] Domanda in ambito: log con categoria, motivo e passaggio all'agente
  - [x] Domanda fuori ambito: rifiuto, nessuna esecuzione del nodo agente nei log
  - [x] Test con risposte del router simulate per entrambi i percorsi
- [x] Prova reale con LM Studio · [x] README · [x] Commit
- **Evidenza minima:** domanda fuori ambito rifiutata senza passare dall'agente

## Step 2 · Revisore: la risposta è coerente con la domanda? (Intermedio)
- [x] Specifica e piano approvati
- [x] Nodo revisore con domanda dell'utente e risposta proposta
- [x] Output strutturato: `coerente` (sì/no) e `motivo`
- [x] Se non coerente, il motivo entra nella cronologia come indicazione per l'agente
- [x] Limite di revisioni nello stato; al limite si restituisce l'ultima risposta, segnalato nei log
- Evidenze
  - [x] Domanda in due parti con risposta parziale: rifiuto motivato e nuova risposta completa
  - [x] Risposta coerente approvata al primo passaggio
  - [x] Limite rispettato con un revisore simulato che rifiuta sempre
- [x] Prova reale con LM Studio · [x] README · [x] Commit
- **Evidenza minima:** risposta incompleta corretta dopo la revisione, entro il limite

## Step 3 · Riassunto della cronologia (Avanzato)
- [x] Specifica e piano approvati
- [x] Soglia configurabile (numero di messaggi o stima dei token)
- [x] Nodo riassunto all'inizio del turno: comprime i vecchi, conserva gli ultimi N
- [x] Il riassunto è un campo dello stato aggiornato, non accumulato
- [x] Il taglio non separa mai una richiesta di tool dal relativo `ToolMessage`
- Evidenze
  - [x] Log con numero di messaggi prima e dopo il riassunto
  - [x] Informazione del primo turno (es. nome dell'utente) usata dopo la compressione
  - [x] Sotto la soglia il nodo non chiama il modello
- [x] Prova reale con LM Studio · [x] README · [x] Commit
- **Evidenza minima:** informazione del primo turno ancora usata dopo la compressione

## Step 4 · Resource: preferenze dell'utente
- [x] Specifica e piano approvati
- [x] Resource `utente://preferenze`: lingua, fuso orario predefinito, stile (sintetico/dettagliato)
- [x] Letta dall'host a inizio sessione e messa in cima al prompt di sistema
- [x] La resource non compare tra i tool di `bind_tools`
- [x] Resource non disponibile: valori predefiniti, segnalati nei log
- Evidenze
  - [x] «Che ore sono?» usa il fuso predefinito senza chiederlo (prova con America/New_York)
  - [x] Cambiando lingua o stile nel file, la sessione successiva risponde di conseguenza
  - [x] Lettura della resource nei log, separata dalle chiamate ai tool
- [x] Prova reale con LM Studio · [x] README · [x] Commit
- **Evidenza minima:** preferenze applicate; modifica del file senza modifica del codice

## Step 5 · Prompt: comandi riusabili nella CLI
- [x] Specifica e piano approvati
- [x] Prompt `spiega(argomento, livello)` e `riassumi_conversazione(stile)`
- [x] Comando `/prompts` con nome, descrizione e argomenti
- [x] Comando `/prompt nome argomento=valore`: messaggi aggiunti alla cronologia e inviati al grafo
- [x] Validazione rispetto a `prompts/list`: argomenti obbligatori mancanti o sconosciuti bloccano
      la richiesta senza chiamare il modello
- Evidenze
  - [x] `/prompt spiega argomento="Model Context Protocol" livello=base`: risposta adeguata al livello
  - [x] `riassumi_conversazione` riassume i turni della sessione corrente
  - [x] Log con prompt richiamato, argomenti e messaggi ottenuti dal server
- [x] Prova reale con LM Studio · [x] README · [x] Commit
- **Evidenza minima:** /prompts e /prompt funzionanti, con argomenti validati

## Step 6 · L'agente come servizio HTTP
- [x] Specifica e piano approvati
- [x] Modulo dell'agente separato dall'interfaccia; la CLI diventa client dell'API
- [x] Endpoint: messaggio e cronologia → risposta e strumenti usati
- [x] Endpoint di stato: agente, server MCP e modello raggiungibili
- [x] Agente senza stato: cronologia e riassunto arrivano dal chiamante e tornano aggiornati
- Evidenze
  - [x] Chiamata HTTP con una domanda che usa un tool: risposta e traccia nei log
  - [x] Modello o strumenti non disponibili: codice e messaggio di errore comprensibili
  - [x] Test dell'API con il grafo simulato; documentazione OpenAPI consultabile
- [x] Prova reale con LM Studio · [x] README · [x] Commit
- **Evidenza minima:** stessa risposta dalla CLI e dall'API

## Step 7 · Back-end: API e salvataggio delle chat
- [x] Specifica e piano approvati
- [x] Creare una chat (restituisce l'identificativo)
- [x] Elencare le chat (titolo e data dell'ultimo messaggio)
- [x] Leggere una chat (messaggi in ordine cronologico)
- [x] Inviare un messaggio (salva la domanda, chiama l'agente, salva e restituisce la risposta)
- [x] Eliminare una chat (con i suoi messaggi)
- [x] Salvataggio in PostgreSQL
- Evidenze
  - [x] Documentazione OpenAPI generata e consultabile
  - [x] Agente non raggiungibile: errore chiaro e comportamento documentato
  - [x] Test con l'agente simulato; chat ancora presenti dopo il riavvio
- [x] Prova reale con LM Studio · [x] README · [x] Commit
- **Evidenza minima:** chat persistenti dopo il riavvio; OpenAPI consultabile

## Step 8 · Front-end: interfaccia di chat
- [x] Specifica e piano approvati
- [x] Chiamate generate dal documento OpenAPI del back-end
- [x] Elenco, creazione ed eliminazione delle chat
- [x] Vista dei messaggi e invio di una nuova domanda
- [x] Stato di attesa ed errori comprensibili
- [x] Indirizzo del back-end da configurazione
- Evidenze
  - [x] Conversazione completa dal browser, con uso di uno strumento
  - [x] Chat creata dall'interfaccia ancora presente dopo il riavvio
  - [x] Con l'agente spento l'interfaccia mostra l'errore senza bloccarsi
- [x] Prova reale con LM Studio · [x] README · [x] Commit
- **Evidenza minima:** conversazione completa dal browser, errori mostrati

## Step 9 · Docker Compose: un container per componente
- [x] Specifica e piano approvati
- [x] Quattro servizi in `compose.yaml`: tre Dockerfile + PostgreSQL ufficiale
- [x] Browser → front-end; API → back-end (porta o proxy); agente non esposto
- [x] Volume per PostgreSQL; credenziali in `.env` fuori da Git; back-end a database pronto
- [x] Agente → LM Studio con `host.docker.internal`; server MCP stdio nel suo container
- Evidenze
  - [x] `docker compose up` avvia i quattro servizi; `docker compose ps` li mostra attivi
  - [x] Chat dal browser con uno strumento, visibile nei log dell'agente
  - [x] Dopo `down` e `up` le chat sono ancora presenti
- [x] Prova reale con LM Studio · [x] README · [x] Commit
- **Evidenza minima:** quattro container avviati con un comando; agente non esposto

## Facoltativo · Streaming della risposta (dopo lo step 9, se manca)
- [ ] Agente: testo emesso man mano, con gli eventi degli strumenti
- [ ] Back-end: inoltro del flusso (es. Server-Sent Events), salvataggio del messaggio completo
- [ ] Front-end: testo mostrato mentre arriva, indicazione degli strumenti in uso
- [ ] Decisione documentata: con il revisore, bozza in diretta oppure solo risposta approvata
