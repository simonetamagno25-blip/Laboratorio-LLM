# Lezione 7 · Esercizio 1: ingestion e ricerca semantica — piano di implementazione

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Obiettivo:** pacchetto `rag/` che indicizza in Qdrant le 790 ricette di Artusi in modo ripetibile
e le interroga con ricerca top-k e filtro per capitolo, più una valutazione su domande con fonte
attesa.

**Architettura:** un modulo per passo della pipeline (`config`, `corpus`, `chunking`, `embedding`,
`indice`) e tre comandi (`ingestion`, `ricerca`, `valuta`). Embedding con chiamate dirette `httpx`
a `/v1/embeddings` di LM Studio; Qdrant con `qdrant-client`. I test usano un embedder finto e
`QdrantClient(":memory:")`.

**Stack:** Python 3.14 (venv) / 3.12.15 (Docker), `httpx` 0.28.1 (già presente),
`qdrant-client` 1.20.0 (nuova), `qdrant/qdrant:v1.20.2`, pytest 9.1.1.

**Specifica:** `docs/superpowers/specs/2026-11-17-rag-ingestion-design.md`

## Vincoli globali
- Solo dentro `lezione_4/`, branch `feat/rag`. Codice sincrono, moduli piccoli, docstring e
  messaggi in italiano come nel resto del progetto.
- Unica dipendenza nuova: `qdrant-client==1.20.0` in `requirements.txt`.
- `rag/` non importa nulla da `assistente/` e non richiede le variabili dell'agente.
- Configurazione non valida o argomenti non validi → messaggio su stderr, uscita **2**. Servizi
  non raggiungibili o in errore (LM Studio, Qdrant), corpus mancante o non valido → messaggio su
  stderr, uscita **1**. Mai un traceback per questi casi.
- Valori fissati dalla specifica: `CHUNK_DIMENSIONE=1200`, `CHUNK_OVERLAP=200`,
  `CHUNK_STRATEGIA=paragrafi`, `EMBEDDING_LOTTO=32`, `RAG_TOP_K=5`, `TOP_K_MASSIMO = 20`
  (costante), `QDRANT_COLLEZIONE=ricette`, `QDRANT_URL=http://localhost:6333`,
  `PERCORSO_CORPUS=dati/artusi.txt`, 790 ricette, 23 capitoli, distanza coseno.
- Metadati della collezione: chiavi esatte `modello_embedding` e `dimensione`.
- Payload: chiavi esatte `documento_id`, `numero`, `titolo`, `capitolo`, `posizione`, `testo`,
  `fonte`. `documento_id` = `ricetta-089` (tre cifre).
- Identificativo reale del modello (verificato con `GET /v1/models`):
  `text-embedding-nomic-embed-text-v1.5`, vettori di 768 dimensioni. Va solo nel `.env` e
  nell'esempio, mai nel codice.
- Pytest raccoglie le funzioni importate il cui nome inizia con `test` (es.
  `testo_da_indicizzare`): nei test importare il **modulo** (`from rag import chunking`).
- Commit Conventional Commits in italiano, terminati da
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`; prima di ogni commit `git status`,
  diff, staging selettivo, `git commit -- <percorsi>`. **Nessun push**: dopo ogni commit scrivere
  «ho fatto il commit» e attendere l'ok dell'utente.
- Comandi da PowerShell in `lezione_4/` con `.\.venv\Scripts\python`. La suite completa
  (`.\.venv\Scripts\python -m pytest -q`) deve restare verde a ogni commit.

## Review Focus
1. **File del corpus scaricato da un'altra fonte o su Windows** (link della slide `pg59047.txt`
   oppure mirror `59047-0.txt`; BOM; righe CRLF): marcatori `*** START OF THIS …` / `*** START OF
   THE …` entrambi riconosciuti, BOM e `\r\n` gestiti → stesso risultato. Test nel Task 2.
2. **Testo introduttivo di un capitolo** (es. la lettera dopo `TORTE E DOLCI AL CUCCHIAIO`, prima
   della ricetta 637): non deve finire attaccato alla ricetta precedente. Test nel Task 2.
3. **Qdrant spento o `QDRANT_URL` sbagliato**: uscita 1 con un messaggio che nomina l'URL, senza
   traceback e senza calcolare embedding. Test nei Task 6 e 7.
4. **Ricerca prima di qualsiasi ingestion** (collezione assente): messaggio «eseguire prima
   l'ingestion», uscita 1. Test nel Task 7.
5. **Modello di embedding non caricato in LM Studio** (risposta HTTP di errore con JSON
   `{"error": …}`): messaggio che nomina modello e URL, uscita 1. Test nel Task 4.

---

### Task 1: Dipendenza e configurazione

**Files:**
- Modify: `requirements.txt` (aggiungere `qdrant-client==1.20.0`), `.env.example`
- Create: `rag/__init__.py` (docstring di una riga), `rag/config.py`
- Test: `tests/test_rag_config.py`

**Interfaces:**
- Produces:
  - `rag.config.TOP_K_MASSIMO: int = 20`, `rag.config.STRATEGIE = ("paragrafi", "finestra")`
  - `class ErroreConfigurazione(ValueError)`
  - `@dataclass(frozen=True) class ConfigurazioneRag`: `base_url: str | None`,
    `modello_embedding: str | None`, `qdrant_url: str`, `collezione: str`, `percorso_corpus: str`,
    `strategia: str`, `dimensione: int`, `overlap: int`, `lotto: int`, `top_k: int`
  - `carica_configurazione_rag(env: Mapping[str, str] | None = None, *, servizi: bool = True) -> ConfigurazioneRag`
    — con `servizi=False` (`--solo-analisi`) `LMSTUDIO_BASE_URL` e `LMSTUDIO_EMBEDDING_MODEL`
    non sono richieste (restano `None`).

- [ ] **Step 1: Installare la dipendenza**

Aggiungere `qdrant-client==1.20.0` a `requirements.txt`, poi
`.\.venv\Scripts\python -m pip install -r requirements-dev.txt`.
Atteso: `.\.venv\Scripts\python -c "import qdrant_client; print(qdrant_client.__version__)"` → `1.20.0`.

- [ ] **Step 2: Scrivere i test che falliscono** in `tests/test_rag_config.py`

```python
from rag import config

BASE = {"LMSTUDIO_BASE_URL": "http://localhost:1234/v1",
        "LMSTUDIO_EMBEDDING_MODEL": "text-embedding-nomic-embed-text-v1.5"}

