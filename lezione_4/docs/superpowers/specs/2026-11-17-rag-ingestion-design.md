# Lezione 7 · Esercizio 1: ingestion e ricerca semantica — specifica

Fonte: `LLM_Lez_7.pdf` («Dai documenti alla ricerca semantica: introduzione al RAG e ingestion»),
slide 11–29. Branch: `feat/rag`, creato da `feat/agente-web`.

## Intento
Costruire un indice vettoriale **ripetibile** del ricettario di Artusi e una ricerca che, data una
domanda, restituisce i passaggi pertinenti **con la loro fonte** (ricetta, capitolo, posizione del
chunk). Il retrieval resta isolato: nessun modello generativo. Serve a misurare la qualità del
recupero prima che, nella lezione 8, la ricerca diventi uno strumento dell'agente: se il passaggio
giusto non arriva, nessun prompt al generatore lo compensa.

Criterio di completamento (slide 29): dato un risultato si sanno indicare ricetta, capitolo e
posizione del chunk; l'ingestion si riesegue senza duplicati; ogni scelta di questa specifica è
motivata.

## Obiettivi
- Pacchetto `rag/` con tre comandi: `python -m rag.ingestion`, `python -m rag.ricerca`,
  `python -m rag.valuta`.
- Corpus pulito: 790 ricette numerate senza buchi, ognuna con numero, titolo e capitolo.
- Chunking configurabile (strategia, dimensione, overlap).
- Embedding con un modello di LM Studio letto dalla configurazione, lo stesso per chunk e domande;
  modello registrato nella collezione e cambio bloccato.
- Qdrant in Docker Compose con volume: un punto per chunk, ID stabili, payload con testo e
  metadati, indice sul campo filtrato.
- Ricerca top-k con massimo imposto dal codice e filtro per capitolo **durante** la ricerca.
- Valutazione su domande con fonte attesa: tabella riproducibile con posizione e score.
- Test che passano con LM Studio e Qdrant spenti.

## Non obiettivi
- Modello generativo, tool `search_documents`, server MCP, agente: lezione 8.
- Modifiche A (`contiene_dosi`) e B (titolo nel testo indicizzato): cicli successivi, ciascuno con
  la propria specifica. Questa specifica deve però renderle possibili senza riscritture (vedi
  «Predisposizione per A e B»).
- Estensioni facoltative (confronto sistematico di strategie, secondo modello multilingue).
- Prefissi di task del modello di embedding (es. `search_query:` di nomic): cambierebbero il
  confronto con la slide 22; eventualmente in un ciclo a parte.
- Codice di download del corpus: il README documenta il comando.

## Anti-obiettivi
- Una seconda ingestion che aumenta i punti, o lascia punti orfani dopo un cambio di chunking.
- Una ricerca che mescola embedding di modelli diversi senza accorgersene.
- Un risultato di cui non si sa dire da quale ricetta e da quale punto della ricetta viene.
- Chunk che contengono intestazione e licenza di Gutenberg, l'appendice o l'indice del libro.
- Dichiarare «funziona» senza la tabella della valutazione.
- Test che richiedono LM Studio o un server Qdrant per passare.

