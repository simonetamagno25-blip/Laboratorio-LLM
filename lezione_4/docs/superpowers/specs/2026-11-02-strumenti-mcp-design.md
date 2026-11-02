# Strumenti MCP — specifica

Data: 2026-11-02 · Branch: `feat/strumenti-mcp` (da `dev`)

## 1. Intento

L'assistente del laboratorio (`lezione_4/`) oggi ha un solo strumento, l'orologio.
Si aggiungono tre strumenti forniti da un **server MCP**, ciascuno legato a un esercizio
«Base» del corso:

| Strumento | Cosa allena |
|-----------|-------------|
| Convertitore di unità | schemi e validazione: unità come elenco chiuso, errore per conversioni incompatibili |
| Calcolatrice sicura | rifiuto esplicito di input non validi: espressioni aritmetiche senza `eval` |
| Giorni e scadenze | formati e casi limite: date ISO, festività da file locale, risultato non normativo |

Successo: l'utente fa una domanda in linguaggio naturale, il modello locale sceglie lo strumento
giusto, il programma lo esegue davvero tramite MCP e la risposta è corretta; per input non validi
l'utente riceve un rifiuto esplicito e motivato, mai un risultato inventato o silenziosamente sbagliato.

Esempi di riferimento:
- «Quanti chilometri sono 26 miglia?» → convertitore; «Converti 5 kg in metri» → errore di incompatibilità.
- «Quanto fa (12 + 8) * 3 / 4?» → calcolatrice; «Calcola `__import__('os')`» → rifiuto.
- «Quanti giorni lavorativi tra il 2026-12-20 e il 2027-01-10?» → giorni e scadenze, con avvertenza non normativa.

## 2. Obiettivi, non obiettivi, anti-obiettivi

**Obiettivi**
- Un server MCP in Python con i tre strumenti.
- L'assistente fa da client MCP: avvia il server, ne elenca gli strumenti e li offre al modello
  insieme all'orologio.
- Grafo LangGraph invariato nella forma (stessi nodi e instradamento).
- Funziona in locale e in Docker Compose.

**Non obiettivi**
- Server MCP come servizio separato o raggiungibile via rete; altri client MCP.
- Altri strumenti oltre ai tre; spostare l'orologio sul server MCP.
- Festività regionali/patronali, fusi orari nelle date, orari nelle scadenze.
- Precisione arbitraria nella calcolatrice o conversioni di valuta.

**Anti-obiettivi** (fallimento anche se "funziona")
- Uso di `eval`/`exec` o equivalenti per la calcolatrice.
- Risultati plausibili ma sbagliati invece di un errore (anno non coperto dalle festività,
  data impossibile, unità sconosciuta "indovinata").
- Il resto del codice diventa asincrono.
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
                  └─ nodo strumenti ─┬─► ora_corrente (locale, invariato)
                                     └─► adattatore MCP sincrono ─stdio─► server MCP (sottoprocesso)
                                                                          ├ converti_unita
                                                                          ├ calcola
                                                                          ├ giorni_tra_date
                                                                          └ calcola_scadenza
```

- **Server MCP**: pacchetto `assistente_mcp/` in `lezione_4/`, scritto con la libreria ufficiale
  `mcp` (FastMCP). Gli schemi degli input derivano dai tipi Python (enum/`Literal` per le unità),
  così il modello vede l'elenco chiuso. Avviabile da solo con `python -m assistente_mcp`
  (trasporto stdio).
- **Logica separata dal protocollo**: ogni strumento è una funzione pura in un suo modulo
  (`unita.py`, `calcolatrice.py`, `scadenze.py`); il modulo del server si limita a registrarle.
- **Client MCP / adattatore sincrono** (nuovo modulo in `assistente/`, es. `mcp_client.py`):
  all'avvio lancia il server come sottoprocesso via stdio, apre la sessione, legge l'elenco
  strumenti e li converte in `BaseTool` LangChain sincroni. Internamente usa un event loop
  asyncio dedicato in un thread di fondo che tiene aperta la sessione per tutta la durata
  dell'assistente; ogni chiamata sincrona attende il risultato con un timeout. Alla chiusura
  dell'assistente (anche con `/esci`, EOF, Ctrl+C) la sessione e il sottoprocesso vengono chiusi.
- **Avvio**: `__main__.py` crea gli strumenti come oggi più quelli MCP e li passa a modello e grafo.
  Se il server non parte o non risponde all'elenco strumenti, l'assistente stampa un messaggio
  chiaro ed esce con codice d'errore (non parte "a metà" con solo l'orologio).
- **Server che cade o va in timeout durante la sessione**: nessun riavvio automatico; ogni chiamata
  a uno strumento MCP restituisce `Errore: server MCP non disponibile` (o `timeout`), l'assistente
  resta aperto e l'orologio continua a funzionare (scelta mia).
- **Prompt di sistema**: aggiornato per citare i nuovi strumenti (usa sempre lo strumento per
  conversioni, calcoli e date; non calcolare a mente; riporta all'utente gli errori dello strumento).
- **Errori degli strumenti**: restituiti come testo che inizia con `Errore:` (stessa convenzione
  del nodo strumenti attuale), così il modello li vede e li spiega.
- **Docker**: stesso container, stessa immagine; il Dockerfile copia anche `assistente_mcp/` e i
  dati delle festività. Nessun nuovo servizio in Compose.

## 5. Strumenti

### 5.1 `converti_unita(valore, da, a)`
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
- Uscita: valore convertito con le due unità, es. `26 mi = 41.843 km`; arrotondamento a un numero
  ragionevole di cifre significative (scelta del builder, documentata e testata).

### 5.2 `calcola(espressione)`
- Analizza l'espressione con `ast.parse(..., mode="eval")` e la valuta con un visitatore che
  ammette **solo**: numeri (int/float letterali), `+ - * / % **`, `//` facoltativo a scelta del
  builder, parentesi, `+`/`-` unari. Nessun `eval`/`exec`/`compile` eseguito.
