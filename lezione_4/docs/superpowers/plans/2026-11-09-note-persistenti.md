# Note persistenti — piano di implementazione

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** aggiungere all'assistente note personali su SQLite (`aggiungi_nota`, `elenca_note`, `cerca_note`, `elimina_nota`), con l'eliminazione confermata dall'utente tramite una pausa del grafo LangGraph.

**Architecture:** un modulo `assistente/note.py` con l'archivio SQLite (dati) e quattro funzioni che restituiscono testo; `strumenti.py` le avvolge come `StructuredTool`. Il grafo ha un nodo nuovo `conferma_eliminazione` che chiama `interrupt()`; con l'archivio il grafo è compilato con `InMemorySaver`. `Sessione` usa un `thread_id` nuovo per ogni domanda e tiene la cronologia nella sua lista come oggi; il ciclo del terminale gestisce la richiesta di conferma.

**Tech Stack:** Python 3.12 (container) / venv locale, libreria standard (`sqlite3`, `unicodedata`, `re`, `uuid`, `pathlib`), `langgraph` (`interrupt`, `Command`, `InMemorySaver`, già installati), `langchain_core`, pytest.

**Spec:** `docs/superpowers/specs/2026-11-09-note-persistenti-design.md`

## Global Constraints

- Nessuna nuova dipendenza: `requirements*.txt` invariati.
- Codice sincrono, moduli piccoli. Query SQLite sempre con parametri `?`; ogni scrittura con `commit` immediato.
- Connessione SQLite unica per archivio, aperta con `check_same_thread=False` (LangGraph può eseguire i nodi in un thread diverso).
- Variabile `PERCORSO_DB_NOTE`, facoltativa, predefinito `note.sqlite3`.
- Numero di nota `INTEGER PRIMARY KEY AUTOINCREMENT`: mai riusato.
- Data di creazione nel fuso `FUSO_ORARIO_PREDEFINITO`, salvata ISO 8601 con offset, mostrata `AAAA-MM-GG HH:MM`.
- Testo della nota: `strip()`, massimo 500 caratteri.
- Elenco e ricerca: al massimo 20 note, le più recenti, in ordine di numero crescente.
- Testi fissi (copiare esatti):
  - `Nota 3 salvata: <testo>`
  - `Errore: il testo della nota è vuoto.`
  - `Errore: la nota supera i 500 caratteri.`
  - `Non ci sono note salvate.`
  - `Errore: indica una o più parole da cercare; per vedere tutte le note usa elenca_note.`
  - `Nessuna nota trovata per "stampante". Non ci sono note corrispondenti.`
  - `Nota 7 non trovata. Usa cerca_note o elenca_note per trovare il numero giusto.`
  - `Nota 3 eliminata.`
  - `Eliminazione annullata dall'utente: la nota 3 non è stata eliminata.`
  - `Errore: elimina una nota alla volta.`
  - riga di una nota: `Nota 3 (2026-11-02 14:05): il sensore SEN-004 va ricalibrato`
  - domanda di conferma: `Eliminare la nota 3 (2026-11-02 14:05): "il sensore SEN-004 va ricalibrato"? [sì/no]`
  - prompt di lettura della conferma: `Conferma> `
  - errore di avvio: `Archivio note non disponibile: <motivo>`, codice di uscita 5.
- Conferma: `sì`, `si`, `s` (dopo `strip()` e `casefold()`) confermano; tutto il resto annulla.
- Garanzia: nessun percorso del grafo elimina una nota esistente senza una conferma registrata per quella chiamata.
- I test non creano mai `note.sqlite3` nella cartella del progetto: usano `tmp_path` o impostano `PERCORSO_DB_NOTE`.
- Comandi da PowerShell nella cartella `lezione_4/`; test con `.\.venv\Scripts\python -m pytest`.
- Conventional Commits in italiano; prima di ogni commit `git status`, diff, staging selettivo; dopo ogni commit avvisare l'utente; push solo su sua conferma.

## Review Focus

