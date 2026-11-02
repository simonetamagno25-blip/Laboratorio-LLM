# Tre strumenti: tool locale, MCP e API — specifica

Data: 2026-11-02 · Branch: `feat/strumenti-mcp` (da `dev`)
Revisione 2: il docente chiede di integrare gli strumenti con i tre meccanismi (tool, MCP, API);
uno strumento per meccanismo, assegnazione decisa da me (§9).

## 1. Intento

L'assistente del laboratorio (`lezione_4/`) oggi ha un solo strumento, l'orologio.
Si aggiungono tre strumenti, ciascuno legato a un esercizio «Base» del corso e ciascuno collegato
al modello con un meccanismo diverso, così da confrontare i tre approcci:

| Strumento | Meccanismo | Cosa allena |
|-----------|-----------|-------------|
| Calcolatrice sicura | **tool locale** (come l'orologio) | rifiuto esplicito di input non validi: espressioni aritmetiche senza `eval` |
| Convertitore di unità | **server MCP** (stdio, sottoprocesso) | schemi e validazione: unità come elenco chiuso, errore per conversioni incompatibili |
| Giorni e scadenze | **API HTTP** scritta da noi | formati e casi limite: date ISO, festività da file locale, risultato non normativo |

Per il modello tutti e tre appaiono come normali strumenti (tool calling); cambia solo dove
viene eseguito il codice: nel processo dell'assistente, in un server MCP o in un servizio HTTP.

Successo: l'utente fa una domanda in linguaggio naturale, il modello locale sceglie lo strumento
giusto, il programma lo esegue davvero attraverso il suo meccanismo e la risposta è corretta; per
input non validi l'utente riceve un rifiuto esplicito e motivato, mai un risultato inventato o
silenziosamente sbagliato.

Esempi di riferimento:
- «Quanto fa (12 + 8) * 3 / 4?» → calcolatrice; «Calcola `__import__('os')`» → rifiuto.
- «Quanti chilometri sono 26 miglia?» → convertitore; «Converti 5 kg in metri» → errore di incompatibilità.
- «Quanti giorni lavorativi tra il 2026-12-20 e il 2027-01-10?» → giorni e scadenze, con avvertenza non normativa.

## 2. Obiettivi, non obiettivi, anti-obiettivi

**Obiettivi**
- Calcolatrice come tool LangChain locale, accanto all'orologio.
- Un server MCP in Python con il convertitore; l'assistente fa da client MCP.
- Un servizio HTTP in Python con giorni e scadenze; l'assistente lo chiama con un client HTTP.
- Grafo LangGraph invariato nella forma (stessi nodi e instradamento).
- Funziona in locale e in Docker Compose.

**Non obiettivi**
- Esporre lo stesso strumento con più meccanismi.
- Server MCP raggiungibile via rete; API pubblica, autenticazione, HTTPS.
- Altri strumenti; spostare l'orologio.
- Festività regionali/patronali, fusi orari nelle date, orari nelle scadenze.
- Precisione arbitraria nella calcolatrice o conversioni di valuta.

**Anti-obiettivi** (fallimento anche se "funziona")
- Uso di `eval`/`exec` o equivalenti per la calcolatrice.
- Risultati plausibili ma sbagliati invece di un errore (anno non coperto dalle festività,
  data impossibile, unità sconosciuta "indovinata").
- Il resto del codice diventa asincrono.
- Logica degli strumenti duplicata nei meccanismi di trasporto (il server MCP e l'API si limitano
  a esporre funzioni pure testate a parte).
- Test che passano solo con il modello attivo; o una risposta simulata presentata come prova
  che il modello sa usare gli strumenti.

## 3. Vincoli

Valgono tutti quelli del `CLAUDE.md` di `lezione_4/` (codice sincrono, moduli piccoli,
dipendenze motivate e con versioni fissate, comandi PowerShell, test senza modello, ecc.).
In particolare:
- Git: si lavora su `feat/strumenti-mcp`; dopo ogni commit si avvisa l'utente e si fa il push
  **solo dopo la sua conferma**. Merge finale in `dev`; `main` non si tocca.
- Il `CLAUDE.md` non va riscritto per registrare il flusso Git; si aggiorna solo per convenzioni
  stabili (struttura, comandi) e senza togliere regole.

## 4. Architettura

```
terminale ─► grafo LangGraph ─► modello (LM Studio)
                  │
                  └─ nodo strumenti ─┬─► ora_corrente          (tool locale, invariato)
                                     ├─► calcola               (tool locale)
                                     ├─► converti_unita ──stdio──► server MCP (sottoprocesso)
                                     └─► giorni_tra_date  ─┐
                                         calcola_scadenza ─┴─HTTP─► servizio scadenze
```

- **Calcolatrice (tool locale)**: modulo `assistente/calcolatrice.py` con la funzione pura;
  registrata in `crea_strumenti` come `StructuredTool`, come l'orologio.
- **Convertitore (MCP)**: pacchetto `convertitore_mcp/` in `lezione_4/` con la logica pura
  (`unita.py`) e il server scritto con la libreria ufficiale `mcp` (classe `MCPServer`, nome
  della 2.x per l'ex FastMCP). Gli schemi derivano dai tipi Python (`Literal` per le unità), così
  il modello vede l'elenco chiuso. Avviabile da solo con `python -m convertitore_mcp` (stdio).
- **Client MCP / adattatore sincrono** (`assistente/client_mcp.py`): all'avvio lancia il server
  come sottoprocesso via stdio, apre la sessione, legge l'elenco strumenti e li converte in
  `BaseTool` LangChain sincroni. Internamente usa un event loop asyncio dedicato in un thread di
  fondo che tiene aperta la sessione per tutta la durata dell'assistente; ogni chiamata sincrona
  attende il risultato con un timeout. Alla chiusura dell'assistente (`/esci`, EOF, Ctrl+C) la
  sessione e il sottoprocesso vengono chiusi.
  - Se il server non parte o non risponde all'elenco strumenti, l'assistente stampa un messaggio
    chiaro ed esce con codice d'errore.
  - Se il server cade o va in timeout durante la sessione: nessun riavvio; la chiamata restituisce
    `Errore: server MCP non disponibile` (o `timeout`), l'assistente resta aperto.
- **Giorni e scadenze (API)**: pacchetto `scadenze_api/` con la logica pura (`scadenze.py`), il file
  delle festività e un servizio HTTP con la sola libreria standard (`http.server`,
  `ThreadingHTTPServer`), avviabile con `python -m scadenze_api` (porta da `SCADENZE_API_PORTA`,
  predefinita 8000). Endpoint `GET`, parametri in query string, risposte JSON:
  - `GET /giorni?inizio=…&fine=…&solo_lavorativi=true|false`
  - `GET /scadenza?inizio=…&giorni=…&solo_lavorativi=true|false`
  - `GET /salute` → `{"stato": "ok"}`
  - successo: 200 `{"risultato": "<testo>"}`; input non valido: 400 `{"errore": "<motivo>"}`;
    percorso sconosciuto: 404 `{"errore": …}`.
- **Client API** (`assistente/client_api.py`): due `StructuredTool` sincroni con lo stesso schema
  degli endpoint, che chiamano il servizio con `httpx` all'indirizzo `SCADENZE_API_URL`.
  Risposta 400 → `Errore: <motivo>`; servizio irraggiungibile o timeout →
  `Errore: servizio scadenze non raggiungibile su <url>`. L'assistente parte anche se il servizio
  non è attivo (in Compose può avviarsi dopo); l'errore emerge alla prima chiamata.
- **Avvio** (`__main__.py`): strumenti locali + MCP + API passati a modello e grafo.
- **Prompt di sistema**: aggiornato per citare i nuovi strumenti (usa sempre lo strumento per
  calcoli, conversioni e date; non calcolare a mente; riporta all'utente gli errori dello strumento).
- **Errori**: sempre testo che inizia con `Errore:` (convenzione del nodo strumenti attuale).
- **Configurazione**: nuova variabile `SCADENZE_API_URL` (obbligatoria, validata come URL http/https),
  aggiunta a `.env.example` (`http://localhost:8000`) e a `Configurazione`.
- **Docker Compose**: nuovo servizio `scadenze` (stessa immagine, comando `python -m scadenze_api`);
  il servizio `assistente` riceve `SCADENZE_API_URL: http://scadenze:8000` e dipende da `scadenze`.
  Il server MCP gira dentro il container dell'assistente come sottoprocesso.

## 5. Strumenti

### 5.1 `calcola(espressione)` — tool locale
- Analizza l'espressione con `ast.parse(..., mode="eval")` e la valuta con un visitatore che
  ammette **solo**: numeri (int/float letterali, non booleani), `+ - * / % **`, `//` facoltativo a
  scelta del builder, parentesi, `+`/`-` unari. Nessun `eval`/`exec`/`compile` eseguito.
- Rifiuto esplicito e motivato per: nomi, chiamate, attributi, indici, stringhe, confronti,
  operatori bit a bit, sintassi non valida, divisione/modulo per zero, espressione più lunga di
  un limite (es. 200 caratteri), esponente oltre un limite (es. |esponente| > 100) o risultato
  non finito / troppo grande.
- Uscita: `espressione = risultato`.

### 5.2 `converti_unita(valore, da, a)` — MCP
- `valore`: numero (int o float, finito). `da`, `a`: unità dall'elenco chiuso.
- Unità ammesse (simboli esatti usati nello schema):
  - lunghezza: `mm`, `cm`, `m`, `km`, `in`, `ft`, `mi`
  - massa: `g`, `kg`, `t`, `oz`, `lb`
  - temperatura: `C`, `F`, `K` (conversione affine, non solo fattore)
  - volume: `ml`, `l`
  - tempo: `s`, `min`, `h`, `d` (giorni)
- Errori espliciti: unità non in elenco; grandezze diverse
  (`Errore: kg → m: grandezze incompatibili (massa, lunghezza)`); valore non finito;
  temperatura sotto lo zero assoluto.
- Uscita: valore convertito con le due unità, es. `26 mi = 41.8429 km`.

### 5.3 Giorni e scadenze — API
- `giorni_tra_date(inizio, fine, solo_lavorativi=False)`: giorni da `inizio` (escluso) a `fine`
  (incluso). Se `fine` precede `inizio` il risultato è negativo.
- `calcola_scadenza(inizio, giorni, solo_lavorativi=False)`: data ottenuta aggiungendo `giorni`
  (intero ≥ 0) a `inizio`.
  - `inizio` è sempre escluso dal conteggio; con `giorni = 0` il risultato è `inizio` così com'è.
  - Con `solo_lavorativi` il risultato è il `giorni`-esimo giorno lavorativo dopo `inizio`.
  - Senza `solo_lavorativi` la data non viene spostata: se cade di sabato, domenica o in una festività
    nota, il risultato lo segnala (`cade di domenica`) senza rinviarla. La segnalazione delle
    festività vale solo per gli anni coperti dal file; per gli altri anni si segnalano solo sabato e
    domenica e non c'è errore.
- Giorno lavorativo = lunedì–venerdì e non festività nazionale italiana.
- Festività nazionali nel file (2026 e 2027): 1 gennaio, 6 gennaio, Pasqua e Lunedì dell'Angelo
  (2026: 5 e 6 aprile; 2027: 28 e 29 marzo), 25 aprile, 1 maggio, 2 giugno, 15 agosto,
  4 ottobre (San Francesco, festività nazionale dal 2026), 1 novembre, 8 dicembre, 25 e 26 dicembre.
  Il builder verifica l'elenco su una fonte ufficiale prima di scrivere il file e lo cita nel README.
- Formato date: solo `AAAA-MM-GG` rigoroso. Rifiuti espliciti per `02/11/2026`, `2026-2-3`,
  `2026-02-30`, stringhe vuote, con orario. `solo_lavorativi` accetta solo `true`/`false`.
- Se un calcolo con `solo_lavorativi` tocca un anno non presente nel file → errore esplicito con gli
  anni coperti. Limite: `giorni` ≤ 3650 e intervalli di al massimo 3650 giorni.
- Ogni risultato riuscito termina con: `(Risultato indicativo, non ha valore normativo.)`

## 6. Dipendenze

- `mcp==2.3.0` (SDK ufficiale Python, pubblicato il 2026-10-02): server `MCPServer` e client stdio.
  Su Windows porta con sé `pywin32`.
- `httpx` fissata esplicitamente alla versione già installata come dipendenza di `openai`, perché
  ora la usiamo direttamente nel client API.
- Servizio HTTP con la sola libreria standard: nessun framework web nuovo.
- Niente `langchain-mcp-adapters`: l'adattatore MCP è piccolo e scritto a mano, così resta sincrono.

## 7. Test e verifiche

Automatici, senza modello attivo:
- **Logica pura** dei tre strumenti: casi validi, casi limite e ogni tipo di rifiuto elencato sopra
  (temperature, date al confine d'anno, 29 febbraio, festività di sabato/domenica, anno non
  coperto, tentativi di iniezione nella calcolatrice).
- **MCP reale**: avvio di `convertitore_mcp` via stdio con l'adattatore; elenco strumenti, schema
  con unità come elenco chiuso, una chiamata riuscita e una fallita; server che non parte →
  errore chiaro; server terminato a sessione aperta → `Errore: …`.
- **API reale**: servizio avviato in un thread su porta libera; endpoint, codici 200/400/404,
  JSON; client API contro il servizio vero; servizio spento → `Errore: … non raggiungibile`.
- **Grafo**: con modello finto, una chiamata a ciascun nuovo strumento passa dal nodo strumenti e il
  risultato arriva come `ToolMessage`.
- **Configurazione**: `SCADENZE_API_URL` mancante o non valida → errore di configurazione.

Separate e attivate esplicitamente:
- prova reale con LM Studio (marcatore `lmstudio` esistente) con almeno una domanda per
  strumento e una per rifiuto;
- prova in Docker Compose (build, due servizi, domanda da pipe, test nel container).

Il resoconto dice cosa è stato eseguito, con quale esito e cosa resta da provare.

## 8. Documentazione
- README: i tre meccanismi e quale strumento usa quale; come avviare il server MCP e il servizio
  API da soli; nuove variabili; test; diagnosi (server MCP che non parte, API non raggiungibile,
  anno festività non coperto). Solo comandi verificati.
- `CLAUDE.md`: aggiungere i nuovi comandi stabili; non togliere regole.

## 9. Decisioni prese da me (da verificare leggendo)
- Assegnazione: calcolatrice → tool locale; convertitore → MCP; giorni e scadenze → API.
- Pacchetti separati per meccanismo: `convertitore_mcp/`, `scadenze_api/`; calcolatrice in `assistente/`.
- API con la sola libreria standard, endpoint GET con query string, `httpx` come client.
- L'assistente parte anche senza API attiva; si blocca invece se il server MCP non parte.
- Server MCP: nessun riavvio a sessione aperta, solo errori espliciti.
- Elenco unità del §5.2; simboli ASCII (`C`, `F`, `K`, `d`).
- Regole di date e scadenze del §5.3; 4 ottobre incluso tra le festività dal 2026.
- Adattatore MCP sincrono scritto a mano, senza `langchain-mcp-adapters`.
- Git: la specifica si committa su `feat/strumenti-mcp` dopo l'approvazione; push solo su conferma.

## 10. Lasciato a chi implementa
- Nomi esatti di funzioni interne, formato numerico dell'output, limiti precisi (lunghezza
  espressione, esponente, timeout MCP e HTTP), purché documentati e testati.
- Struttura del file JSON delle festività.
- Ordine degli incrementi nel piano.
