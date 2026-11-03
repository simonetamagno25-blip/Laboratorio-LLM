# Catalogo locale — piano di implementazione

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** aggiungere all'assistente due tool locali, `cerca_articoli` e `dettaglio_articolo`, sopra un catalogo JSON del materiale del laboratorio validato all'avvio.

**Architecture:** un modulo `assistente/catalogo.py` con dati immutabili, validazione e due funzioni pure che restituiscono testo; `assistente/strumenti.py` le avvolge come `StructuredTool`; `__main__` carica il catalogo prima di avviare il server MCP. Grafo, cronologia e CLI invariati, salvo una frase nel prompt di sistema.

**Tech Stack:** Python 3.12, libreria standard (`json`, `unicodedata`, `re`, `dataclasses`, `pathlib`), `langchain_core` (già presente), pytest.

**Spec:** `docs/superpowers/specs/2026-11-03-catalogo-locale-design.md`

## Global Constraints

- Nessuna nuova dipendenza: `requirements*.txt` invariati.
- Codice sincrono, moduli piccoli; il grafo non cambia forma (nodi e instradamento).
- Il catalogo si legge soltanto; nessuna funzione di scrittura.
- Categorie (elenco chiuso): `schede`, `sensori`, `attuatori`, `cavi`, `alimentazione`, `strumenti di misura`.
- Prefissi: `SCH` schede, `SEN` sensori, `ATT` attuatori, `CAV` cavi, `ALI` alimentazione, `MIS` strumenti di misura.
- Codice nel formato `AAA-000` (tre lettere maiuscole, trattino, tre cifre).
- Massimo 10 risultati per ricerca.
- Testo fisso del dettaglio non trovato: `Codice non trovato: "XYZ-999". Usa cerca_articoli per trovare il codice giusto.`
- Errori degli strumenti con prefisso `Errore: `, come calcolatrice e convertitore.
- Comandi da PowerShell, cartella `lezione_4/`; test con `.\.venv\Scripts\python -m pytest`.
- Conventional Commits in italiano; prima di ogni commit `git status`, diff, staging selettivo; dopo ogni commit avvisare l'utente; push solo su sua conferma.

## Review Focus

1. File salvato con BOM (Blocco note di Windows) → deve caricarsi lo stesso: lettura con `encoding="utf-8-sig"`. Test in Task 1.
2. Il modello passa punteggiatura o maiuscole nel testo (`"DHT22?"`, `"Temperatura,"`) → stesse corrispondenze del testo pulito: parole estratte con `\w+`. Test in Task 2.
3. Testo fatto solo di spazi o punteggiatura, senza categoria → trattato come vuoto: errore «indica un testo o una categoria». Test in Task 2.
4. Categoria con spazi o maiuscole (`" Sensori "`) → accettata. Test in Task 2.
5. Codice con spazi interni o minuscole (`"sen 004"`, `" sen-004 "`) → trovato `SEN-004`. Test in Task 2.

---

### Task 1: dati del catalogo e validazione al caricamento

**Files:**
- Create: `assistente/catalogo.py`
- Create: `assistente/dati/catalogo.json`
- Test: `tests/test_catalogo.py`

**Interfaces:**
- Produces:
  - `CATEGORIE: dict[str, str]` — prefisso → categoria (i sei valori del §4).
  - `@dataclass(frozen=True) class Articolo: codice: str; nome: str; categoria: str; descrizione: str; quantita: int; posizione: str`
  - `Catalogo = tuple[Articolo, ...]`
  - `class ErroreCatalogo(ValueError)`
  - `FILE_CATALOGO: Path` = `Path(__file__).parent / "dati" / "catalogo.json"`
  - `valida_catalogo(dati: object) -> Catalogo` — riceve il JSON già decodificato.
  - `carica_catalogo(percorso: Path = FILE_CATALOGO) -> Catalogo` — legge con `utf-8-sig`, decodifica, chiama `valida_catalogo`; file mancante o JSON non valido → `ErroreCatalogo` con il percorso nel messaggio.