def test_predefiniti():
    c = config.carica_configurazione_rag(BASE)
    assert (c.qdrant_url, c.collezione, c.percorso_corpus) == ("http://localhost:6333", "ricette", "dati/artusi.txt")
    assert (c.strategia, c.dimensione, c.overlap, c.lotto, c.top_k) == ("paragrafi", 1200, 200, 32, 5)
    assert config.TOP_K_MASSIMO == 20

def test_servizi_obbligatori_solo_se_richiesti():
    with pytest.raises(config.ErroreConfigurazione, match="LMSTUDIO_EMBEDDING_MODEL"):
        config.carica_configurazione_rag({"LMSTUDIO_BASE_URL": "http://x/v1"})
    c = config.carica_configurazione_rag({}, servizi=False)
    assert c.modello_embedding is None and c.base_url is None

@pytest.mark.parametrize("nome,valore", [
    ("CHUNK_STRATEGIA", "frasi"), ("CHUNK_DIMENSIONE", "0"), ("CHUNK_DIMENSIONE", "abc"),
    ("CHUNK_OVERLAP", "1200"), ("CHUNK_OVERLAP", "-1"), ("EMBEDDING_LOTTO", "0"),
    ("RAG_TOP_K", "21"), ("RAG_TOP_K", "0"), ("QDRANT_URL", "localhost:6333"),
])
def test_valori_non_validi(nome, valore):
    with pytest.raises(config.ErroreConfigurazione, match=nome):
        config.carica_configurazione_rag({**BASE, nome: valore})
```
(`CHUNK_OVERLAP` deve essere `0 ≤ overlap < CHUNK_DIMENSIONE`; `QDRANT_URL` schema http/https
con host. `LMSTUDIO_BASE_URL` senza `/` finale.)

- [ ] **Step 3: Verificare che falliscano** — `.\.venv\Scripts\python -m pytest tests/test_rag_config.py -v` → FAIL (`ModuleNotFoundError: rag`).

- [ ] **Step 4: Implementare `rag/config.py`** seguendo lo stile di `assistente/config.py`
(funzioni `_obbligatoria`, `_intero_positivo` locali, non importate).

- [ ] **Step 5: Aggiornare `.env.example`** con un blocco commentato «RAG (lezione 7)» contenente
tutte le variabili della tabella della specifica e `LMSTUDIO_EMBEDDING_MODEL=text-embedding-nomic-embed-text-v1.5`
con il commento «identificativo restituito da GET /v1/models». Aggiungere le stesse righe al
`.env` locale (non versionato).

- [ ] **Step 6: Test verdi** — stesso comando → PASS; suite completa verde.

- [ ] **Step 7: Commit** — `git commit -- requirements.txt .env.example rag/__init__.py rag/config.py tests/test_rag_config.py`
con messaggio `feat(rag): configurazione e dipendenza qdrant-client`.

---

### Task 2: Corpus — caricamento, pulizia, validazione

**Files:**
- Create: `rag/corpus.py`, `tests/fakes_rag.py` (costante `ESTRATTO`)
- Test: `tests/test_rag_corpus.py`

**Interfaces:**
- Produces:
  - `NUMERO_RICETTE = 790`
  - `CAPITOLI: tuple[str, ...]` — esattamente, in quest'ordine (forma leggibile del payload):
    `"Brodi, gelatina e sughi", "Minestre in brodo", "Minestre asciutte e di magro", "Principii",
    "Salse", "Uova", "Paste e pastelle", "Ripieni", "Fritti", "Lesso", "Tramessi", "Umidi",
    "Rifreddi", "Erbaggi e legumi", "Piatti di pesce", "Arrosti", "Pasticceria",
    "Torte e dolci al cucchiaio", "Siroppi", "Conserve", "Liquori", "Gelati", "Cose diverse"`
    (verificato sul file: prima ricetta di ciascuno 1, 7, 55, 108, 119, 139, 153, 160, 162, 226,
    227, 253, 360, 376, 455, 521, 559, 637, 723, 732, 746, 753, 776)
  - `@dataclass(frozen=True) class Ricetta`: `numero: int`, `titolo: str`, `capitolo: str`,
    `paragrafi: tuple[str, ...]`
  - `class ErroreCorpus(ValueError)`
  - `leggi_ricette(testo: str) -> list[Ricetta]` — nessuna validazione di conteggio
  - `valida_ricette(ricette: Sequence[Ricetta], numero_atteso: int = NUMERO_RICETTE, capitoli_attesi: int = len(CAPITOLI)) -> None`
  - `carica_corpus(percorso: str | Path) -> list[Ricetta]` — legge (`utf-8-sig`), chiama
    `leggi_ricette` e `valida_ricette`; file mancante → `ErroreCorpus` che nomina il percorso
  - `normalizza_capitolo(nome: str) -> str` — confronto senza maiuscole e spazi ai bordi con
    `CAPITOLI`; sconosciuto → `ValueError` con l'elenco dei capitoli validi

Regole di lettura (dalla specifica, più due decisioni del piano marcate ★):
- testo tra la riga che inizia con `*** START OF` e quella che inizia con `*** END OF`; `\r\n` → `\n`;
- dentro, solo da la riga `RICETTE` (esatta, dopo `strip`) alla riga `APPENDICE` esclusa;
- capitolo = riga che, dopo `strip`, è tutta maiuscola e uguale a `nome.upper()` di un elemento di
  `CAPITOLI`; i capitoli devono comparire nell'ordine di `CAPITOLI`;
- ricetta = riga `^(\d{1,3})\. (\S.*)$` con numero = precedente + 1 (la prima è 1); titolo = gruppo 2 con `strip`;
- ★ a una riga di capitolo la ricetta corrente si chiude; il testo fino alla ricetta successiva
  (introduzione del capitolo) è scartato e il numero di paragrafi scartati va nel log DEBUG;
- ★ `SOVRATITOLI = ("MINESTRE",)`: una riga uguale a un sovratitolo chiude la ricetta corrente
  come un capitolo, senza cambiare capitolo; la sua introduzione (due paragrafi sulla minestra,
  prima di `MINESTRE IN BRODO`) è scartata. Senza questa regola finirebbe nella ricetta 6;
- paragrafi separati da righe vuote; righe dello stesso paragrafo unite con uno spazio; `_`
  rimossi; caratteri di controllo rimossi; spazi multipli ridotti a uno;
- ★ le righe maiuscole che non sono capitoli restano paragrafi della ricetta.

- [ ] **Step 1: Scrivere `ESTRATTO` in `tests/fakes_rag.py`** — stringa con: BOM iniziale,
intestazione, marcatore `*** START OF THIS PROJECT GUTENBERG EBOOK LA SCIENZA IN CUCINA ***`,
`PREFAZIO` con un paragrafo, `RICETTE`, `BRODI, GELATINA E SUGHI`, ricetta `1. Brodo` (un
paragrafo su due righe «Il brodo si fa con carne di manzo» / «e acqua fredda.» e un elenco
rientrato «  Manzo, grammi 500.» / «  Acqua, litri 2.»), ricetta `2. Gelatina` (paragrafo su due
righe «Per la gelatina vedi il N. 1 e» / «10. passaggi da non confondere.»), `MINESTRE` con un
paragrafo «Introduzione alle minestre.», `MINESTRE IN BRODO`, ricetta `3. Cappelletti all'uso di Romagna` (paragrafo «A un mangiatore
_discreto_ bastano due dozzine.», paragrafo `RICETTA DI DETTA ZUPPA`, paragrafo «Testo interno
alla ricetta.»), `TORTE E DOLCI AL CUCCHIAIO`, paragrafo «Lettera di un ammiratore.», ricetta
`4. Torta di noci` («Noci e zucchero.»), `APPENDICE`, `CUCINA PER GLI STOMACHI DEBOLI`,
`5. Non è del ricettario`, marcatore `*** END OF THIS PROJECT GUTENBERG EBOOK ***`, licenza.