1. Il modello passa il numero come stringa (`{"numero": "1"}`), cosa frequente con modelli piccoli → la conferma compare lo stesso e con «sì» la nota viene eliminata. Test in Task 3.
2. Numero non valido (`0`, `-1`, `true`, `"tre"`) → nessuna pausa, nessuna eliminazione, risposta d'errore o «non trovata». Test in Task 3.
3. Testo della nota con apici, a capo o SQL (`'; DROP TABLE note; --`) → salvato e riletto identico, tabella intatta. Test in Task 1.
4. Risposta alla conferma con maiuscole, accento o spazi (`" Sì "`, `"S"`) → conferma; `"sìì"`, `"yes"`, `"ok"` → annulla. Test in Task 4.
5. Limite di lunghezza al confine: 500 caratteri accettati, 501 rifiutati; spazi esterni non contano. Test in Task 1.

---

### Task 1: archivio SQLite delle note e funzioni testuali

**Files:**
- Create: `assistente/testo.py` (normalizzazione condivisa)
- Modify: `assistente/catalogo.py` (usa `assistente/testo.py` al posto di `_normalizza` e di `re.findall(r"\w+", ...)`)
- Create: `assistente/note.py`
- Modify: `.gitignore`, `.dockerignore` (aggiungere `*.sqlite3` e `*.sqlite3-journal`)
- Test: `tests/test_note.py`