## Decisioni prese con l'utente
| Tema | Decisione |
|---|---|
| Dove | pacchetto `rag/` dentro `lezione_4/`, separato da `assistente/`, così la lezione 8 lo collega all'agente |
| Branch | `feat/rag` da `feat/agente-web` |
| Cicli | esercizio 1 ora; A e B dopo, ciascuno con il ciclo completo e una nuova valutazione |
| Unità di documento | una ricetta = un documento |
| Chunking predefinito | **per paragrafi**: paragrafi interi accorpati fino a `CHUNK_DIMENSIONE` (1200 caratteri) con `CHUNK_OVERLAP` (200), senza mai superare il confine della ricetta. Scelto perché tiene le dosi con il piatto e il procedimento (un terzo dei paragrafi è sotto i 120 caratteri, per lo più righe di dosi) e perché ripete la configurazione della slide 22, utile come termine di confronto |
| Strategia alternativa | finestra fissa con overlap, selezionabile da configurazione |
| Librerie | (proposta in conversazione, senza obiezioni; da confermare con l'approvazione) chiamate dirette: `httpx` (già presente) verso `/v1/embeddings`, `qdrant-client` per Qdrant. Scartato LangChain (`OpenAIEmbeddings` + `langchain-qdrant`): dipendenza in più, ID e payload meno controllabili, e `OpenAIEmbeddings` tokenizza con `tiktoken` di default, da disattivare con LM Studio |
| Ripetizioni | ID stabili e upsert (strategia A della slide 18), non la ricostruzione: le modifiche A e B richiedono di aggiornare i punti senza ricreare la collezione |

## Scelte di chi ha scritto la specifica (da controllare)
- Qdrant con profilo `rag` e porta solo su `127.0.0.1`: l'applicazione completa non cambia.
- Massimo di k = 20, costante nel codice; k fuori limite → errore, non troncamento silenzioso.
- Rimozione dei punti orfani a ogni ingestion.
- Capitolo nel filtro confrontato senza maiuscole, valori sconosciuti rifiutati con l'elenco.
- Opzione `--solo-analisi` per ispezionare i chunk senza servizi.
- Nessun prefisso di task per il modello di embedding.

## Approcci considerati
1. **`httpx` + `qdrant-client` diretti** (scelto). Una sola dipendenza nuova; ogni passo della
   slide 11 è una funzione ispezionabile; `set_payload` permette la modifica A; i test usano
   `QdrantClient(":memory:")`.
2. **Wrapper LangChain** (`OpenAIEmbeddings`, `QdrantVectorStore`). Meno codice e coerente con
   l'agente, ma nasconde proprio gli ID e il payload che l'esercizio chiede di controllare.
3. **Ricostruzione completa della collezione a ogni ingestion.** Semplice, ma incompatibile con le
   modifiche A e B («senza ricreare la collezione»).

## Il corpus (osservato sul file reale)
- Fonte: Project Gutenberg n. 59047, UTF-8, salvato in `dati/artusi.txt` (fuori da Git).
  `www.gutenberg.org` può essere in manutenzione: il mirror `gutenberg.pglaf.org/5/9/0/4/59047/59047-0.txt`
  serve lo stesso testo. Il README riporta il comando PowerShell.
- Intestazione e licenza delimitate da `*** START OF …` e `*** END OF …`.
- Prima delle ricette: prefazioni e note (fino alla riga `RICETTE`). Dopo la ricetta 790: la riga
  `APPENDICE` e poi «Cucina per gli stomachi deboli» e l'indice: **esclusi**.
- Ricette nel formato `N. Titolo` a inizio riga; nel testo compaiono anche rimandi come
  «del N. 14», da non scambiare per un inizio di ricetta (i numeri crescono di uno).
- Capitoli: righe in maiuscolo isolate da righe vuote (`MINESTRE IN BRODO`, `FRITTI`, …). Compaiono
  anche righe maiuscole che **non** sono capitoli: sovratitoli (`MINESTRE` sopra `MINESTRE IN
  BRODO`), sottotitoli interni a una ricetta (`RICETTA A`, `PRIMA RICETTA`, `PASTA FROLLA`,
  `QUALITÀ E STAGIONE DEI PESCI`), firme (`UN AMMIRATORE`).
- Righe spezzate a circa 70 caratteri; paragrafi separati da righe vuote; elenchi di ingredienti
  rientrati; corsivi segnati con `_parola_`.
- Misure: 3167 paragrafi; 72% delle ricette sotto i 1200 caratteri; mediana circa 880.

## Progetto

### Struttura di `rag/`
Moduli piccoli, uno per passo della pipeline (nomi indicativi, il builder può adattarli):
- `config.py` — configurazione da variabili d'ambiente;
- `corpus.py` — caricamento e pulizia: dal file a una lista di `Ricetta(numero, titolo, capitolo,
  paragrafi)`;
- `chunking.py` — da ricetta a chunk, due strategie;
- `embedding.py` — client di `/v1/embeddings` (protocollo `Embedder` con `embed(testi) -> vettori`,
  così i test usano un embedder finto);
- `indice.py` — collezione Qdrant: creazione, controllo del modello, upsert, rimozione orfani,
  conteggio, ricerca;
- `ingestion.py`, `ricerca.py`, `valuta.py` — i tre comandi (`__main__` con `argparse`).

### Configurazione (variabili d'ambiente, valori nel `.env.example`)
| Variabile | Predefinito | Note |
|---|---|---|
| `LMSTUDIO_BASE_URL` | obbligatoria | già esistente, condivisa con l'agente |
| `LMSTUDIO_EMBEDDING_MODEL` | obbligatoria | identificativo restituito da `GET /v1/models`, mai inventato |
| `QDRANT_URL` | `http://localhost:6333` | in Docker `http://qdrant:6333` da `compose.yaml` |
| `QDRANT_COLLEZIONE` | `ricette` | |
| `PERCORSO_CORPUS` | `dati/artusi.txt` | |
| `CHUNK_STRATEGIA` | `paragrafi` | `paragrafi` oppure `finestra` |
| `CHUNK_DIMENSIONE` | `1200` | caratteri, intero positivo |
| `CHUNK_OVERLAP` | `200` | caratteri, `0 ≤ overlap < dimensione` |
| `EMBEDDING_LOTTO` | `32` | testi per richiesta a `/v1/embeddings` |
| `RAG_TOP_K` | `5` | k predefinito |

Il massimo di k (`TOP_K_MASSIMO = 20`) è una costante nel codice, non configurabile (slide 25:
«massimo imposto dal codice»). Configurazione non valida → messaggio chiaro e codice di uscita 2,
come nel resto del progetto. La configurazione del RAG è separata da quella dell'agente:
`rag` non deve richiedere `AMBITO_AGENTE` o le altre variabili dell'agente.

### Pulizia del corpus
- Si tiene solo il testo tra i marcatori di Gutenberg, e di questo solo la parte da `RICETTE` ad
  `APPENDICE` (esclusa).
- Capitoli riconosciuti confrontando le righe maiuscole con l'**elenco dei 23 capitoli** del libro,
  tenuto nel codice; la versione nel payload è in forma leggibile («Minestre in brodo»,
  «Fritti»), come nella slide 16. Ogni ricetta riceve il capitolo più recente.
- Una ricetta inizia a una riga `N. Titolo` con `N` = numero precedente + 1.
- Dentro un paragrafo le righe spezzate si uniscono con uno spazio; spazi multipli normalizzati;
  marcatori di corsivo `_` rimossi; caratteri di controllo rimossi. I confini di paragrafo
  (righe vuote) si conservano: servono al chunking.
- Le righe maiuscole interne a una ricetta che non sono capitoli restano nel testo come paragrafi.
- Validazione: 790 ricette, numerate da 1 a 790 senza buchi, 23 capitoli distinti, nessuna ricetta
  senza capitolo o con testo vuoto. Se fallisce, l'ingestion si ferma con un errore che dice cosa
  manca, prima di toccare Qdrant.

### Chunking
- **`paragrafi`** (predefinito): si accodano paragrafi interi finché il chunk non supera
  `CHUNK_DIMENSIONE`. Il chunk successivo riparte includendo, dalla fine del precedente, i
  paragrafi interi che stanno in `CHUNK_OVERLAP` caratteri (se l'ultimo paragrafo è più lungo
  dell'overlap, l'overlap è vuoto: non si taglia un paragrafo per fare overlap). Un paragrafo più
  lungo di `CHUNK_DIMENSIONE` si spezza per frasi; una frase più lunga ancora, a finestra.
- **`finestra`**: finestre di `CHUNK_DIMENSIONE` caratteri sul testo della ricetta, con
  `CHUNK_OVERLAP` caratteri ripetuti, spostando il taglio all'ultimo spazio per non spezzare
  parole.
- Entrambe: nessun chunk attraversa due ricette; nessun chunk vuoto; `posizione` parte da 0 in
  ogni ricetta. Una ricetta breve produce un solo chunk.

### Embedding
- `POST {LMSTUDIO_BASE_URL}/embeddings` con `model` e `input` (lista), a lotti di
  `EMBEDDING_LOTTO`; risposte riordinate per `index`.
- La dimensione dei vettori **si misura** dalla prima risposta, non si configura.
- Errori (server spento, modello non caricato, risposta inattesa) → messaggio comprensibile che
  nomina URL e modello; codice di uscita 1.
- Stesso client e stesso modello per i chunk (ingestion) e per la domanda (ricerca).

### Collezione Qdrant
- Nome da `QDRANT_COLLEZIONE`, distanza coseno, dimensione = dimensione misurata.
- Metadati della collezione: `modello_embedding` e `dimensione`. All'avvio di ingestion e ricerca:
  se la collezione esiste e il modello registrato è diverso da quello configurato, ci si ferma
  con un errore che spiega di reindicizzare (eliminare la collezione e rifare l'ingestion). Stessa
  cosa se la dimensione non coincide.
- Indice sul payload: `capitolo` (keyword).
- **ID del punto**: `uuid5(NAMESPACE, f"{documento_id}:{posizione}")` con un namespace fisso nel
  codice. Stesso chunk → stesso ID → l'upsert sostituisce.
- **Orfani**: dopo l'upsert si eliminano i punti della collezione il cui ID non è stato prodotto da
  questa esecuzione (per esempio dopo un cambio di dimensione dei chunk che ne riduce il numero).
- **Payload** di ogni punto:

  | Campo | Esempio | Uso |
  |---|---|---|
  | `documento_id` | `ricetta-089` | identificativo stabile, base dell'ID |
  | `numero` | `89` | citare la ricetta |
  | `titolo` | `Gnocchi di patate` | fonte leggibile |
  | `capitolo` | `Minestre asciutte e di magro` | fonte e filtro |
  | `posizione` | `0` | ordine nel documento, chunk adiacenti |
  | `testo` | testo del chunk | ciò che la ricerca restituisce |
  | `fonte` | `Artusi, La scienza in cucina e l'arte di mangiar bene (1891), Project Gutenberg n. 59047` | citazione |

### Comando `python -m rag.ingestion`
Carica, pulisce, valida, divide, calcola gli embedding a lotti, crea la collezione se manca,
controlla il modello, fa l'upsert, rimuove gli orfani. Registra (log `INFO`): ricette, chunk
prodotti, configurazione di chunking, modello, dimensione, punti nella collezione **prima** e
**dopo**, punti rimossi, durata. Opzione `--solo-analisi`: si ferma dopo il chunking e stampa le
statistiche (numero di chunk, distribuzione delle lunghezze), senza LM Studio né Qdrant: serve a
ispezionare il risultato prima di indicizzare (slide 11).

### Comando `python -m rag.ricerca "domanda" [--capitolo NOME] [--k N]`
- Embedding della domanda così com'è, query a Qdrant dei k punti più vicini, con il filtro sul
  capitolo **dentro** la query (slide 17).
- `--k` fuori da `1..TOP_K_MASSIMO` → errore. `--capitolo` confrontato senza distinzione di
  maiuscole con i 23 capitoli noti; valore sconosciuto → errore che elenca i capitoli validi (evita
  il «filtro senza risultati» della slide 23).
- Per ogni risultato stampa: posizione in classifica, score, `N. Titolo`, capitolo, posizione del
  chunk, testo. La funzione di ricerca restituisce oggetti con questi campi (nella lezione 8 la
  userà il tool).

### Comando `python -m rag.valuta [--k N] [--output FILE]`
- Legge le domande da un file versionato (`rag/domande.json`): testo, fonte attesa (lista di
  numeri di ricetta, vuota se il corpus non contiene la risposta), capitolo facoltativo per le
  domande da provare anche con il filtro.
- Per ogni domanda: posizione della prima fonte attesa tra i primi k (o «assente»), score della
  fonte, score migliore. Per le domande senza risposta: lo score migliore (la slide 22 mostra che
  non esiste una soglia).
- Stampa una tabella Markdown preceduta dalla configurazione (modello, strategia, dimensione,
  overlap, k, punti nella collezione) e il riepilogo «fonte trovata in X casi su Y». Con
  `--output` la scrive anche su file. Stesso indice e stesse domande → stessa tabella.
- Domande viste in aula, con il testo delle slide (fonti verificate sul file):

  | Domanda | Fonte attesa | Slide |
  |---|---|---|
  | Quanta farina serve per 400 grammi di patate negli gnocchi? | 89 | 21, 22 |
  | Che vino si usa per il pollo alla cacciatora? | 208 | 21, 22 |
  | Come si chiama il cacciucco sulle coste dell'Adriatico? | 455 o 456 (una domanda: vale la prima delle due che compare) | 21 |
  | Quanti cappelletti bastano a un mangiatore moderato? | 7 (Cappelletti all'uso di Romagna) | 22 |
  | Perché gli gnocchi possono sciogliersi nell'acqua? | 89 | 22 |
  | Qual è la ricetta del tiramisù? | nessuna | 21, 22 |

  Si aggiungono almeno tre domande nuove con fonte attesa, scritte senza copiare le parole del
  testo, e una seconda domanda senza risposta nel corpus: in tutto otto con fonte e due senza,
  come nella slide 22 (che mostra solo cinque righe delle sue dieci). Le fonti attese delle
  domande nuove si verificano leggendo il testo prima di eseguire la ricerca. Il file delle
  domande non cambia tra la valutazione di partenza e quelle dopo A e dopo B.

### Docker Compose
- Servizio `qdrant` con l'immagine ufficiale a versione fissata (`qdrant/qdrant:v1.20.2`,
  allineata a `qdrant-client` 1.20.0), volume `dati_qdrant`. Porta 6333 pubblicata **solo su
  `127.0.0.1`** (API e dashboard dal browser dell'host; Qdrant non ha chiave API). Ha il profilo
  `rag`, come il servizio `rag`: `docker compose up -d --build` dell'applicazione completa resta
  com'è e non avvia Qdrant; lo si avvia con `docker compose up -d qdrant` (nominare il servizio ne
  attiva il profilo). Nella lezione 8, quando la ricerca entra nell'agente, Qdrant passerà allo
  stack principale.
- Servizio `rag` con profilo `rag` (non parte con `up`): stessa immagine dell'applicazione,
  `QDRANT_URL=http://qdrant:6333`, `LMSTUDIO_BASE_URL=http://host.docker.internal:1234/v1`,
  `./dati` montata in sola lettura. Esempi:
  `docker compose run --rm rag python -m rag.ingestion`.
- Il `Dockerfile` copia anche `rag/`. Gli altri servizi non cambiano.

### Dipendenze
- `qdrant-client==1.20.0` (motivazione: client ufficiale; modalità in memoria per i test).
- Nessun'altra dipendenza nuova.

## Test (senza servizi)
- **Corpus**: su un estratto sintetico con intestazione Gutenberg, sovratitolo, sottotitolo
  interno, rimando «N. 14» e appendice → ricette, titoli e capitoli corretti, appendice esclusa;
  validazione che segnala un buco nella numerazione. Un test sul file reale, saltato se
  `dati/artusi.txt` manca, verifica 790 ricette e 23 capitoli.
- **Chunking**: ricetta breve → un chunk; ricetta lunga → più chunk entro la dimensione, confini a
  fine paragrafo, overlap fatto di paragrafi interi; paragrafo gigante spezzato; strategia
  `finestra`; parametri non validi rifiutati.
- **Embedding**: client HTTP con trasporto finto di `httpx` (lotti, riordino per `index`, errori).
- **Indice** con `QdrantClient(":memory:")` ed embedder finto deterministico: due ingestion →
  stesso numero di punti; ID stabili; orfani rimossi dopo un cambio di chunking; modello diverso
  bloccato; filtro per capitolo → tutti i risultati del capitolo, al massimo k; k fuori limite
  rifiutato; payload completo.
- **Valutazione**: con risultati simulati, posizione, «assente» e riepilogo corretti.
- **Prova reale** separata (marker `lmstudio`, già esistente): l'embedder reale restituisce vettori
  della stessa dimensione per due testi.

## Verifiche reali (da registrare in `docs/retrieval.md`)
1. LM Studio con il modello di embedding caricato; `docker compose up -d qdrant`.
2. Ingestion completa due volte: punti dopo la prima = punti dopo la seconda.
3. Ricerca con e senza `--capitolo`.
4. `python -m rag.valuta`: tabella di partenza.
5. Due query commentate (una riuscita, una mancata con la causa, es. ricetta 208).

`docs/retrieval.md` raccoglie queste evidenze; le sezioni «dopo A» e «dopo B» arriveranno con i
cicli successivi. Il README riceve configurazione, download del corpus, avvio di Qdrant, i tre
comandi e la diagnosi (tabella degli errori tipici della slide 23), solo con comandi verificati.

## Predisposizione per A e B
- A (`contiene_dosi`): il payload è un dizionario costruito in un solo punto; `indice.py` espone
  l'aggiornamento del payload senza ricalcolare gli embedding; il filtro della ricerca accetta più
  condizioni.
- B (titolo nel testo indicizzato): il testo passato all'embedder è prodotto da una funzione
  separata dal testo salvato nel payload (oggi coincidono).

## Lasciato al builder
- Nomi interni di funzioni e classi, forma dell'output a terminale, formato dei log.
- Come implementare il taglio per frasi e l'embedder finto (purché deterministico e capace di
  rendere significativi i test di ricerca).
- Testo delle domande nuove della valutazione e della seconda domanda senza risposta.
- Codici di uscita per Qdrant non raggiungibile, arrotondamento degli score, validazione della
  configurazione con `--solo-analisi` (che non deve richiedere LM Studio né Qdrant).

## Verifiche già fatte (2026-11-17)
- `qdrant-client==1.20.0` esiste su PyPI; l'immagine `qdrant/qdrant:v1.20.2` esiste su Docker Hub.
- `create_collection(..., metadata={...})` funziona anche con `QdrantClient(":memory:")` e
  `get_collection(...).config.metadata` restituisce i valori: i metadati della collezione sono
  testabili senza server. Se una versione fissata risultasse inutilizzabile, si sceglie la più
  vicina della stessa serie e lo si segnala; un cambio di serie torna all'utente.
- Fonti attese delle domande in aula: 7 «Cappelletti all'uso di Romagna», 89 «Gnocchi di patate»,
  208 «Pollo alla cacciatora», 455 «Cacciucco I», 456 «Cacciucco II».

## Da verificare all'inizio del piano
- L'identificativo del modello di embedding in LM Studio (`GET /v1/models`), quando LM Studio è
  acceso: oggi non è raggiungibile. Senza di esso si possono fare tutti i passi tranne la prova
  reale.