- [ ] **Step 2: Scrivere i test che falliscono** in `tests/test_rag_corpus.py`

```python
from rag import corpus
from tests.fakes_rag import ESTRATTO

def test_ricette_dell_estratto():
    r = corpus.leggi_ricette(ESTRATTO)
    assert [x.numero for x in r] == [1, 2, 3, 4]
    assert r[0] == corpus.Ricetta(1, "Brodo", "Brodi, gelatina e sughi",
        ("Il brodo si fa con carne di manzo e acqua fredda.", "Manzo, grammi 500. Acqua, litri 2."))
    assert r[1].paragrafi == ("Per la gelatina vedi il N. 1 e 10. passaggi da non confondere.",)
    # niente sovratitolo MINESTRE né la sua introduzione
    assert r[2].capitolo == "Minestre in brodo"
    assert r[2].paragrafi == ("A un mangiatore discreto bastano due dozzine.",
                              "RICETTA DI DETTA ZUPPA", "Testo interno alla ricetta.")
    assert r[3].capitolo == "Torte e dolci al cucchiaio"
    assert r[3].paragrafi == ("Noci e zucchero.",)          # niente lettera, niente appendice

def test_crlf_e_marcatori_alternativi():
    variante = ESTRATTO.replace("START OF THIS", "START OF THE").replace("\n", "\r\n")
    assert corpus.leggi_ricette(variante) == corpus.leggi_ricette(ESTRATTO)

def test_validazione():
    r = corpus.leggi_ricette(ESTRATTO)
    corpus.valida_ricette(r, numero_atteso=4, capitoli_attesi=3)
    with pytest.raises(corpus.ErroreCorpus, match="4"):
        corpus.valida_ricette(r[:3], numero_atteso=4, capitoli_attesi=3)
    with pytest.raises(corpus.ErroreCorpus, match="2"):
        corpus.valida_ricette([r[0], r[2], r[3]], numero_atteso=3, capitoli_attesi=3)  # buco: manca la 2

def test_file_mancante(tmp_path):
    with pytest.raises(corpus.ErroreCorpus, match="non_esiste.txt"):
        corpus.carica_corpus(tmp_path / "non_esiste.txt")

def test_normalizza_capitolo():
    assert corpus.normalizza_capitolo("  fritti ") == "Fritti"
    with pytest.raises(ValueError, match="Cose diverse"):
        corpus.normalizza_capitolo("Dolci")

@pytest.mark.skipif(not Path("dati/artusi.txt").exists(), reason="corpus non scaricato")
def test_corpus_reale():
    r = corpus.carica_corpus("dati/artusi.txt")
    assert len(r) == 790 and len({x.capitolo for x in r}) == 23
    assert (r[88].titolo, r[88].capitolo) == ("Gnocchi di patate", "Minestre asciutte e di magro")
    assert r[207].capitolo == "Fritti" and r[636].capitolo == "Torte e dolci al cucchiaio"
    assert sum(len(p) for p in r[789].paragrafi) < 3000      # niente appendice né indice
    assert not any("biada dell'uomo" in p for p in r[5].paragrafi)  # intro di MINESTRE scartata
```

- [ ] **Step 3: Verificare che falliscano** — `.\.venv\Scripts\python -m pytest tests/test_rag_corpus.py -v` → FAIL.

- [ ] **Step 4: Implementare `rag/corpus.py`** con le regole sopra. `valida_ricette` controlla:
numerazione 1..`numero_atteso` senza buchi (il messaggio nomina il primo numero mancante o il
conteggio trovato), numero di capitoli distinti, titoli e paragrafi non vuoti.