**Interfaces:**
- Produces:
  - `assistente/testo.py`: `normalizza(testo: str) -> str` (corpo identico all'attuale `_normalizza`), `parole(testo: str) -> list[str]` (`re.findall(r"\w+", normalizza(testo))`).
  - `assistente/note.py`:
    - `class ErroreArchivio(Exception)`
    - `@dataclass(frozen=True) class Nota: numero: int; testo: str; creata: datetime`
    - `MAX_CARATTERI = 500`, `MAX_RISULTATI = 20`
    - `class ArchivioNote` con `aggiungi(testo: str) -> Nota` (testo già validato), `tutte() -> list[Nota]` (ordine per numero), `leggi(numero: int) -> Nota | None`, `elimina(numero: int) -> bool`, `chiudi() -> None`
    - `apri_archivio(percorso: str | Path, fuso: str = "Europe/Rome", adesso: Callable[[], datetime] = <utc now>) -> ArchivioNote`; `":memory:"` ammesso (nessuna cartella creata). Crea la cartella genitore (`mkdir(parents=True, exist_ok=True)`), si connette, `CREATE TABLE IF NOT EXISTS note (...)`. `OSError` e `sqlite3.Error` → `ErroreArchivio` con il motivo.
    - `formatta_nota(nota: Nota) -> str` → riga fissa dei Global Constraints.
    - `aggiungi_nota(archivio, testo: str) -> str`, `elenca_note(archivio) -> str`, `cerca_note(archivio, testo: str) -> str`, `elimina_nota(archivio, numero: int) -> str`.
- Intestazioni dei risultati: `elenca_note` → `Note salvate: N` poi una riga per nota; `cerca_note` → `Note trovate: N` poi le righe. Oltre 20: le 20 più recenti e la riga finale `Altre K note non mostrate: usa cerca_note con parole più precise.`

- [ ] **Step 1: test che falliscono** in `tests/test_note.py`. Fixture `archivio(tmp_path)` = `apri_archivio(tmp_path / "note.sqlite3", "Europe/Rome", lambda: datetime(2026, 10, 26, 16, 5, 12, tzinfo=timezone.utc))`.

```python
def test_aggiunta_e_numero(archivio):
    assert aggiungi_nota(archivio, "  il sensore SEN-004 va ricalibrato  ") == "Nota 1 salvata: il sensore SEN-004 va ricalibrato"
    assert formatta_nota(archivio.leggi(1)) == "Nota 1 (2026-10-26 17:05): il sensore SEN-004 va ricalibrato"

def test_testo_vuoto_e_limite(archivio):
    assert aggiungi_nota(archivio, "   ") == "Errore: il testo della nota è vuoto."
    assert aggiungi_nota(archivio, " " + "a" * 500 + " ").startswith("Nota 1 salvata")
    assert aggiungi_nota(archivio, "a" * 501) == "Errore: la nota supera i 500 caratteri."

def test_testo_con_sql_e_a_capo(archivio):
    testo = "riga 1\nl'apice \"doppio\" '; DROP TABLE note; --"
    aggiungi_nota(archivio, testo)
    assert archivio.leggi(1).testo == testo and len(archivio.tutte()) == 1

def test_elenco(archivio):
    assert elenca_note(archivio) == "Non ci sono note salvate."
    # con 2 note: "Note salvate: 2" seguito dalle due righe in ordine di numero

def test_elenco_oltre_20(archivio):
    # 23 note: compaiono le note 4..23 e l'ultima riga è
    # "Altre 3 note non mostrate: usa cerca_note con parole più precise."

def test_ricerca(archivio):
    aggiungi_nota(archivio, "Il sensore di umidità va ricalibrato")
    aggiungi_nota(archivio, "Comprare cavi USB")
    assert "Nota 1" in cerca_note(archivio, "UMIDITA sensore")   # maiuscole, accenti, più parole
    assert "Nota 2" not in cerca_note(archivio, "sensore")
    assert cerca_note(archivio, "stampante") == 'Nessuna nota trovata per "stampante". Non ci sono note corrispondenti.'
    assert cerca_note(archivio, " ?! ") == "Errore: indica una o più parole da cercare; per vedere tutte le note usa elenca_note."

def test_eliminazione_e_numero_non_riusato(archivio):
    aggiungi_nota(archivio, "a"); aggiungi_nota(archivio, "b")
    assert elimina_nota(archivio, 2) == "Nota 2 eliminata."
    assert elimina_nota(archivio, 2) == "Nota 2 non trovata. Usa cerca_note o elenca_note per trovare il numero giusto."
    assert aggiungi_nota(archivio, "c") == "Nota 3 salvata: c"

def test_persistenza_tra_aperture(tmp_path):
    # apri, aggiungi, chiudi; riapri sullo stesso file: la nota 1 c'è con lo stesso testo e data

def test_file_non_database(tmp_path):
    (tmp_path / "x.sqlite3").write_bytes(b"non sono un database" * 100)
    with pytest.raises(ErroreArchivio): apri_archivio(tmp_path / "x.sqlite3")

def test_cartella_non_creabile(tmp_path):
    (tmp_path / "file").write_text("x")
    with pytest.raises(ErroreArchivio): apri_archivio(tmp_path / "file" / "note.sqlite3")

def test_cartella_creata_se_manca(tmp_path):
    apri_archivio(tmp_path / "nuova" / "note.sqlite3").chiudi()
    assert (tmp_path / "nuova" / "note.sqlite3").exists()
```

Ogni test chiude l'archivio (fixture con `yield` e `chiudi()`), altrimenti su Windows `tmp_path` non si cancella.

- [ ] **Step 2:** `.\.venv\Scripts\python -m pytest tests/test_note.py -v` → FAIL (modulo inesistente).
- [ ] **Step 3:** scrivere `assistente/testo.py` e `assistente/note.py` secondo le Interfaces; in `catalogo.py` sostituire `_normalizza`/`re.findall` con `normalizza`/`parole` senza cambiare comportamento. La ricerca legge `tutte()` e filtra in Python: una nota corrisponde se `all(p in normalizza(nota.testo) for p in parole(testo))`.
- [ ] **Step 4:** `.\.venv\Scripts\python -m pytest -v` → tutto verde (anche `tests/test_catalogo.py` invariato).
- [ ] **Step 5:** commit `feat(note): archivio SQLite con aggiunta, elenco, ricerca ed eliminazione` (file del task, `.gitignore`, `.dockerignore`).

### Task 2: configurazione e strumenti delle note

**Files:**
- Modify: `assistente/config.py`, `.env.example`, `assistente/strumenti.py`
- Test: `tests/test_config.py`, `tests/test_strumenti.py`

**Interfaces:**
- Consumes: Task 1 (`ArchivioNote`, le quattro funzioni testuali).
- Produces:
  - `Configurazione.percorso_db_note: str` (ultimo campo), da `PERCORSO_DB_NOTE` con `strip()`, vuoto → `"note.sqlite3"`.
  - `crea_strumenti(adesso=adesso_utc, catalogo=None, archivio: ArchivioNote | None = None) -> list[BaseTool]`: senza archivio la lista resta quella di oggi; con archivio aggiunge in coda `aggiungi_nota`, `elenca_note`, `cerca_note`, `elimina_nota` (in quest'ordine). Firma dei tool: `aggiungi_nota(testo: str)`, `elenca_note()`, `cerca_note(testo: str)`, `elimina_nota(numero: int)`.
  - Descrizioni per il modello (dal §5 della spec): `aggiungi_nota` «Salva una nota personale dell'utente, che resta disponibile anche nelle sessioni successive. Riporta il testo come l'utente l'ha detto.»; `elenca_note` «Elenca le note salvate dall'utente.»; `cerca_note` «Cerca tra le note salvate quelle che contengono tutte le parole indicate. Usa una o due parole chiave brevi, al singolare.»; `elimina_nota` «Elimina una nota dato il suo numero. Se non conosci il numero usa prima cerca_note o elenca_note. Il programma chiederà conferma all'utente prima di eliminare.»

- [ ] **Step 1: test che falliscono**
  - `test_config`: `percorso_db_note` vale `"note.sqlite3"` senza variabile e con variabile vuota; vale `"C:/x/n.sqlite3"` con `PERCORSO_DB_NOTE=" C:/x/n.sqlite3 "`.
  - `test_strumenti`: `test_senza_archivio_nessun_tool_delle_note` (nomi invariati); `test_con_archivio_i_quattro_tool` (nomi in coda nell'ordine sopra, descrizioni non vuote, `elimina_nota` ha nella descrizione «conferma»); `test_tool_note_scrivono_nell_archivio` (`aggiungi_nota.invoke({"testo": "x"})` → «Nota 1 salvata: x» e `archivio.leggi(1)` non è `None`), con archivio `":memory:"`.
- [ ] **Step 2:** `.\.venv\Scripts\python -m pytest tests/test_config.py tests/test_strumenti.py -v` → FAIL.
- [ ] **Step 3:** implementare; in `.env.example` aggiungere un commento e `PERCORSO_DB_NOTE=note.sqlite3`.
- [ ] **Step 4:** `.\.venv\Scripts\python -m pytest -v` → verde.
- [ ] **Step 5:** commit `feat(note): strumenti delle note e percorso dell'archivio da variabile d'ambiente`.

### Task 3: conferma dell'eliminazione nel grafo

**Files:**
- Modify: `assistente/grafo.py`
- Test: `tests/test_grafo.py`

**Interfaces:**
- Consumes: Task 1 (`ArchivioNote.leggi`), Task 2 (`crea_strumenti(..., archivio=...)`).
- Produces:
  - `costruisci_grafo(modello, strumenti, fuso_predefinito, max_passaggi, archivio: ArchivioNote | None = None)`. Se fra gli strumenti c'è `elimina_nota` e `archivio` è `None` → `ValueError`. Con archivio: `compile(checkpointer=InMemorySaver())`; senza: `compile()` come oggi (i test esistenti che chiamano `invoke` senza `thread_id` restano validi).
  - `StatoConversazione` con un campo in più `eliminazioni_confermate: NotRequired[list[str]]` (id delle chiamate confermate), letto con `stato.get(..., [])`.
  - `instrada_dopo_modello` può restituire anche `"conferma_eliminazione"`: dopo il controllo del limite, se una delle `tool_calls` ha nome `elimina_nota`.
  - Dati dell'interruzione: `{"numero": int, "creata": "AAAA-MM-GG HH:MM", "testo": str}`; la ripresa è `Command(resume=True | False)`.
  - `limite_ricorsione(max_passaggi) = 3 * max_passaggi + 4` (un passo in più per giro).
- Comportamento (algoritmo che i test non determinano del tutto):
  - `_numero(args) -> int | None`: accetta `int` (non `bool`) o stringa di sole cifre; `> 0`; altrimenti `None`.
  - `nodo_conferma_eliminazione`: prende la **prima** chiamata `elimina_nota` del messaggio; se `_numero` è valido e `archivio.leggi(n)` esiste → `si = interrupt(dati)`; restituisce `{"eliminazioni_confermate": [id] if si is True else []}`. Altrimenti `{"eliminazioni_confermate": []}` senza pausa.
  - `nodo_strumenti`, per ogni chiamata `elimina_nota`: se non è la prima del messaggio → `Errore: elimina una nota alla volta.`; se il suo id è confermato → esegue lo strumento; se non è confermata e la nota esiste → `Eliminazione annullata dall'utente: la nota N non è stata eliminata.`; se la nota non esiste o il numero non è valido → esegue lo strumento (risponde «non trovata» o con l'errore di validazione, non elimina nulla). Le altre chiamate come oggi.
  - Prompt di sistema: aggiungere prima di «Se uno strumento risponde con un errore…»: «L'utente può salvare note personali: quando chiede di annotare o ricordare qualcosa usa aggiungi_nota; per ritrovarle usa cerca_note con una parola chiave, o elenca_note per vederle tutte; per cancellarne una usa elimina_nota con il numero della nota, che trovi con cerca_note: la conferma all'utente la chiede il programma. Se più note corrispondono, elencale e chiedi quale eliminare. Non citare note che gli strumenti non hanno restituito. »

- [ ] **Step 1: test che falliscono** (helper `crea_con_note(risposte, tmp_path)` che apre l'archivio con l'orologio `AUTUNNO`, costruisce il grafo con `crea_strumenti(AUTUNNO, archivio=archivio)` e `archivio=archivio`; config `{"recursion_limit": limite_ricorsione(3), "configurable": {"thread_id": "t"}}`; stato iniziale `{"messages": [HumanMessage("elimina")], "passaggi_strumenti": 0}`; chiamate con `chiamata_strumento(None, nome="elimina_nota", args={"numero": 1})`):

```python
def test_instradamento_elimina_va_alla_conferma(): ...  # "conferma_eliminazione"
def test_instradamento_elimina_al_limite(): ...          # "limite_raggiunto"

def test_elimina_si_ferma_con_i_dati_dell_archivio(tmp_path):
    # nota 1 "sensore SEN-004 da ricalibrare"; il modello chiede elimina_nota(1)
    esito = grafo.invoke(stato, config)
    assert esito["__interrupt__"][0].value == {"numero": 1, "creata": "2026-10-26 17:05", "testo": "sensore SEN-004 da ricalibrare"}
    assert archivio.leggi(1) is not None

def test_elimina_confermata(tmp_path):
    # dopo la pausa: grafo.invoke(Command(resume=True), config)
    # → archivio.leggi(1) is None; ToolMessage "Nota 1 eliminata."; ultimo messaggio = risposta finale del modello

def test_elimina_rifiutata(tmp_path):
    # Command(resume=False) → nota presente; ToolMessage "Eliminazione annullata dall'utente: la nota 1 non è stata eliminata."

def test_elimina_con_numero_stringa(tmp_path):          # args {"numero": "1"} → pausa, poi eliminata con True

@pytest.mark.parametrize("numero", [7, 0, -1, True, "tre"])
def test_elimina_numero_non_valido_senza_pausa(tmp_path, numero):
    # nessun "__interrupt__"; nota 1 ancora presente; ToolMessage che contiene "non trovata" o inizia con "Errore"

def test_due_eliminazioni_una_conferma(tmp_path):
    # un AIMessage con due elimina_nota (id "a" numero 1, id "b" numero 2), entrambe le note esistono
    # una sola pausa (numero 1); dopo True: nota 1 eliminata, nota 2 presente, ToolMessage di "b" = "Errore: elimina una nota alla volta."

def test_aggiunta_senza_pausa(tmp_path):                # aggiungi_nota → nessuna pausa, nota salvata

def test_elimina_senza_archivio_rifiutato():
    with pytest.raises(ValueError):
        costruisci_grafo(ModelloFinto([]), crea_strumenti(AUTUNNO, archivio=apri_archivio(":memory:")), "Europe/Rome", 3)

def test_prompt_di_sistema_cita_le_note():
    for nome in ("aggiungi_nota", "cerca_note", "elenca_note", "elimina_nota"):
        assert nome in prompt_di_sistema("Europe/Rome")
```

- [ ] **Step 2:** `.\.venv\Scripts\python -m pytest tests/test_grafo.py -v` → i nuovi FAIL, gli esistenti verdi.
- [ ] **Step 3:** implementare secondo le Interfaces; nodo `conferma_eliminazione` con arco verso `strumenti`; mappa di `add_conditional_edges` estesa.
- [ ] **Step 4:** `.\.venv\Scripts\python -m pytest -v` → tutto verde.
- [ ] **Step 5:** commit `feat(grafo): conferma dell'eliminazione delle note con interrupt`.

### Task 4: sessione e terminale con la richiesta di conferma

**Files:**
- Modify: `assistente/cli.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: Task 3 (dati dell'interruzione, `Command(resume=bool)`).
- Produces:
  - `@dataclass(frozen=True) class Conferma: domanda: str`
  - `domanda_conferma(dati: dict) -> str` → testo fisso dei Global Constraints.
  - `e_un_si(risposta: str) -> bool`
  - `Sessione.chiedi(testo: str) -> str | Conferma`: `thread_id = uuid4().hex` nuovo per ogni domanda; input `{"messages": cronologia + [HumanMessage(testo)], "passaggi_strumenti": 0, "eliminazioni_confermate": []}`; se il risultato ha `"__interrupt__"` restituisce `Conferma(domanda_conferma(valore))` e conserva la config del turno; altrimenti aggiorna `cronologia` e restituisce il testo come oggi.
  - `Sessione.conferma(si: bool) -> str | Conferma`: riprende con `Command(resume=si)` nella stessa config; stessa gestione del risultato. Un errore durante la ripresa lascia `cronologia` invariata.
  - `esegui_ciclo`: finché l'esito è `Conferma` → `scrivi(esito.domanda)`, `leggi("Conferma> ")`, `sessione.conferma(e_un_si(riga))`. `EOFError`/`KeyboardInterrupt` durante la lettura della conferma → `Arrivederci.` e uscita, nessuna eliminazione. Le eccezioni della ripresa seguono la gestione già esistente.

- [ ] **Step 1: test che falliscono** (helper `crea_con_note` come nel Task 3, con `Sessione(grafo, limite_ricorsione(3))`; archivio con nota 1 «sensore SEN-004 da ricalibrare»; il modello finto risponde `elimina_nota(1)` e poi `AIMessage("fatto")`):

```python
@pytest.mark.parametrize("risposta, atteso", [("sì", True), (" Sì ", True), ("si", True), ("S", True),
                                              ("", False), ("no", False), ("sìì", False), ("yes", False), ("ok", False)])
def test_e_un_si(risposta, atteso): ...

def test_chiedi_restituisce_la_conferma(tmp_path):
    esito = sessione.chiedi("elimina la nota sul sensore")
    assert esito == Conferma('Eliminare la nota 1 (2026-10-26 17:05): "sensore SEN-004 da ricalibrare"? [sì/no]')
    assert sessione.cronologia == []

def test_conferma_completa_il_turno(tmp_path):
    # chiedi → Conferma; conferma(True) == "fatto"; archivio.leggi(1) is None;
    # in cronologia c'è il ToolMessage "Nota 1 eliminata."

def test_errore_dopo_la_conferma_non_entra_in_cronologia(tmp_path):
    # il modello finto alza RuntimeError dopo la ripresa: conferma(True) solleva, cronologia == [], nota eliminata comunque

def test_ciclo_con_conferma_si(tmp_path):     # ciclo(sessione, ["elimina", "sì", "/esci"]) → domanda nell'output, nota eliminata, "Assistente> fatto"
def test_ciclo_con_conferma_vuota(tmp_path):  # ["elimina", "", "/esci"] → nota presente
@pytest.mark.parametrize("eccezione", [EOFError, KeyboardInterrupt])
def test_ciclo_interrotto_durante_la_conferma(tmp_path, eccezione):  # ["elimina", eccezione] → "Arrivederci.", nota presente
```

- [ ] **Step 2:** `.\.venv\Scripts\python -m pytest tests/test_cli.py -v` → i nuovi FAIL; quelli esistenti (cronologia, turno fallito, contatore, Ctrl+C) restano verdi senza modifiche.
- [ ] **Step 3:** implementare.
- [ ] **Step 4:** `.\.venv\Scripts\python -m pytest -v` → verde.
- [ ] **Step 5:** commit `feat(cli): richiesta di conferma nel terminale e un thread per ogni domanda`.

### Task 5: avvio con l'archivio

**Files:**
- Modify: `assistente/__main__.py`
- Test: `tests/test_main.py`

**Interfaces:**
- Consumes: Task 1 (`apri_archivio`, `ErroreArchivio`), Task 2 (`config.percorso_db_note`, `crea_strumenti(..., archivio=)`), Task 3 (`costruisci_grafo(..., archivio=)`).
- Produces: ordine di avvio configurazione → catalogo → archivio → server MCP. `ErroreArchivio` → `Archivio note non disponibile: <motivo>` su stderr, `return 5`, server MCP mai avviato. L'archivio viene chiuso in ogni uscita successiva alla sua apertura (MCP fallito, Ctrl+C all'avvio, fine normale).

- [ ] **Step 1: test che falliscono**
  - `ENV` dei test aggiornato: ogni test di `test_main.py` imposta `PERCORSO_DB_NOTE` su `tmp_path / "note.sqlite3"` (fixture `autouse` con `monkeypatch`).
  - `test_avvio_con_tutti_gli_strumenti`: la lista attesa ha `"aggiungi_nota", "elenca_note", "cerca_note", "elimina_nota"` dopo `"dettaglio_articolo"` e prima di `"converti_unita"`.
  - `test_archivio_non_disponibile_blocca_l_avvio`: `PERCORSO_DB_NOTE` sotto un file esistente → `main() == 5`, stderr contiene `Archivio note non disponibile:`, `ClientMCP.avvia` mai chiamato.
  - `test_archivio_chiuso_se_mcp_non_parte`: con `ArchivioNote.chiudi` sostituito da un registratore, server MCP che esce → `main() == 3` e `chiudi` chiamato.
- [ ] **Step 2:** `.\.venv\Scripts\python -m pytest tests/test_main.py -v` → FAIL.
- [ ] **Step 3:** implementare.
- [ ] **Step 4:** `.\.venv\Scripts\python -m pytest -v` → verde; `git status` non mostra `note.sqlite3`.
- [ ] **Step 5:** commit `feat(note): archivio aperto all'avvio con codice di uscita 5 se non disponibile`.

### Task 6: volume Docker

**Files:**
- Modify: `docker-compose.yml`, `Dockerfile`, `README.md` (paragrafo Docker)

**Interfaces:**
- Produces: volume con nome `note` montato su `/app/note` nel servizio `assistente`, `PERCORSO_DB_NOTE: /app/note/note.sqlite3` in `environment`; nel `Dockerfile` la cartella `/app/note` creata e di proprietà di `app` prima di `USER app`.

- [ ] **Step 1:** modificare i due file.
- [ ] **Step 2:** con Docker Desktop avviato: `docker compose build` → successo; `docker compose run --rm assistente python -m pytest -v` → verde (la prova reale saltata).
- [ ] **Step 3: prova del volume** (richiede LM Studio attivo):
  `"Annota che il saldatore va pulito", "/esci" | docker compose run --rm -T assistente` → nei log `chiamata strumento aggiungi_nota`; poi in un secondo run separato `"Quali note ho?", "/esci" | docker compose run --rm -T assistente` → la risposta contiene la nota. Poi `"Elimina la nota sul saldatore", "sì", "Quali note ho?", "/esci" | docker compose run --rm -T assistente` → compare la domanda `Eliminare la nota ...? [sì/no]` e l'elenco finale non ha più la nota. Se il modello non arriva a `elimina_nota` in un turno, annotarlo nel resoconto: è un limite del modello, non del volume.
- [ ] **Step 4:** `docker compose down`; `docker volume ls` mostra ancora il volume delle note.
- [ ] **Step 5:** README: nella sezione Avvio, il volume delle note e l'avvertenza che `docker compose down -v` cancella le note, con i soli comandi verificati allo Step 3.
- [ ] **Step 6:** commit `feat(docker): volume per l'archivio delle note`.

### Task 7: prove reali con LM Studio e documentazione

**Files:**
- Modify: `tests/test_lmstudio.py`, `README.md`, `CLAUDE.md` (solo se cambiano comandi stabili)

**Interfaces:**
- Consumes: tutto quanto sopra.
- Produces:
  - fixture di modulo `archivio_prova(tmp_path_factory)`; `grafo_completo` gli passa l'archivio (strumenti e grafo); le chiamate `grafo.invoke` di `grafo_completo` e dell'helper `chiedi` aggiungono `{"configurable": {"thread_id": uuid4().hex}}`.
  - helper `chiedi_con_conferma(grafo_completo, domanda, risposta: bool)` che riprende con `Command(resume=risposta)` a ogni pausa, registra i dati delle pause e stampa chiamate e risposta.
  - fixture `note_di_prova(archivio_prova)` che svuota l'archivio e aggiunge «il sensore SEN-004 va ricalibrato» e «comprare cavi USB».

- [ ] **Step 1: prove** (marcatore `lmstudio`), asserzioni sulle chiamate e sull'archivio, risposte stampate:
  - `test_note_aggiunta` (archivio vuoto): «Annota che il saldatore va pulito» → chiamata `aggiungi_nota`; una nota nell'archivio contiene «saldatore».
  - `test_note_ricerca`: «Cosa avevo scritto sul sensore?» → `cerca_note`; un `ToolMessage` contiene «SEN-004».
  - `test_note_elenco`: «Quali note ho?» → `elenca_note`.
  - `test_note_nessun_risultato`: «Cosa avevo scritto sulla stampante?» → `cerca_note` con risultato «Nessuna nota trovata».
  - `test_note_eliminazione_confermata`: «Elimina la nota sul sensore», risposta `True` → una pausa con il numero della nota del sensore; la nota non c'è più, quella dei cavi sì.
  - `test_note_eliminazione_annullata`: come sopra con `False` → entrambe le note presenti.
- [ ] **Step 2:** `.\.venv\Scripts\python -m pytest --lmstudio -m lmstudio -v -s` → tutte le prove, anche quelle esistenti (il prompt è cambiato). Se una prova esistente peggiora, correggere prompt o descrizioni e rieseguire **tutte** le prove; non adattare i dati a una sola domanda. Leggere a occhio le risposte: nessuna nota inventata.
- [ ] **Step 3:** `.\.venv\Scripts\python -m pytest -v` → verde senza modello.
- [ ] **Step 4:** README:
  - sezione «Note personali» (file, `PERCORSO_DB_NOTE`, i quattro strumenti, conferma `sì/no`, esempi di richieste);
  - «Regole degli strumenti»: riga delle note;
  - «Struttura del grafo»: schema mermaid con `conferma_eliminazione` e il campo `eliminazioni_confermate`;
  - «Test»: descrizione aggiornata della prova reale con il numero di test superati;
  - «Diagnosi»: «Archivio note non disponibile» (codice 5);
  - «Checklist manuale»: voce sulle note, compresa la conferma in sessione interattiva locale e Docker con TTY e Ctrl+C durante la conferma (da eseguire a mano, segnata come non ancora verificata finché non lo è).
  - `CLAUDE.md`: nella sezione Comandi, una riga sul volume delle note e su `docker compose down -v`.
- [ ] **Step 5:** commit `test(note): prove reali con LM Studio e documentazione delle note`.
- [ ] **Step 6:** handoff in `docs/superpowers/handoff-2026-11-09-note.md` con cosa è stato eseguito, gli esiti, cosa resta da provare a mano e i rilievi minori; commit `docs: handoff delle note persistenti`.
