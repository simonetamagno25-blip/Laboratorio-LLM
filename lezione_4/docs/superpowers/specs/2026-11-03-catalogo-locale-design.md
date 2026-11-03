# Catalogo locale del laboratorio — specifica

Data: 2026-11-03 · Esercizio «Intermedio: Catalogo locale» · Stato: approvata dall'utente il 2026-11-03.

Primo dei tre esercizi intermedi (catalogo, note persistenti, meteo), da realizzare uno alla volta,
ciascuno con specifica e piano propri.

## 1. Intento

L'assistente del laboratorio (`lezione_4/`) ha già orologio e calcolatrice (tool locali),
convertitore (MCP) e giorni/scadenze (API). Si aggiunge un **catalogo del materiale del
laboratorio** (schede, sensori, cavi, alimentatori…) letto da un file JSON del progetto.

L'esercizio allena due cose:
- **la scelta tra più tool**: due strumenti con scopi vicini ma diversi (cercare vs. leggere
  la scheda), che il modello deve distinguere e, quando serve, usare in sequenza;
- **i risultati vuoti**: quando non c'è nulla, lo strumento lo dice in modo esplicito e il
  modello risponde che l'articolo non c'è, senza inventare.

Meccanismo: **tool locale** (come la calcolatrice). Motivo: i dati sono nel progetto e si
leggono soltanto; un server MCP o un'API aggiungerebbero un processo senza insegnare niente
di nuovo su questo esercizio.

Successo, con il modello reale di LM Studio:

| Domanda | Comportamento atteso |
|---------|----------------------|
| «Avete sensori di temperatura?» | chiama `cerca_articoli`, elenca i risultati |
| «Dimmi tutto su SEN-004» | chiama `dettaglio_articolo` con `SEN-004` |
| «Dov'è il sensore di umidità?» | `cerca_articoli`, poi `dettaglio_articolo` sul codice trovato, risponde con la posizione |
| «Avete stampanti 3D?» | `cerca_articoli` senza risultati; risponde che non ci sono, senza inventare |
| «Dettaglio di XYZ-999» | `dettaglio_articolo` → codice inesistente; spiega l'errore |

## 2. Obiettivi, non obiettivi, anti-obiettivi

**Obiettivi**
- File `catalogo.json` con circa 20 articoli plausibili, in più categorie, con almeno un
  articolo a quantità 0.
- Due tool locali, `cerca_articoli` e `dettaglio_articolo`, accanto a quelli esistenti.
- Prompt di sistema aggiornato perché il modello sappia quando usarli.
- Funziona in locale e in Docker Compose, senza nuove dipendenze (solo `json` della libreria
  standard).

**Non obiettivi**
- Modificare il catalogo (aggiunte, prestiti, scarico quantità): le scritture arrivano con
  l'esercizio delle note.
- Ricerca «intelligente» (sinonimi, errori di battitura, embedding/RAG).
- Formato CSV: si sceglie solo JSON.
- Esporre il catalogo via MCP o API.

**Anti-obiettivi** (fallimento anche se «funziona»)
- Un risultato vuoto restituito come stringa vuota o lista vuota muta, che lascia il modello
  libero di inventare.
- Il modello risponde con articoli, quantità o posizioni non presenti nel file.
- Un file catalogo malformato che viene accettato in silenzio (articoli scartati, codici duplicati).
- Grafo modificato nella forma: nodi e instradamento restano quelli attuali.

## 3. Vincoli

Valgono tutti quelli del `CLAUDE.md` di `lezione_4/`: codice sincrono, moduli piccoli, test
senza modello attivo, prove LM Studio separate e attivate esplicitamente, comandi PowerShell,
README aggiornato con soli comandi verificati, Conventional Commits in italiano.

## 4. Dati

File: `assistente/dati/catalogo.json` (dentro il pacchetto, quindi già copiato nell'immagine
Docker da `COPY assistente/ assistente/`). Struttura: lista di oggetti.

| Campo | Tipo | Esempio |
|-------|------|---------|
| `codice` | stringa, unica, formato `AAA-000` | `SEN-004` |
| `nome` | stringa non vuota | `Sensore di temperatura e umidità DHT22` |
| `categoria` | stringa, da un elenco chiuso | `sensori` |
| `descrizione` | stringa non vuota | `Misura temperatura (-40…80 °C) e umidità relativa.` |
| `quantita` | intero ≥ 0 | `6` |
| `posizione` | stringa non vuota | `Armadio B, ripiano 2` |

Categorie (elenco chiuso, minuscole): `schede`, `sensori`, `attuatori`, `cavi`,
`alimentazione`, `strumenti di misura`.

Prefissi dei codici: `SCH` schede, `SEN` sensori, `ATT` attuatori, `CAV` cavi,
`ALI` alimentazione, `MIS` strumenti di misura.

I dati devono rendere possibili gli esempi del §1: almeno un sensore di temperatura, un articolo
`SEN-004` che sia il sensore di umidità (DHT22), nessuna stampante 3D.