- [ ] **Step 5: Test verdi** — stesso comando → PASS (il test reale gira se `dati/artusi.txt`
c'è: scaricarlo ora con il comando del Task 9, Step 1).

- [ ] **Step 6: Commit** — `feat(rag): caricamento e pulizia del ricettario di Artusi`.

---

### Task 3: Chunking

**Files:**
- Create: `rag/chunking.py`
- Test: `tests/test_rag_chunking.py`

**Interfaces:**
- Consumes: `corpus.Ricetta`
- Produces:
  - `@dataclass(frozen=True) class Chunk`: `documento_id: str`, `numero: int`, `titolo: str`,
    `capitolo: str`, `posizione: int`, `testo: str`
  - `documento_id(numero: int) -> str` → `"ricetta-089"`
  - `dividi_ricetta(ricetta: Ricetta, strategia: str, dimensione: int, overlap: int) -> list[Chunk]`
  - `dividi_corpus(ricette: Sequence[Ricetta], strategia: str, dimensione: int, overlap: int) -> list[Chunk]`
  - `testo_da_indicizzare(chunk: Chunk) -> str` — oggi restituisce `chunk.testo` (punto di
    aggancio della modifica B)

Algoritmo `paragrafi` (il testo di un chunk è la concatenazione delle sue unità con `"\n\n"`, e la
lunghezza si misura su quella stringa):
1. Unità = paragrafi. Un paragrafo più lungo di `dimensione` si sostituisce con pezzi ≤ `dimensione`
   ottenuti accorpando frasi (taglio dopo `.`, `!`, `?`, `;`, `:` seguiti da spazio); una frase
   più lunga di `dimensione` si spezza a finestra all'ultimo spazio.
2. Si aggiungono unità al chunk finché la lunghezza resta ≤ `dimensione`; altrimenti si chiude
   il chunk.
3. Il chunk successivo parte con il suffisso più lungo di unità **intere** del chunk chiuso la cui
   lunghezza è ≤ `overlap`, purché sia più corto del chunk intero (altrimenti nessun overlap); se
   overlap + nuova unità supera `dimensione`, si tolgono unità di overlap dall'inizio.

Algoritmo `finestra`: sul testo della ricetta (paragrafi uniti con `"\n\n"`), finestre di al più
`dimensione` caratteri; il taglio si sposta indietro all'ultimo spazio bianco; la finestra
successiva inizia `overlap` caratteri prima del taglio, spostata avanti al primo inizio di parola.
Nessuna parola spezzata se non è più lunga della finestra.

- [ ] **Step 1: Scrivere i test che falliscono** in `tests/test_rag_chunking.py`

```python
from rag import chunking
from rag.corpus import Ricetta

def ricetta(*paragrafi):
    return Ricetta(89, "Gnocchi di patate", "Minestre asciutte e di magro", tuple(paragrafi))

def par(lettera, n):           # paragrafo di n caratteri fatto di parole
    return " ".join([lettera * 9] * (n // 10))[:n].strip()

def test_ricetta_breve_un_solo_chunk():
    [c] = chunking.dividi_ricetta(ricetta("Uno.", "Due."), "paragrafi", 1200, 200)
    assert c == chunking.Chunk("ricetta-089", 89, "Gnocchi di patate",
                               "Minestre asciutte e di magro", 0, "Uno.\n\nDue.")

def test_paragrafi_interi_e_overlap():
    p1, p2, p3, p4 = par("a", 500), par("b", 500), par("c", 150), par("d", 500)
    cs = chunking.dividi_ricetta(ricetta(p1, p2, p3, p4), "paragrafi", 1200, 200)
    assert [c.testo for c in cs] == ["\n\n".join([p1, p2, p3]), "\n\n".join([p3, p4])]
    assert [c.posizione for c in cs] == [0, 1]

def test_paragrafo_gigante_spezzato_per_frasi():
    frasi = [f"Frase numero {i} " + "x" * 80 + "." for i in range(40)]
    cs = chunking.dividi_ricetta(ricetta(" ".join(frasi)), "paragrafi", 1200, 200)
    assert len(cs) > 1 and all(len(c.testo) <= 1200 for c in cs)
    assert all(c.testo.endswith(".") for c in cs)

def test_frase_senza_punteggiatura_piu_lunga_della_dimensione():
    cs = chunking.dividi_ricetta(ricetta(par("z", 3000)), "paragrafi", 1200, 0)
    assert all(len(c.testo) <= 1200 for c in cs)
    assert " ".join(c.testo for c in cs).split() == par("z", 3000).split()

def test_finestra():
    testo = " ".join(f"parola{i}" for i in range(600))
    cs = chunking.dividi_ricetta(ricetta(testo), "finestra", 1200, 200)
    assert len(cs) > 1 and all(len(c.testo) <= 1200 for c in cs)
    assert all(set(c.testo.split()) <= set(testo.split()) for c in cs)
    for a, b in zip(cs, cs[1:]):
        assert b.testo.split()[0] in a.testo.split()     # c'è overlap

def test_corpus_non_attraversa_le_ricette():
    r1 = Ricetta(1, "A", "Brodi, gelatina e sughi", ("x" * 50,))
    r2 = Ricetta(2, "B", "Brodi, gelatina e sughi", ("y" * 50,))
    cs = chunking.dividi_corpus([r1, r2], "paragrafi", 1200, 200)
    assert [(c.documento_id, c.posizione) for c in cs] == [("ricetta-001", 0), ("ricetta-002", 0)]

def test_testo_da_indicizzare_coincide_con_il_testo():
    [c] = chunking.dividi_ricetta(ricetta("Uno."), "paragrafi", 1200, 200)
    assert chunking.testo_da_indicizzare(c) == "Uno."
```

- [ ] **Step 2: Verificare che falliscano** — `.\.venv\Scripts\python -m pytest tests/test_rag_chunking.py -v` → FAIL.
- [ ] **Step 3: Implementare `rag/chunking.py`.** Strategia sconosciuta → `ValueError`.
- [ ] **Step 4: Test verdi** — stesso comando → PASS.
- [ ] **Step 5: Commit** — `feat(rag): chunking per paragrafi e a finestra`.

---

### Task 4: Embedding con LM Studio

**Files:**
- Create: `rag/embedding.py`; aggiungere `EmbedderFinto` a `tests/fakes_rag.py`
- Test: `tests/test_rag_embedding.py`, `tests/test_rag_lmstudio.py`

**Interfaces:**
- Produces:
  - `class Embedder(Protocol)`: attributo `modello: str`; `embed(self, testi: Sequence[str]) -> list[list[float]]`
  - `class ErroreEmbedding(RuntimeError)`
  - `class EmbedderLMStudio(base_url: str, modello: str, lotto: int = 32, *, client: httpx.Client | None = None, timeout: float = 120.0)`
    — `POST {base_url}/embeddings` con JSON `{"model": modello, "input": [...]}` a lotti; risultati
    riordinati per `index`; lista vuota → `[]` senza richieste. Errori di rete, stato HTTP ≥ 400
    (includendo `error.message` del JSON se presente) e risposte senza `data` coerente →
    `ErroreEmbedding` con modello e URL nel messaggio.
  - `tests/fakes_rag.EmbedderFinto(modello: str = "finto", dimensione: int = 64)`: vettore
    deterministico «bag of words»: per ogni parola minuscola di almeno 3 lettere
    (`[a-zàèéìòù]{3,}`) `v[int(md5(parola).hexdigest(), 16) % dimensione] += 1`; vettore nullo →
    `v[0] = 1`. Registra le chiamate in `self.chiamate: list[list[str]]`.

- [ ] **Step 1: Scrivere i test che falliscono** in `tests/test_rag_embedding.py` usando
`httpx.MockTransport`:
  - `test_lotti_e_ordine`: `lotto=2`, 5 testi → 3 richieste con `input` di 2, 2, 1 testi e
    `model` corretto; il trasporto risponde con gli `index` in ordine inverso; il risultato è
    nell'ordine dei testi.
  - `test_lista_vuota_nessuna_richiesta`.
  - `test_modello_non_caricato`: risposta 404 con `{"error": {"message": "model not found"}}` →
    `ErroreEmbedding` il cui messaggio contiene il modello, l'URL e `model not found`.
  - `test_server_spento`: il trasporto solleva `httpx.ConnectError` → `ErroreEmbedding` con l'URL.
  - `test_embedder_finto_deterministico`: stessi testi → stessi vettori; «gnocchi di patate» più
    vicino (coseno) a «patate per gli gnocchi» che a «pollo arrosto».

- [ ] **Step 2: Verificare che falliscano** — `.\.venv\Scripts\python -m pytest tests/test_rag_embedding.py -v` → FAIL.
- [ ] **Step 3: Implementare `rag/embedding.py` e `EmbedderFinto`.**
- [ ] **Step 4: Test verdi** — stesso comando → PASS.
- [ ] **Step 5: Prova reale** in `tests/test_rag_lmstudio.py`, `@pytest.mark.lmstudio`, saltata se
  mancano `LMSTUDIO_BASE_URL` o `LMSTUDIO_EMBEDDING_MODEL`: due testi → due vettori della stessa
  lunghezza > 0. Eseguire (con `.env` caricato e LM Studio acceso)
  `.\.venv\Scripts\python -m pytest tests/test_rag_lmstudio.py --lmstudio -m lmstudio -v` → PASS (768).
- [ ] **Step 6: Commit** — `feat(rag): embedding tramite LM Studio`.

---

### Task 5: Indice Qdrant

**Files:**
- Create: `rag/indice.py`
- Test: `tests/test_rag_indice.py`

**Interfaces:**
- Consumes: `chunking.Chunk`
- Produces:
  - `class ErroreIndice(RuntimeError)`; `ERRORI_QDRANT = (ResponseHandlingException, UnexpectedResponse)`
    (da `qdrant_client.http.exceptions`) — le eccezioni da intercettare nei comandi
  - `FONTE = "Artusi, La scienza in cucina e l'arte di mangiar bene (1891), Project Gutenberg n. 59047"`
  - `NAMESPACE_RAG = uuid.uuid5(uuid.NAMESPACE_URL, "https://www.gutenberg.org/ebooks/59047")`
  - `id_punto(documento_id: str, posizione: int) -> str` → `str(uuid5(NAMESPACE_RAG, f"{documento_id}:{posizione}"))`
  - `payload_chunk(chunk: Chunk) -> dict[str, object]` — le sette chiavi dei vincoli globali
  - `@dataclass(frozen=True) class Risultato`: `score: float`, `documento_id: str`, `numero: int`,
    `titolo: str`, `capitolo: str`, `posizione: int`, `testo: str`
  - `class Indice(client: QdrantClient, collezione: str)` con:
    - `esiste() -> bool`
    - `verifica_modello(modello: str) -> int` — collezione assente → `ErroreIndice` con «eseguire
      prima l'ingestion»; `modello_embedding` diverso → `ErroreIndice` che nomina i due modelli e
      dice di eliminare la collezione e reindicizzare; restituisce `dimensione`
    - `prepara(modello: str, dimensione: int) -> None` — crea se manca (coseno, metadati, indice
      keyword su `capitolo`); se esiste verifica modello e dimensione (`ErroreIndice` se diversa)
    - `conta() -> int` — `count(exact=True)`; 0 se la collezione non esiste
    - `scrivi(chunks: Sequence[Chunk], vettori: Sequence[Sequence[float]]) -> set[str]` — upsert a
      blocchi di 256 punti; restituisce gli ID scritti
    - `rimuovi_orfani(ids_validi: set[str]) -> int` — scorre tutti gli ID con `scroll` e cancella
      quelli fuori dall'insieme; restituisce quanti
    - `cerca(vettore: Sequence[float], k: int, filtri: Mapping[str, str | int | bool] | None = None) -> list[Risultato]`
      — `query_points` con `query_filter=Filter(must=[FieldCondition(key=…, match=MatchValue(value=…))])`
      per ogni filtro (filtro **dentro** la query)
  - `crea_indice(qdrant_url: str, collezione: str) -> Indice` — `QdrantClient(url=…, timeout=10)`

- [ ] **Step 1: Scrivere i test che falliscono** in `tests/test_rag_indice.py` (fixture:
`Indice(QdrantClient(":memory:"), "prova")`, chunk costruiti a mano, vettori da `EmbedderFinto`):
  - `test_id_stabili`: `id_punto("ricetta-089", 0)` uguale a sé stesso e diverso da `("ricetta-089", 1)`; è un UUID valido.
  - `test_payload_completo`: `payload_chunk(c)` ha esattamente le sette chiavi, `fonte == FONTE`.
  - `test_prepara_registra_modello`: dopo `prepara("finto", 64)`,
    `client.get_collection("prova").config.metadata == {"modello_embedding": "finto", "dimensione": 64}`
    e `verifica_modello("finto") == 64`.
  - `test_modello_diverso_bloccato`: `prepara("finto", 64)` poi `verifica_modello("altro")` e
    `prepara("altro", 64)` → `ErroreIndice` con `"finto"` e `"altro"` nel messaggio.
  - `test_dimensione_diversa_bloccata`: `prepara("finto", 64)` poi `prepara("finto", 32)` → `ErroreIndice`.
  - `test_collezione_assente`: `verifica_modello("finto")` → `ErroreIndice` con `"ingestion"`; `conta() == 0`.
  - `test_upsert_non_duplica`: `scrivi` due volte gli stessi 3 chunk → `conta() == 3`.
  - `test_rimuovi_orfani`: scrivi 3 chunk, `rimuovi_orfani` con gli ID dei primi 2 → restituisce 1, `conta() == 2`.
  - `test_filtro_capitolo`: 6 chunk, 3 in «Fritti» e 3 in «Arrosti»; `cerca(v, 5, {"capitolo": "Fritti"})`
    → 3 risultati tutti «Fritti»; senza filtro e `k=2` → 2 risultati, score decrescenti.

- [ ] **Step 2: Verificare che falliscano** — `.\.venv\Scripts\python -m pytest tests/test_rag_indice.py -v` → FAIL.
- [ ] **Step 3: Implementare `rag/indice.py`.** Verificato con 1.20.0 in `:memory:`: metadati
  (`create_collection(..., metadata=...)`, `get_collection(...).config.metadata`), upsert idempotente,
  `query_points` con `Filter`, `count(exact=True)`, `scroll` paginato (ID restituiti come `str`),
  `delete` con `PointIdsList`, `collection_exists`. `create_payload_index` in `:memory:` emette un
  `UserWarning` («Payload indexes have no effect in the local Qdrant»): è atteso, l'indice si
  verifica sul server nel Task 10; nei test filtrarlo con
  `@pytest.mark.filterwarnings("ignore:Payload indexes")`.
- [ ] **Step 4: Test verdi** — stesso comando → PASS.
- [ ] **Step 5: Commit** — `feat(rag): collezione Qdrant con ID stabili e modello registrato`.

---

### Task 6: Comando di ingestion

**Files:**
- Create: `rag/ingestion.py` (con `if __name__ == "__main__": raise SystemExit(main())`)
- Test: `tests/test_rag_ingestion.py`

**Interfaces:**
- Consumes: `carica_configurazione_rag`, `carica_corpus`, `dividi_corpus`, `testo_da_indicizzare`,
  `EmbedderLMStudio`, `Indice`, `crea_indice`, `id_punto`, `ERRORI_QDRANT`
- Produces:
  - `@dataclass(frozen=True) class Riepilogo`: `ricette: int`, `chunk: int`, `punti_prima: int`,
    `punti_dopo: int`, `rimossi: int`, `dimensione: int`
  - `esegui_ingestion(ricette: Sequence[Ricetta], embedder: Embedder, indice: Indice, strategia: str, dimensione: int, overlap: int) -> Riepilogo`
    — ordine: chunk → se l'indice esiste `verifica_modello(embedder.modello)` (**prima** degli
    embedding) → `punti_prima = conta()` → embedding di `testo_da_indicizzare` → `prepara` →
    `scrivi` → `rimuovi_orfani` → `conta()`
  - `statistiche_chunk(chunks: Sequence[Chunk]) -> str` — numero di chunk, lunghezza minima /
    mediana / massima, ricette con più di un chunk
  - `main(argv: Sequence[str] | None = None, env: Mapping[str, str] | None = None) -> int` —
    opzione `--solo-analisi` (configurazione con `servizi=False`, stampa `statistiche_chunk`, non
    contatta servizi); logging come `assistente/__main__.py` (`httpx` a WARNING)