- [ ] **Step 1: scrivere i test che falliscono** in `tests/test_catalogo.py`:
  - `test_file_reale_valido`: `carica_catalogo()` restituisce tra 18 e 25 articoli; tutte le sei categorie presenti; almeno un articolo con `quantita == 0`; esiste `SEN-004` con `"umidità"` in `nome.casefold()`; almeno un articolo con `"temperatura"` nel nome; nessun articolo con `"stampant"` in nome o descrizione (casefold).
  - `test_articolo_valido_diventa_articolo`: un dict valido (`SEN-001`, `sensori`, quantità 3) → `valida_catalogo([d]) == (Articolo(...),)`.
  - `test_errori_di_validazione` parametrizzato; ognuno → `pytest.raises(ErroreCatalogo, match=...)`:
    - contenuto non lista (`{}`) → `match="lista"`;
    - lista vuota → `match="vuot"`;
    - articolo non oggetto (`["x"]`) → `match="articolo 1"`;
    - campo mancante (senza `posizione`) → `match="posizione"`;
    - campo in più (`"prezzo": 3`) → `match="prezzo"`;
    - nome `"   "` → `match="nome"`;
    - nome non stringa (`5`) → `match="nome"`;
    - codice `"SEN-04"` → `match="SEN-04"`;
    - codice `"sen-004"` → `match="sen-004"`;
    - prefisso incoerente (`ATT-001` con categoria `sensori`) → `match="ATT-001"`;
    - categoria `"robot"` → `match="robot"`;
    - quantità `-1` → `match="quantita"`;
    - quantità `True` → `match="quantita"`;
    - quantità `2.5` → `match="quantita"`;
    - due articoli con lo stesso codice → `match="duplicato"`.
    Il messaggio indica la posizione (`articolo N`, da 1) e il codice quando è leggibile.
  - `test_file_mancante` (`tmp_path / "no.json"`) e `test_json_non_valido` (file con `"{"`) → `ErroreCatalogo` con il nome del file nel messaggio.
  - `test_file_con_bom`: scrittura di un catalogo valido con `encoding="utf-8-sig"` → `carica_catalogo(percorso)` lo legge.

- [ ] **Step 2: eseguire e vedere fallire**
  Run: `.\.venv\Scripts\python -m pytest tests/test_catalogo.py -v`
  Expected: FAIL (`ModuleNotFoundError: assistente.catalogo`).

- [ ] **Step 3: implementare `assistente/catalogo.py`** con le interfacce sopra. Formato del codice con `re.fullmatch(r"[A-Z]{3}-\d{3}", codice)`; quantità valida solo se `type(q) is int and q >= 0`. Scrivere `assistente/dati/catalogo.json` (UTF-8, indentato, ~20 articoli plausibili) che soddisfa `test_file_reale_valido`; almeno 3 sensori, così una ricerca per categoria `sensori` restituisce più righe.

- [ ] **Step 4: eseguire e vedere passare**
  Run: `.\.venv\Scripts\python -m pytest tests/test_catalogo.py -v`
  Expected: PASS.

- [ ] **Step 5: commit**
  ```powershell
  git add assistente/catalogo.py assistente/dati/catalogo.json tests/test_catalogo.py
  git commit -m "feat(catalogo): dati del laboratorio e validazione al caricamento"
  ```

### Task 2: ricerca e dettaglio

**Files:**
- Modify: `assistente/catalogo.py`
- Test: `tests/test_catalogo.py`

**Interfaces:**
- Consumes: `Articolo`, `Catalogo`, `CATEGORIE` (Task 1).
- Produces:
  - `cerca_articoli(catalogo: Catalogo, testo: str = "", categoria: str = "") -> str`
  - `dettaglio_articolo(catalogo: Catalogo, codice: str) -> str`
  - `MAX_RISULTATI = 10`

Formati di uscita (copia esatta):
- riga di risultato: `SEN-004 | Sensore di temperatura e umidità DHT22 | quantità: 6`; se `quantita == 0`: `... | quantità: 0 (esaurito)`.
- con risultati: prima riga `Articoli trovati: N`, poi una riga per articolo (al massimo 10, ordine per codice); se `N > 10`, ultima riga `Altri K articoli non mostrati: restringi la ricerca.`
- nessun risultato: `Nessun articolo trovato per "<testo>". Il catalogo non contiene articoli corrispondenti.`; con categoria: `Nessun articolo trovato per "<testo>" nella categoria "<categoria>". Il catalogo non contiene articoli corrispondenti.` (`<testo>` e `<categoria>` come passati, ripuliti con `strip`).
- categoria non valida: `Errore: categoria non valida: "<categoria>". Categorie valide: schede, sensori, attuatori, cavi, alimentazione, strumenti di misura.`
- testo e categoria vuoti: `Errore: indica un testo da cercare o una categoria.`
- dettaglio: sei righe `codice: …`, `nome: …`, `categoria: …`, `descrizione: …`, `quantità: N` (con ` (esaurito)` se 0), `posizione: …`, separate da `\n`.