**Validazione al caricamento.** Il file si legge una volta all'avvio e si controllano **tutti**
i vincoli della tabella (scelta mia: un file malformato non deve passare in silenzio). È un
errore se:
- il file manca o non è JSON valido;
- il contenuto non è una lista, oppure è una lista vuota;
- un articolo non è un oggetto, ha campi mancanti o campi in più;
- un campo testuale non è una stringa o è vuoto (anche solo spazi);
- il codice non rispetta `AAA-000` o il prefisso non corrisponde alla categoria;
- la categoria è fuori elenco;
- la quantità non è un intero (i booleani non valgono) o è negativa;
- due articoli hanno lo stesso codice.

L'errore riporta il motivo e l'articolo coinvolto (posizione nella lista e, se c'è, il codice);
l'assistente non parte e stampa il messaggio, come per gli altri errori di avvio.

## 5. Strumenti

Le funzioni di ricerca e dettaglio sono **pure** (ricevono il catalogo già caricato), testate a
parte; i tool LangChain sono un involucro sottile. Restituiscono testo, come gli strumenti
esistenti.

### `cerca_articoli(testo: str = "", categoria: str = "")`

Descrizione per il modello: cerca articoli del catalogo per parole e/o categoria; restituisce un
elenco breve con codice, nome e quantità; per i dettagli (descrizione, posizione) usare
`dettaglio_articolo` con il codice.

- Confronto per **sottostringa**, senza distinzione di maiuscole (`casefold`) né di accenti
  (`unicodedata`, libreria standard: «umidita» trova «umidità»), su nome, descrizione e
  categoria uniti in un unico testo.
- Più parole nel testo: un articolo corrisponde se contiene **tutte** le parole, anche in campi
  diversi (una nel nome, un'altra nella descrizione).
- Niente gestione di singolari e plurali (la ricerca intelligente è un non obiettivo). Per
  ridurre i falsi «nessun risultato», la descrizione del tool chiede al modello di usare una o
  due parole chiave brevi, al singolare (scelta mia).
- `categoria` facoltativa: se indicata deve essere una delle categorie (senza distinzione di
  maiuscole); altrimenti errore che elenca le categorie valide.
- Testo e categoria entrambi vuoti → errore che chiede di indicare almeno uno dei due.
- Ordine: per codice. Al massimo 10 risultati; se ce ne sono di più, una riga finale dice quanti
  sono stati omessi e suggerisce di restringere la ricerca.
- Articoli a quantità 0 compaiono, segnalati come esauriti.
- **Nessun risultato** → messaggio esplicito, per esempio
  `Nessun articolo trovato per "stampante 3d". Il catalogo non contiene articoli corrispondenti.`

### `dettaglio_articolo(codice: str)`

Descrizione per il modello: restituisce la scheda completa di un articolo dato il suo codice
(per esempio `SEN-004`); se non si conosce il codice, usare prima `cerca_articoli`.

- Codice normalizzato (spazi tolti, maiuscolo) prima del confronto.
- Scheda: tutti i campi del §4, in righe `campo: valore`.
- **Codice inesistente** → `Codice non trovato: "XYZ-999". Usa cerca_articoli per trovare il codice giusto.`

## 6. Collegamento

- `crea_strumenti` (in `assistente/strumenti.py`) riceve anche il catalogo e aggiunge i due tool;
  il catalogo viene caricato in `__main__` con gli altri passi di avvio.
- Prompt di sistema (`grafo.py`): una frase che dice di usare `cerca_articoli` per domande sul
  materiale del laboratorio e `dettaglio_articolo` per la scheda di un codice, e di non
  inventare articoli che gli strumenti non restituiscono.
- Grafo, cronologia e CLI invariati.

## 7. Test

Automatici (senza modello):
- caricamento del file reale valido; un caso per ogni errore di validazione del §4;
- ricerca: per parola, più parole, categoria, maiuscole, nessun risultato, categoria non valida,
  entrambi vuoti, troncamento a 10, articolo esaurito;
- dettaglio: codice esistente, codice in minuscolo/con spazi, codice inesistente;
- i due tool compaiono in `crea_strumenti` con nome e descrizione;
- un test del grafo con modello simulato che chiama `cerca_articoli` e poi `dettaglio_articolo`,
  per verificare che il programma li esegua davvero e passi i risultati al modello.

Prova reale con LM Studio (marcatore `lmstudio`, opzione `--lmstudio`): le cinque domande del §1
(scelta mia sul livello di rigore):
- **asserzioni** sulle chiamate agli strumenti lette dai messaggi: nome del tool, e dove conta
  l'argomento (`SEN-004`, `XYZ-999`); per la domanda 3, `cerca_articoli` seguito da
  `dettaglio_articolo` con un codice restituito dalla ricerca; per la domanda 4, risultato dello
  strumento con «Nessun articolo trovato»;
- la **risposta finale** viene stampata (`-s`) e giudicata a mano («senza inventare» non si
  verifica con una sottostringa); nel resoconto si distingue ciò che è provato dalle asserzioni
  da ciò che è stato controllato a occhio.

Se il modello cerca con una forma flessa e non trova nulla, la prova fallisce: si corregge la
descrizione del tool o il prompt, non i dati per farli combaciare con una sola domanda.
Docker: test nel container e una domanda sul catalogo da pipe.

## 8. Documentazione

README: sezione sul catalogo (dove sta il file, campi, categorie, esempi di domande), voci
nuove nella checklist manuale, eventuali nuovi comandi solo se verificati.