- Righe di log INFO esatte (sono le evidenze):
  - `ingestion: <ricette> ricette, <chunk> chunk (strategia=<s>, dimensione=<d>, overlap=<o>)`
  - `ingestion: modello=<modello> dimensione_vettori=<n>`
  - `ingestion: punti prima=<p> dopo=<q> rimossi=<r> (<secondi> s)`

- [ ] **Step 1: Scrivere i test che falliscono** in `tests/test_rag_ingestion.py` (ricette = `leggi_ricette(ESTRATTO)`, indice `:memory:`, `EmbedderFinto`):
  - `test_due_ingestion_stesso_numero_di_punti`: due esecuzioni → `r2.punti_prima == r1.punti_dopo == r2.punti_dopo` e `r2.rimossi == 0`.
  - `test_cambio_chunking_rimuove_orfani`: prima con `dimensione=40, overlap=0`, poi con `1200, 200`
    → nella seconda `rimossi > 0` e `punti_dopo == ` numero di chunk della seconda configurazione.
  - `test_modello_diverso_bloccato_prima_degli_embedding`: dopo un'ingestion con «finto», un
    `EmbedderFinto(modello="altro")` → `ErroreIndice`, `altro.chiamate == []`, conteggio invariato.
  - `test_main_configurazione_non_valida`: `main([], {"CHUNK_DIMENSIONE": "0"})` → 2.
  - `test_main_corpus_mancante`: env valido con `PERCORSO_CORPUS` inesistente → 1, messaggio con il percorso (capsys).
  - `test_main_qdrant_spento`: env valido, corpus reale (skip se manca), `QDRANT_URL=http://127.0.0.1:9`,
    `LMSTUDIO_BASE_URL=http://127.0.0.1:9/v1` → 1, messaggio su stderr con `127.0.0.1:9`, nessun traceback.
  - `test_main_solo_analisi`: corpus reale (skip se manca), env vuoto tranne `PERCORSO_CORPUS` → 0,
    stdout contiene `chunk`.