- Rifiuto esplicito e motivato per: nomi, chiamate, attributi, indici, stringhe, confronti,
  operatori bit a bit, sintassi non valida, divisione/modulo per zero, espressione più lunga di
  un limite (es. 200 caratteri), esponente oltre un limite (es. |esponente| > 100) o risultato
  non finito / troppo grande.
- Uscita: `espressione = risultato`.

### 5.3 Giorni e scadenze
- `giorni_tra_date(inizio, fine, solo_lavorativi=False)`: giorni da `inizio` (escluso) a `fine`
  (incluso). Se `fine` precede `inizio` il risultato è negativo (scelta mia, da confermare in test).
- `calcola_scadenza(inizio, giorni, solo_lavorativi=False)`: data ottenuta aggiungendo `giorni`
  (intero ≥ 0) a `inizio`; con `solo_lavorativi` si contano solo i giorni lavorativi.
  Regole (scelte mie, coerenti con `giorni_tra_date`):
  - `inizio` è sempre escluso dal conteggio; con `giorni = 0` il risultato è `inizio` così com'è.
  - Con `solo_lavorativi` il risultato è il `giorni`-esimo giorno lavorativo dopo `inizio`
    (quindi cade sempre in un giorno lavorativo).
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
  `2026-02-30`, stringhe vuote, con orario.
- Festività da file locale JSON (es. `assistente_mcp/dati/festivita_it.json`) per gli anni 2026 e
  2027, Pasqua/Pasquetta incluse come date fisse nel file. Se il calcolo con `solo_lavorativi`
  tocca un anno non presente nel file → errore esplicito con gli anni coperti. Senza
  `solo_lavorativi` le festività non servono e non c'è limite di anno.
- Limite ragionevole sull'ampiezza (es. `giorni` ≤ 3650) per evitare cicli enormi.
- Ogni risultato riuscito termina con: `(Risultato indicativo, non ha valore normativo.)`

## 6. Dipendenze

- `mcp` (SDK ufficiale Python: server FastMCP e client stdio). Unica dipendenza nuova prevista;
  versione fissata nel piano dopo verifica della compatibilità con Python 3.12 e con le versioni
  già presenti.
- Niente `langchain-mcp-adapters`: l'adattatore è piccolo e scritto a mano, così resta sincrono
  e senza una dipendenza in più (scelta mia).

## 7. Test e verifiche

Automatici, senza modello attivo:
- **Logica pura** dei tre strumenti: casi validi, casi limite e ogni tipo di rifiuto elencato sopra
  (incluse temperature, date al confine d'anno, 29 febbraio, festività di sabato/domenica,
  anno non coperto, tentativi di iniezione nella calcolatrice).
- **Server MCP reale**: test che avvia `assistente_mcp` via stdio con l'adattatore e verifica
  l'elenco dei quattro strumenti, i loro schemi (unità come elenco chiuso) e una chiamata riuscita
  e una fallita per strumento.
- **Grafo**: con modello finto, una chiamata a uno strumento MCP passa dal nodo strumenti e il
  risultato arriva come `ToolMessage`; errori dello strumento arrivano come testo `Errore: ...`.
- **Avvio**: server che non parte → messaggio chiaro e uscita.

Separate e attivate esplicitamente:
- prova reale con LM Studio (marcatore `lmstudio` esistente) con almeno una domanda per
  strumento e una per rifiuto;
- prova in Docker (build + domanda da pipe + test nel container).

Il resoconto dice cosa è stato eseguito, con quale esito e cosa resta da provare.

## 8. Documentazione
- README: nuovi strumenti, come avviare il server MCP da solo, test, diagnosi (server MCP che
  non parte, anno festività non coperto). Solo comandi verificati.
- `CLAUDE.md`: aggiungere eventuali nuovi comandi stabili; non togliere regole.

## 9. Decisioni prese da me (da verificare leggendo)
- Un solo server MCP con tutti gli strumenti, in `assistente_mcp/` dentro `lezione_4/`.
- Date: quattro strumenti MCP in totale (due per giorni e scadenze) invece di uno con parametro
  "operazione", per semplificare la scelta a un modello locale piccolo.
- Elenco unità del §5.1; simboli ASCII (`C`, `F`, `K`, `d`).
- Inizio escluso / fine inclusa; differenza negativa se le date sono invertite.
- Festività solo nazionali italiane, anni 2026–2027.
- Adattatore sincrono scritto a mano, senza `langchain-mcp-adapters`.
- Avvio bloccato se il server MCP non parte; durante la sessione, nessun riavvio ma errori espliciti.
- Regole di `calcola_scadenza` del §5.3 (inizio escluso, nessun rinvio automatico senza
  `solo_lavorativi`, solo segnalazione).
- 4 ottobre incluso tra le festività nazionali dal 2026.
- Git: la specifica si committa su `feat/strumenti-mcp` dopo l'approvazione; push solo su conferma.

## 10. Lasciato a chi implementa
- Nomi esatti di moduli e funzioni interne, formato numerico dell'output, limiti precisi
  (lunghezza espressione, esponente, giorni massimi, timeout chiamata MCP), purché documentati e testati.
- Struttura del file JSON delle festività.
- Ordine degli incrementi nel piano.