Normalizzazione (una funzione privata usata per testo cercato e testo dell'articolo):
```python
def _normalizza(testo: str) -> str:
    scomposto = unicodedata.normalize("NFKD", testo)
    return "".join(c for c in scomposto if not unicodedata.combining(c)).casefold()
```
Parole cercate: `re.findall(r"\w+", _normalizza(testo))`; corrispondenza se ogni parola è sottostringa di `_normalizza(f"{nome} {descrizione} {categoria}")`. Codice del dettaglio: `"".join(codice.split()).upper()`.

- [ ] **Step 1: scrivere i test che falliscono** in `tests/test_catalogo.py`, su un catalogo di prova costruito nel test (fixture `piccolo` con 4 articoli, tra cui `SEN-004` «Sensore di temperatura e umidità DHT22», un `SEN-001` «Sensore di temperatura DS18B20» con quantità 0, un `CAV-001` e un `SCH-001`) e una fixture `grande` con 12 sensori:
  - `test_cerca_per_parola`: `"temperatura"` → contiene `Articoli trovati: 2`, `SEN-001` prima di `SEN-004`.
  - `test_cerca_tutte_le_parole_anche_in_campi_diversi`: una parola nel nome e una solo nella descrizione → trovato; con una parola assente → nessun risultato.
  - `test_cerca_senza_maiuscole_e_accenti`: `"UMIDITA"` → trova `SEN-004`.
  - `test_cerca_con_punteggiatura`: `"DHT22?"` e `"Temperatura,"` danno lo stesso risultato di `"dht22"` e `"temperatura"`.
  - `test_cerca_per_categoria`: `categoria=" Sensori "` senza testo → solo articoli `SEN-`.
  - `test_cerca_testo_e_categoria`: `"temperatura"` + `"cavi"` → messaggio nessun risultato con la categoria.
  - `test_esaurito_segnalato`: riga di `SEN-001` termina con `quantità: 0 (esaurito)`.
  - `test_nessun_risultato`: `"stampante 3D"` → esattamente `Nessun articolo trovato per "stampante 3D". Il catalogo non contiene articoli corrispondenti.`
  - `test_categoria_non_valida`: `categoria="robot"` → testo esatto dell'errore.
  - `test_testo_e_categoria_vuoti` parametrizzato su `("", "")`, `("   ", "")`, `("?!", "")` → `Errore: indica un testo da cercare o una categoria.`
  - `test_troncamento`: fixture `grande`, `categoria="sensori"` → `Articoli trovati: 12`, 10 righe articolo, ultima riga `Altri 2 articoli non mostrati: restringi la ricerca.`
  - `test_dettaglio`: `SEN-004` → le sei righe esatte.
  - `test_dettaglio_codice_normalizzato` parametrizzato su `"sen-004"`, `" SEN-004 "`, `"sen 004"` → come `SEN-004`.
  - `test_dettaglio_inesistente`: `"XYZ-999"` → testo fisso dei Global Constraints.

- [ ] **Step 2: eseguire e vedere fallire**
  Run: `.\.venv\Scripts\python -m pytest tests/test_catalogo.py -v`
  Expected: FAIL (`ImportError: cannot import name 'cerca_articoli'`).

- [ ] **Step 3: implementare `cerca_articoli` e `dettaglio_articolo`** in `assistente/catalogo.py` come sopra.

- [ ] **Step 4: eseguire e vedere passare**
  Run: `.\.venv\Scripts\python -m pytest tests/test_catalogo.py -v`
  Expected: PASS.

- [ ] **Step 5: commit**
  ```powershell
  git add assistente/catalogo.py tests/test_catalogo.py
  git commit -m "feat(catalogo): ricerca per parole e categoria e dettaglio per codice"
  ```

### Task 3: tool, prompt e avvio

**Files:**
- Modify: `assistente/strumenti.py` (`crea_strumenti`)
- Modify: `assistente/grafo.py` (`prompt_di_sistema`)
- Modify: `assistente/__main__.py` (`main`)
- Test: `tests/test_strumenti.py`, `tests/test_grafo.py`, `tests/test_main.py`

**Interfaces:**
- Consumes: `carica_catalogo`, `ErroreCatalogo`, `Catalogo`, `cerca_articoli`, `dettaglio_articolo` (Task 1–2).
- Produces: `crea_strumenti(adesso: Orologio = adesso_utc, catalogo: Catalogo | None = None) -> list[BaseTool]`. Con `catalogo=None` usa `carica_catalogo()` (così i chiamanti esistenti non cambiano). Ordine: `ora_corrente`, `calcola`, `cerca_articoli`, `dettaglio_articolo`.

Descrizioni dei tool (copia esatta):
- `cerca_articoli`: `"Cerca nel catalogo del materiale del laboratorio per parole chiave e/o categoria. Usa una o due parole chiave brevi, al singolare (per esempio temperatura, cavo). Categorie: schede, sensori, attuatori, cavi, alimentazione, strumenti di misura. Restituisce codice, nome e quantità; per descrizione e posizione usa dettaglio_articolo."`
- `dettaglio_articolo`: `"Restituisce la scheda completa di un articolo del catalogo dato il suo codice, per esempio SEN-004, con descrizione, quantità e posizione. Se non conosci il codice usa prima cerca_articoli."`

Frase da aggiungere al prompt di sistema, prima di «Se uno strumento risponde con un errore…»:
`"Per domande sul materiale del laboratorio usa cerca_articoli e, per la scheda di un codice, dettaglio_articolo; non citare articoli, quantità o posizioni che gli strumenti non hanno restituito. "`

Avvio: in `main`, subito dopo `logging.getLogger(...)` e **prima** di creare `ClientMCP`, `catalogo = carica_catalogo()`; su `ErroreCatalogo` stampa `Catalogo non valido: <errore>` su stderr e `return 4`. Poi `crea_strumenti(catalogo=catalogo)`.

- [ ] **Step 1: scrivere i test che falliscono**
  - `tests/test_strumenti.py::test_strumenti_del_catalogo_esposti`: nomi di `crea_strumenti()` == `["ora_corrente", "calcola", "cerca_articoli", "dettaglio_articolo"]`; le descrizioni contengono rispettivamente `"al singolare"` e `"cerca_articoli"`.
  - `tests/test_strumenti.py::test_strumenti_usano_il_catalogo_passato`: catalogo di un solo articolo → `invoke({"codice": "SEN-001"})` di `dettaglio_articolo` restituisce la sua scheda; `invoke({"testo": "temperatura"})` di `cerca_articoli` contiene `Articoli trovati: 1`.
  - `tests/test_grafo.py::test_ricerca_poi_dettaglio`: `ModelloFinto` con tre risposte: `chiamata_strumento(None, id="c1", nome="cerca_articoli", args={"testo": "umidità"})`, poi `chiamata_strumento(None, id="c2", nome="dettaglio_articolo", args={"codice": "SEN-004"})`, poi `AIMessage("È nell'armadio …")`; grafo costruito con `crea_strumenti(AUTUNNO)`. Verificare: 3 chiamate al modello; nella seconda c'è un `ToolMessage` con `tool_call_id == "c1"` che contiene `SEN-004`; nella terza un `ToolMessage` `c2` che contiene `posizione:`.
  - `tests/test_grafo.py::test_prompt_di_sistema_cita_il_catalogo`: `"cerca_articoli"` e `"dettaglio_articolo"` in `prompt_di_sistema("Europe/Rome")`.
  - `tests/test_main.py::test_avvio_con_tutti_gli_strumenti`: aggiornare l'elenco atteso inserendo `"cerca_articoli", "dettaglio_articolo"` dopo `"calcola"`.
  - `tests/test_main.py::test_catalogo_non_valido_blocca_l_avvio`: `monkeypatch.setattr(punto_di_ingresso, "carica_catalogo", ...)` con una funzione che solleva `ErroreCatalogo("articolo 3: codice duplicato")`; e `ClientMCP.avvia` sostituito da una funzione che registra la chiamata → `main() == 4`, stderr contiene `Catalogo non valido: articolo 3`, `avvia` mai chiamato.

- [ ] **Step 2: eseguire e vedere fallire**
  Run: `.\.venv\Scripts\python -m pytest tests/test_strumenti.py tests/test_grafo.py tests/test_main.py -v`
  Expected: FAIL sui test nuovi e su `test_avvio_con_tutti_gli_strumenti`.

- [ ] **Step 3: implementare** le modifiche a `strumenti.py`, `grafo.py` e `__main__.py` descritte sopra.

- [ ] **Step 4: eseguire tutta la suite**
  Run: `.\.venv\Scripts\python -m pytest -v`
  Expected: tutti passati tranne i test `lmstudio` saltati; nessuna regressione rispetto ai 186 passati precedenti.

- [ ] **Step 5: commit**
  ```powershell
  git add assistente/strumenti.py assistente/grafo.py assistente/__main__.py tests/test_strumenti.py tests/test_grafo.py tests/test_main.py
  git commit -m "feat(grafo): collega cerca_articoli e dettaglio_articolo all'assistente"
  ```

### Task 4: prove reali, Docker e documentazione

**Files:**
- Modify: `tests/test_lmstudio.py`
- Modify: `README.md`

**Interfaces:**
- Consumes: `crea_strumenti` (Task 3), fixture `grafo_completo` già presente in `tests/test_lmstudio.py`.

- [ ] **Step 1: scrivere le prove LM Studio** in `tests/test_lmstudio.py` (marcatore `lmstudio`), riusando `grafo_completo`; per ciascuna stampare con `print` le chiamate (nome, argomenti) e la risposta finale:
  - `test_catalogo_ricerca`: «Avete sensori di temperatura?» → almeno una chiamata `cerca_articoli`; un `ToolMessage` contiene `Articoli trovati:`.
  - `test_catalogo_dettaglio`: «Dimmi tutto su SEN-004» → chiamata `dettaglio_articolo` con `codice` che, normalizzato, è `SEN-004`.
  - `test_catalogo_ricerca_poi_dettaglio`: «Dov'è il sensore di umidità?» → una `cerca_articoli` prima di una `dettaglio_articolo`, e il codice del dettaglio compare nel risultato della ricerca.
  - `test_catalogo_nessun_risultato`: «Avete stampanti 3D?» → chiamata `cerca_articoli`; un `ToolMessage` contiene `Nessun articolo trovato`.
  - `test_catalogo_codice_inesistente`: «Dammi il dettaglio dell'articolo XYZ-999» → chiamata `dettaglio_articolo`; un `ToolMessage` contiene `Codice non trovato`.
  La risposta finale si giudica a occhio (non inventa articoli): annotarlo nel resoconto.

- [ ] **Step 2: verificare che senza `--lmstudio` siano saltati**
  Run: `.\.venv\Scripts\python -m pytest -v`
  Expected: i 5 nuovi test risultano `SKIPPED`, il resto passa.

- [ ] **Step 3: prova reale (LM Studio acceso, `.env` caricato, attivata esplicitamente)**
  Run: `.\.venv\Scripts\python -m pytest --lmstudio -m lmstudio -v -s`
  Expected: PASS di tutte le prove, comprese le 5 precedenti. Se una prova del catalogo fallisce per una ricerca con una forma flessa, correggere la descrizione del tool o il prompt (non i dati) e ripetere; riportare l'esito esatto.

- [ ] **Step 4: Docker**
  Run: `docker compose build`, poi `docker compose run --rm assistente python -m pytest -v`, poi `"Avete sensori di temperatura?", "/esci" | docker compose run --rm -T assistente`, infine `docker compose down`.
  Expected: test passati nel container; la risposta da pipe elenca articoli del catalogo e i log mostrano `cerca_articoli`.

- [ ] **Step 5: README**: sezione «Catalogo del laboratorio» (file `assistente/dati/catalogo.json`, campi, categorie e prefissi, cosa succede se il file non è valido, esempi delle cinque domande); voce nella checklist manuale per le domande del catalogo; solo comandi eseguiti negli step 2–4. `CLAUDE.md` non cambia (nessun comando nuovo).

- [ ] **Step 6: commit**
  ```powershell
  git add tests/test_lmstudio.py README.md
  git commit -m "test(catalogo): prove reali con LM Studio e documentazione del catalogo"
  ```