- [ ] **Step 2: Verificare che falliscano** — `.\.venv\Scripts\python -m pytest tests/test_rag_ingestion.py -v` → FAIL.
- [ ] **Step 3: Implementare `rag/ingestion.py`.** (Verificato: con `qdrant-client` 1.20.0 una
  connessione rifiutata solleva `qdrant_client.http.exceptions.ResponseHandlingException`, in
  circa 4 s.) In `main`: `ErroreConfigurazione` → 2;
  `ErroreCorpus`, `ErroreEmbedding`, `ErroreIndice`, `ERRORI_QDRANT` → messaggio (per Qdrant:
  «Qdrant non raggiungibile su <url>: avviarlo con docker compose up -d qdrant») e 1.
- [ ] **Step 4: Test verdi** — stesso comando → PASS; suite completa verde.
- [ ] **Step 5: Commit** — `feat(rag): comando di ingestion ripetibile`.

---

### Task 7: Comando di ricerca

**Files:**
- Create: `rag/ricerca.py`
- Test: `tests/test_rag_ricerca.py`

**Interfaces:**
- Consumes: `Indice`, `Risultato`, `Embedder`, `normalizza_capitolo`, `TOP_K_MASSIMO`
- Produces:
  - `cerca(domanda: str, embedder: Embedder, indice: Indice, k: int, capitolo: str | None = None) -> list[Risultato]`
    — `ValueError` se la domanda è vuota (dopo `strip`) o `k` fuori da `1..TOP_K_MASSIMO`;
    capitolo con `normalizza_capitolo`; `indice.verifica_modello(embedder.modello)` prima
    dell'embedding; domanda passata all'embedder **senza modifiche**
  - `formatta_risultati(risultati: Sequence[Risultato]) -> str` — per ciascuno una riga
    `<i>. score <0,777> · ricetta <N> «<titolo>» · <capitolo> · chunk <posizione>` seguita dal testo
    rientrato di 3 spazi; score con 3 decimali e virgola
  - `main(argv=None, env=None) -> int` — `python -m rag.ricerca "domanda" [--capitolo NOME] [--k N]`;
    `--k` predefinito `RAG_TOP_K`; `ValueError` → stderr e 2; errori dei servizi come nel Task 6 → 1

- [ ] **Step 1: Scrivere i test che falliscono** in `tests/test_rag_ricerca.py` (indice popolato con `esegui_ingestion` su `ESTRATTO`):
  - `test_risultati_con_fonte`: «brodo di manzo» → primo risultato ricetta 1, campi `capitolo` e `posizione` valorizzati.
  - `test_filtro_capitolo`: `capitolo="minestre in brodo"` → tutti i risultati con capitolo «Minestre in brodo», al massimo k.
  - `test_k_fuori_limite`: `k=0` e `k=21` → `ValueError` con `20` nel messaggio.
  - `test_domanda_vuota`: `"   "` → `ValueError`.
  - `test_capitolo_sconosciuto`: `"Dolci"` → `ValueError` con l'elenco.
  - `test_collezione_assente`: indice vuoto → `ErroreIndice` con «ingestion».
  - `test_domanda_non_modificata`: `embedder.chiamate[-1] == ["  Come si fa il brodo?  "]`.
  - `test_formatta`: un `Risultato(0.7774, "ricetta-089", 89, "Gnocchi di patate", "Minestre asciutte e di magro", 0, "testo")`
    → la prima riga è `1. score 0,777 · ricetta 89 «Gnocchi di patate» · Minestre asciutte e di magro · chunk 0`.
  - `test_main_qdrant_spento`: `main(["brodo"], env con QDRANT_URL=http://127.0.0.1:9 …)` → 1, nessun traceback.
  - `test_main_k_non_valido`: `main(["brodo", "--k", "50"], env)` → 2.

- [ ] **Step 2: Verificare che falliscano** — `.\.venv\Scripts\python -m pytest tests/test_rag_ricerca.py -v` → FAIL.
- [ ] **Step 3: Implementare `rag/ricerca.py`.**
- [ ] **Step 4: Test verdi** — stesso comando → PASS.
- [ ] **Step 5: Commit** — `feat(rag): ricerca top-k con filtro per capitolo`.

---

### Task 8: Valutazione con domande a fonte attesa

**Files:**
- Create: `rag/valuta.py`, `rag/domande.json`
- Test: `tests/test_rag_valuta.py`

**Interfaces:**
- Consumes: `ricerca.cerca`, `Risultato`
- Produces:
  - `@dataclass(frozen=True) class Domanda`: `testo: str`, `fonti: tuple[int, ...]`, `capitolo: str | None = None`
  - `@dataclass(frozen=True) class Esito`: `domanda: Domanda`, `filtrata: bool`,
    `posizione: int | None`, `score_fonte: float | None`, `score_migliore: float | None`
  - `carica_domande(percorso: str | Path) -> list[Domanda]`
  - `valuta(domanda: Domanda, risultati: Sequence[Risultato], filtrata: bool = False) -> Esito`
    — posizione (da 1) del primo risultato il cui `numero` è in `fonti`
  - `tabella(esiti: Sequence[Esito], intestazione: Mapping[str, object], k: int) -> str` —
    righe `chiave: valore` dell'intestazione (modello, strategia, dimensione, overlap, k, punti),
    poi tabella Markdown `| Domanda | Fonte attesa | Filtro | Posizione | Score fonte | Score migliore |`,
    poi `Fonte attesa trovata in X casi su Y (top-k = k).` contando solo le righe non filtrate con
    fonti. Celle: posizione `assente` se non trovata, `—` se la domanda non ha fonti; score con 3
    decimali e virgola; fonti `455, 456`.
  - `main(argv=None, env=None) -> int` — `--k` (predefinito `RAG_TOP_K`), `--output FILE`,
    `--domande` (predefinito `rag/domande.json`); per le domande con `capitolo` una seconda riga
    filtrata.

`rag/domande.json` — esattamente queste dieci (fonti verificate sul testo; le ultime quattro sono
nuove, scritte senza copiare le parole del libro):

| testo | fonti | capitolo |
|---|---|---|
| Quanta farina serve per 400 grammi di patate negli gnocchi? | [89] | |
| Che vino si usa per il pollo alla cacciatora? | [208] | Fritti |
| Come si chiama il cacciucco sulle coste dell'Adriatico? | [455, 456] | |
| Quanti cappelletti bastano a un mangiatore moderato? | [7] | |
| Perché gli gnocchi possono sciogliersi nell'acqua? | [89] | |
| Per quante persone bastano tre etti di vitello preparato alla romana con prosciutto e salvia? | [222] | |
| Che cosa pensano i bolognesi di chi serve la pasta all'uovo tagliata troppo corta? | [71] | |
| Quanti tuorli servono per la crema del dolce inglese fatto nello stampo? | [675] | |
| Qual è la ricetta del tiramisù? | [] | |
| Come si prepara la pasta alla carbonara? | [] | |

- [ ] **Step 1: Scrivere i test che falliscono** in `tests/test_rag_valuta.py`:
  - `test_posizione_e_score`: risultati con numeri `[5, 89, 3]` e score `[0.8, 0.7, 0.6]`, fonti `(89,)` → `posizione == 2`, `score_fonte == 0.7`, `score_migliore == 0.8`.
  - `test_fonte_assente`: fonti `(208,)` non presente → `posizione is None`; nella tabella la cella è `assente`.
  - `test_senza_fonti`: fonti `()` → cella posizione `—`, score migliore riportato.
  - `test_riepilogo`: 3 esiti non filtrati con fonti (2 trovati) + 1 filtrato + 1 senza fonti → riga `Fonte attesa trovata in 2 casi su 3 (top-k = 5).`
  - `test_score_con_virgola`: `0.7774` → `0,777` nella tabella.
  - `test_domande_del_repository`: `carica_domande("rag/domande.json")` → 10 domande, 8 con fonti, 2 senza; quella con capitolo ha `"Fritti"`.
  - `test_riproducibile`: indice `:memory:` con `ESTRATTO` ed `EmbedderFinto`, due valutazioni con un file di due domande scritto in `tmp_path` → tabelle identiche.

- [ ] **Step 2: Verificare che falliscano** — `.\.venv\Scripts\python -m pytest tests/test_rag_valuta.py -v` → FAIL.
- [ ] **Step 3: Implementare `rag/valuta.py` e scrivere `rag/domande.json`.**
- [ ] **Step 4: Test verdi** — stesso comando → PASS; suite completa verde.
- [ ] **Step 5: Commit** — `feat(rag): valutazione con domande a fonte attesa`.

---

### Task 9: Docker Compose

**Files:**
- Modify: `compose.yaml`, `Dockerfile` (aggiungere `COPY rag/ rag/`), `.dockerignore`
  (aggiungere `dati` e `slide lezioni`)

Servizi da aggiungere (gli altri restano invariati):

```yaml
  # Database vettoriale per il RAG (lezione 7). Profilo rag: non parte con `up` dell'applicazione;
  # avvio: docker compose up -d qdrant. Porta solo su 127.0.0.1 (nessuna chiave API).
  qdrant:
    image: qdrant/qdrant:v1.20.2
    profiles: ["rag"]
    ports:
      - "127.0.0.1:6333:6333"
    volumes:
      - dati_qdrant:/qdrant/storage

  # Comandi del RAG: docker compose run --rm rag python -m rag.ingestion
  rag:
    build: .
    profiles: ["rag"]
    command: ["python", "-m", "rag.ingestion"]
    env_file: .env
    environment:
      QDRANT_URL: http://qdrant:6333
      LMSTUDIO_BASE_URL: http://host.docker.internal:1234/v1
      PERCORSO_CORPUS: /app/dati/artusi.txt
    volumes:
      - ./dati:/app/dati:ro
    depends_on:
      - qdrant
    extra_hosts:
      - "host.docker.internal:host-gateway"
```
e `dati_qdrant:` sotto `volumes:`.

- [ ] **Step 1: Scaricare il corpus** (se non già fatto):
  `New-Item -ItemType Directory -Force dati; Invoke-WebRequest -Uri https://www.gutenberg.org/ebooks/59047.txt.utf-8 -OutFile dati\artusi.txt`
  (se gutenberg.org è in manutenzione: `-Uri https://gutenberg.pglaf.org/5/9/0/4/59047/59047-0.txt`).
  Atteso: `.\.venv\Scripts\python -m rag.ingestion --solo-analisi` → uscita 0 con le statistiche.
- [ ] **Step 2: Modificare `compose.yaml`, `Dockerfile`, `.dockerignore`.**
- [ ] **Step 3: Verificare la configurazione** — `docker compose config --quiet` → nessun errore;
  `docker compose --profile rag config --services` elenca anche `qdrant` e `rag`;
  `docker compose config --services` **non** li elenca.
- [ ] **Step 4: Avvio** (Docker Desktop acceso) — `docker compose up -d qdrant`, poi
  `docker compose ps` → `qdrant` attivo; `http://localhost:6333/dashboard` risponde.
- [ ] **Step 5: Test nel container** — `docker compose build assistente` e
  `docker compose run --rm assistente python -m pytest -q` → stesso esito della suite locale.
- [ ] **Step 6: Commit** — `build(rag): servizio Qdrant e comandi del RAG in Docker Compose`.

---

### Task 10: Prove reali, `docs/retrieval.md`, README e CLAUDE.md

**Files:**
- Create: `docs/retrieval.md`
- Modify: `README.md` (sezione «RAG (lezione 7)»), `CLAUDE.md` (sezione «Comandi»), `docs/ROADMAP.md`
  (sezione «Lezione 7» con le voci dell'esercizio 1 spuntate e A, B ancora aperte)

Ogni comando eseguito qui con il suo esito va riportato in `docs/retrieval.md`; nel README e nel
CLAUDE.md vanno **solo** comandi eseguiti con successo.

- [ ] **Step 1: Ingestion reale due volte** (LM Studio con il modello di embedding, Qdrant attivo,
  `.env` caricato): `.\.venv\Scripts\python -m rag.ingestion` due volte. Atteso: alla seconda
  `punti prima=P dopo=P rimossi=0`, con P uguale al dopo della prima. Registrare entrambe le righe.
- [ ] **Step 2: Ingestion nel container** — `docker compose run --rm rag` → stesso P, `rimossi=0`.
  Verificare sul server l'indice e i metadati:
  `Invoke-RestMethod http://localhost:6333/collections/ricette | ConvertTo-Json -Depth 6` → `payload_schema`
  contiene `capitolo` (keyword) e `config.metadata` contiene modello e `768`.
- [ ] **Step 3: Ricerca** — `.\.venv\Scripts\python -m rag.ricerca "Come si frigge il pollo?" --capitolo Fritti --k 3`
  → 3 risultati tutti «Fritti»; la stessa domanda senza filtro; una ricerca con `--capitolo Dolci` → errore e uscita 2.
- [ ] **Step 4: Valutazione di partenza** —
  `.\.venv\Scripts\python -m rag.valuta --output docs/valutazione-partenza.md`; eseguirla una seconda
  volta e verificare che l'output sia identico. Copiare la tabella in `docs/retrieval.md`.
- [ ] **Step 5: Scrivere `docs/retrieval.md`**: configurazione (modello, 768, strategia,
  dimensione, overlap, k); conteggi delle due ingestion; tabella di partenza; due query commentate
  (una riuscita con ricetta, capitolo e posizione del chunk; una mancata con la causa letta nel
  testo del chunk, per esempio la ricetta 208 senza la parola «cacciatora»); sezioni «Dopo la
  modifica A» e «Dopo la modifica B» con «da fare».
- [ ] **Step 6: README** — sezione «RAG (lezione 7)»: download del corpus, variabili del `.env`,
  `docker compose up -d qdrant`, i tre comandi in locale e in Docker, test, diagnosi (tabella
  degli errori tipici della slide 23 con il comando di controllo di ciascuno).
- [ ] **Step 7: CLAUDE.md** — nella sezione «Comandi» le righe verificate: download del corpus,
  `docker compose up -d qdrant`, `python -m rag.ingestion [--solo-analisi]`, `python -m rag.ricerca`,
  `python -m rag.valuta`, `docker compose run --rm rag`.
- [ ] **Step 8: Verifica finale** — suite completa verde
  (`.\.venv\Scripts\python -m pytest -q`), `git status` senza `dati/`, `.env` o slide.
- [ ] **Step 9: Commit** — `docs(rag): valutazione di partenza, README e comandi`.
