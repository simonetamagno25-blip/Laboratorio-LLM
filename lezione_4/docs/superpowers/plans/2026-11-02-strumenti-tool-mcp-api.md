# Tre strumenti (tool, MCP, API) — piano di implementazione

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** aggiungere all'assistente una calcolatrice sicura (tool locale), un convertitore di unità (server MCP via stdio) e giorni e scadenze (servizio HTTP), senza cambiare la forma del grafo.

**Architecture:** ogni strumento ha la logica in funzioni pure testate a parte; il trasporto (StructuredTool locale, server `MCPServer` + adattatore sincrono, servizio `http.server` + client `httpx`) si limita a esporle. Il grafo riceve una lista di `BaseTool` come oggi.

**Tech Stack:** Python 3.12 (Docker) / venv locale esistente, LangGraph, langchain-core, `mcp==2.3.0`, `httpx==0.28.1`, libreria standard (`ast`, `http.server`, `json`, `datetime`), pytest.

**Spec:** `lezione_4/docs/superpowers/specs/2026-11-02-strumenti-mcp-design.md` (revisione 2). Leggerla prima di ogni task.

## Global Constraints

- Lavorare solo in `lezione_4/`, branch `feat/strumenti-mcp`. Tutti i comandi si lanciano da `lezione_4/` (PowerShell).
- Codice sincrono fuori dall'adattatore MCP; moduli piccoli; stile, nomi e commenti in italiano come il codice esistente.
- Ogni errore restituito al modello è testo che inizia con `Errore:`.
- Ogni risultato riuscito di giorni e scadenze termina con `(Risultato indicativo, non ha valore normativo.)`.
- Mai `eval`, `exec`, `compile` nella calcolatrice.
- Dipendenze nuove solo: `mcp==2.3.0` e `httpx==0.28.1` in `requirements.txt`.
- Test automatici senza modello attivo; la prova LM Studio resta sotto il marcatore `lmstudio`.
- Commit: Conventional Commits in italiano, `git status` + diff + staging selettivo prima di ogni commit, riga finale `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. **Dopo ogni commit avvisare l'utente («ho fatto il commit …») e fare `git push` solo dopo la sua conferma.**
- Comando test: `.\.venv\Scripts\python -m pytest -v` (da `lezione_4/`).

## Review Focus

1. Input numerici "strani" alla calcolatrice: `True`, `1e309`, `10**10**10`, `-(2**1000)**2` → rifiuto motivato, mai blocco del processo né `inf`. (Task 1)
2. Convertitore chiamato con unità uguali (`m`→`m`) o valore `0 K`/`-273.15 C` al limite dello zero assoluto → risultato corretto, non errore. (Task 2)
3. Date con spazi o maiuscole nei booleani (`" 2026-01-01"`, `solo_lavorativi=True`) → rifiuto esplicito coerente, non 500. (Task 3, Task 4)
4. Richiesta HTTP con parametro ripetuto o mancante, o eccezione inattesa nel handler → 400/500 con JSON `{"errore": …}`, mai connessione chiusa senza risposta. (Task 4)
5. Uscita dall'assistente con Ctrl+C mentre il server MCP è aperto → sottoprocesso chiuso, nessun processo orfano né traceback. (Task 6)

---

### Task 1: Calcolatrice sicura (tool locale)

**Files:**
- Create: `assistente/calcolatrice.py`
- Modify: `assistente/strumenti.py` (registrare `calcola` in `crea_strumenti`)
- Test: `tests/test_calcolatrice.py`, `tests/test_strumenti.py` (nome strumento presente)

**Interfaces:**
- Produces: `class ErroreCalcolo(ValueError)`; `valuta(espressione: str) -> int | float` (solleva `ErroreCalcolo` con motivo in italiano); `calcola(espressione: str) -> str` (restituisce `"<espressione> = <risultato>"` oppure `"Errore: <motivo>"`). Tool LangChain di nome `calcola`, parametro `espressione`.

- [ ] **Step 1: Test che falliscono** in `tests/test_calcolatrice.py`:
  - `calcola("(12 + 8) * 3 / 4") == "(12 + 8) * 3 / 4 = 15"` (float interi stampati senza `.0`);
  - `calcola("2 ** 10") == "2 ** 10 = 1024"`, `calcola("-3 + +2") == "-3 + +2 = -1"`, `calcola("7 % 3") == "7 % 3 = 1"`, `calcola("1 / 3")` inizia con `"1 / 3 = 0.333333"`;
  - parametrizzato, ognuno `startswith("Errore:")`: `"__import__('os')"`, `"abs(-1)"`, `"x + 1"`, `"(1).real"`, `"[1][0]"`, `"'a' * 3"`, `"1 < 2"`, `"1 & 3"`, `"1 +"`, `""`, `"1 / 0"`, `"5 % 0"`, `"True + 1"`, `"2 ** 101"`, `"10 ** 10 ** 10"`, `"1e309"`, `"9.9e99 * 10"`, `"1" + "+1" * 150` (oltre 200 caratteri);
  - motivi leggibili: `"Errore: divisione per zero" in calcola("1 / 0")`, `"non consentit" in calcola("abs(-1)")`;
  - `"eval(" not in` e `"exec(" not in` il sorgente di `assistente/calcolatrice.py` (lettura del file).
- [ ] **Step 2:** `.\.venv\Scripts\python -m pytest tests/test_calcolatrice.py -v` → FAIL (modulo mancante).
- [ ] **Step 3: Implementare** in `assistente/calcolatrice.py`: `ast.parse(testo, mode="eval")`, visitatore ricorsivo che accetta solo `Expression`, `Constant` (int/float, non bool), `BinOp` con `Add Sub Mult Div Mod Pow`, `UnaryOp` con `UAdd USub`; tutto il resto → `ErroreCalcolo(f"operazione non consentita: {nome_nodo}")`. Limiti come costanti di modulo: `LUNGHEZZA_MASSIMA = 200`, `ESPONENTE_MASSIMO = 100`, `VALORE_MASSIMO = 1e100` (controllato dopo ogni operazione e sui letterali; `inf`/`nan` → errore). Formattazione: float con `:.12g`; float con valore intero → int. `SyntaxError` → `"espressione non valida"`.
- [ ] **Step 4:** In `crea_strumenti` aggiungere `StructuredTool.from_function(func=calcola, name="calcola", description=…)` dopo l'orologio; descrizione: valuta espressioni aritmetiche con `+ - * / % **` e parentesi, usare sempre per i calcoli. Test in `tests/test_strumenti.py`: `[s.name for s in crea_strumenti()] == ["ora_corrente", "calcola"]`.
- [ ] **Step 5:** `.\.venv\Scripts\python -m pytest -v` → tutti PASS.
- [ ] **Step 6: Commit** `feat(strumenti): calcolatrice sicura senza eval come tool locale`, poi avvisare l'utente e attendere l'ok per il push.

### Task 2: Logica del convertitore di unità

**Files:**
- Create: `convertitore_mcp/__init__.py`, `convertitore_mcp/unita.py`
- Modify: `pyproject.toml` solo se serve perché pytest trovi il pacchetto (oggi trova `assistente` dalla cartella corrente: verificare)
- Test: `tests/test_unita.py`

**Interfaces:**
- Produces: `Unita = Literal["mm","cm","m","km","in","ft","mi","g","kg","t","oz","lb","C","F","K","ml","l","s","min","h","d"]`; `class ErroreConversione(ValueError)`; `converti(valore: float, da: str, a: str) -> float`; `descrivi_conversione(valore: float, da: str, a: str) -> str` → `"<valore> <da> = <risultato:.6g> <a>"` oppure `"Errore: <motivo>"`.

- [ ] **Step 1: Test che falliscono:**
  - `descrivi_conversione(26, "mi", "km") == "26 mi = 41.8429 km"`;
  - `converti(100, "C", "F") == pytest.approx(212)`, `converti(0, "F", "C") == pytest.approx(-17.7778, abs=1e-4)`, `converti(0, "K", "C") == pytest.approx(-273.15)`, `converti(1, "d", "h") == 24`, `converti(1, "lb", "kg") == pytest.approx(0.45359237)`, `converti(1, "in", "cm") == pytest.approx(2.54)`, `converti(5, "m", "m") == 5`, `converti(1, "l", "ml") == 1000`;
  - `descrivi_conversione(5, "kg", "m") == "Errore: kg → m: grandezze incompatibili (massa, lunghezza)"`;
  - `startswith("Errore:")` per: unità `"furlong"`, `"KG"`, valore `float("inf")`, `float("nan")`, `converti(-1, "K", "C")`, `converti(-300, "C", "K")`;
  - insieme dei simboli di `typing.get_args(Unita)` == insieme delle chiavi della tabella interna (nessuna unità ammessa senza conversione).
- [ ] **Step 2:** pytest su `tests/test_unita.py` → FAIL.
- [ ] **Step 3: Implementare**: tabella `simbolo -> (grandezza, fattore verso unità base)` per lunghezza (m), massa (kg), volume (l), tempo (s); temperatura a parte con passaggio per kelvin; zero assoluto = 0 K. Fattori esatti: `in` 0.0254, `ft` 0.3048, `mi` 1609.344, `oz` 0.028349523125, `lb` 0.45359237, `t` 1000.
- [ ] **Step 4:** pytest → PASS.
- [ ] **Step 5: Commit** `feat(convertitore): logica di conversione con unità a elenco chiuso`; avvisare e attendere l'ok.

### Task 3: Logica di giorni e scadenze

**Files:**
- Create: `scadenze_api/__init__.py`, `scadenze_api/scadenze.py`, `scadenze_api/dati/festivita_it.json`
- Test: `tests/test_scadenze.py`

**Interfaces:**
- Produces: `class ErroreScadenze(ValueError)`; `AVVERTENZA = "(Risultato indicativo, non ha valore normativo.)"`; `leggi_data(testo: str) -> date` (rigoroso `AAAA-MM-GG`); `carica_festivita(percorso: Path | None = None) -> dict[int, dict[date, str]]` (anno → data → nome; default il file del pacchetto); `giorni_tra_date(inizio: str, fine: str, solo_lavorativi: bool = False, festivita=None) -> str`; `calcola_scadenza(inizio: str, giorni: int, solo_lavorativi: bool = False, festivita=None) -> str`. Le due funzioni sollevano `ErroreScadenze` per input non validi (il trasporto lo trasforma in errore).

- [ ] **Step 1: Verificare l'elenco delle festività** su una fonte ufficiale (Gazzetta Ufficiale / governo.it per il 4 ottobre dal 2026) e annotare la fonte per il README. Scrivere il JSON: `{"fonte": "…", "anni": {"2026": {"2026-01-01": "Capodanno", …}, "2027": {…}}}` con le 13 date per anno della spec §5.3.
- [ ] **Step 2: Test che falliscono** (valori già verificati):
  - `giorni_tra_date("2026-12-20", "2027-01-10")` inizia con `"21 giorni"`; con `solo_lavorativi=True` inizia con `"12 giorni lavorativi"`; entrambi terminano con `AVVERTENZA`;
  - `giorni_tra_date("2026-01-10", "2026-01-01")` inizia con `"-9 giorni"`; `giorni_tra_date("2026-03-01", "2026-03-01")` inizia con `"0 giorni"`;
  - `calcola_scadenza("2026-12-23", 3, True)` contiene `"2026-12-29"`; `calcola_scadenza("2026-12-23", 3)` contiene `"2026-12-26"` e `"sabato"`; `calcola_scadenza("2026-10-01", 3)` contiene `"2026-10-04"`, `"domenica"` e `"San Francesco"`; `calcola_scadenza("2026-05-05", 0)` contiene `"2026-05-05"`;
  - `calcola_scadenza("2028-02-28", 1)` contiene `"2028-02-29"` (nessun limite di anno senza lavorativi);
  - `pytest.raises(ErroreScadenze)` per `leggi_data` con `"02/11/2026"`, `"2026-2-3"`, `"2026-02-30"`, `"2027-02-29"`, `""`, `" 2026-01-01"`, `"2026-01-01T10:00"`;
  - `ErroreScadenze` con `"2026"` e `"2027"` nel messaggio per `giorni_tra_date("2027-12-20", "2028-01-10", True)`;
  - `ErroreScadenze` per `calcola_scadenza("2026-01-01", -1)`, `calcola_scadenza("2026-01-01", 3651)`, `giorni_tra_date("2026-01-01", "2036-01-02")`;
  - il file JSON caricato ha per 2026 e 2027 esattamente 13 date ciascuno, e `date(2026, 10, 4)` è presente.
- [ ] **Step 3:** pytest → FAIL.
- [ ] **Step 4: Implementare**. Formati di uscita: `"<n> giorni[ lavorativi] dal <inizio> (escluso) al <fine> (incluso). <AVVERTENZA>"`; `"Scadenza: <data> (<giorno della settimana>)[, cade di <sabato|domenica>][, festività: <nome>]. <AVVERTENZA>"`. Nomi dei giorni in italiano da una tupla, non da `locale`. `leggi_data`: regex `^\d{4}-\d{2}-\d{2}$` poi `date.fromisoformat`.
- [ ] **Step 5:** pytest → PASS.
- [ ] **Step 6: Commit** `feat(scadenze): calcolo di giorni e scadenze con festività da file locale`; avvisare e attendere l'ok.

### Task 4: Servizio HTTP e client API di giorni e scadenze

**Files:**
- Create: `scadenze_api/servizio.py`, `scadenze_api/__main__.py`, `assistente/client_api.py`
- Modify: `requirements.txt` (+ `httpx==0.28.1`), `assistente/config.py` (campo `scadenze_api_url`), `.env.example` (`SCADENZE_API_URL=http://localhost:8000`), `tests/test_config.py`
- Test: `tests/test_servizio_scadenze.py`, `tests/test_client_api.py`

**Interfaces:**
- Consumes: Task 3 (`giorni_tra_date`, `calcola_scadenza`, `ErroreScadenze`).
- Produces: `crea_server(host: str, porta: int) -> ThreadingHTTPServer`; `python -m scadenze_api` ascolta su `0.0.0.0` porta `SCADENZE_API_PORTA` (default 8000). `Configurazione.scadenze_api_url: str` (obbligatoria, deve iniziare con `http://` o `https://`, senza `/` finale). `crea_strumenti_api(base_url: str, timeout: float = 10.0) -> list[BaseTool]` con tool `giorni_tra_date(inizio: str, fine: str, solo_lavorativi: bool = False)` e `calcola_scadenza(inizio: str, giorni: int, solo_lavorativi: bool = False)`.

- [ ] **Step 1: Test del servizio che falliscono.** Fixture che avvia `crea_server("127.0.0.1", 0)` in un thread e lo chiude con `shutdown()`; richieste con `httpx`:
  - `GET /salute` → 200 `{"stato": "ok"}`;
  - `GET /giorni?inizio=2026-12-20&fine=2027-01-10&solo_lavorativi=true` → 200, `risultato` inizia con `"12 giorni lavorativi"`;
  - `GET /scadenza?inizio=2026-12-23&giorni=3&solo_lavorativi=true` → 200, contiene `"2026-12-29"`;
  - 400 con chiave `errore` per: `inizio=02/11/2026`, `giorni=tre`, `giorni=-1`, `solo_lavorativi=True`, `solo_lavorativi=si`, parametro mancante, parametro ripetuto (`inizio=…&inizio=…`), parametro sconosciuto;
  - `GET /altro` → 404 JSON; `POST /giorni` → 405 JSON;
  - con `giorni_tra_date` sostituito (monkeypatch) da una funzione che solleva `RuntimeError` → 500 JSON `{"errore": "errore interno"}`;
  - `Content-Type` delle risposte `application/json; charset=utf-8`.
- [ ] **Step 2:** pytest → FAIL.
- [ ] **Step 3: Implementare** `servizio.py` con `BaseHTTPRequestHandler`: `urllib.parse.parse_qs(keep_blank_values=True)`, validazione dei parametri attesi per endpoint, `ErroreScadenze`/errori di parametri → 400, ogni altra eccezione → 500 con log; `log_message` instradato su `logging`. `__main__.py`: configura logging, legge `SCADENZE_API_PORTA`, `serve_forever()` fino a Ctrl+C.
- [ ] **Step 4:** pytest → PASS.
- [ ] **Step 5: Test configurazione che falliscono** in `tests/test_config.py`: `SCADENZE_API_URL` mancante → `ErroreConfigurazione`; `"ftp://x"` → `ErroreConfigurazione`; `"http://localhost:8000/"` → `config.scadenze_api_url == "http://localhost:8000"`. Aggiornare gli `env` di prova esistenti con la nuova variabile. Implementare in `config.py`, aggiornare `.env.example`. pytest → PASS.
- [ ] **Step 6: Test client che falliscono** in `tests/test_client_api.py`, contro il servizio vero della fixture (spostarla in `conftest.py`):
  - nomi dei tool `["giorni_tra_date", "calcola_scadenza"]`; lo schema di `calcola_scadenza` ha `giorni` di tipo integer;
  - `tool.invoke({"inizio": "2026-12-20", "fine": "2027-01-10", "solo_lavorativi": True})` inizia con `"12 giorni lavorativi"`;
  - input non valido → stringa che inizia con `"Errore: "` e contiene il motivo del servizio;
  - `crea_strumenti_api("http://127.0.0.1:<porta chiusa>")` → `"Errore: servizio scadenze non raggiungibile su http://127.0.0.1:…"`.
- [ ] **Step 7: Implementare** `client_api.py` con `httpx.get(…, params=…, timeout=…)`, booleani serializzati come `"true"/"false"`; `httpx.TransportError` → non raggiungibile; 4xx/5xx → `Errore: <errore dal JSON>`. pytest completo → PASS.
- [ ] **Step 8: Commit** `feat(api): servizio HTTP di giorni e scadenze e client dell'assistente`; avvisare e attendere l'ok.

### Task 5: Server MCP del convertitore

**Files:**
- Create: `convertitore_mcp/server.py`, `convertitore_mcp/__main__.py`
- Modify: `requirements.txt` (+ `mcp==2.3.0`), poi reinstallare: `.\.venv\Scripts\python -m pip install -r requirements-dev.txt`
- Test: `tests/test_server_mcp.py`

**Interfaces:**
- Consumes: Task 2 (`Unita`, `descrivi_conversione`).
- Produces: `server: MCPServer` (nome `"convertitore"`) con tool `converti_unita(valore: float, da: Unita, a: Unita) -> str`; `python -m convertitore_mcp` esegue `server.run("stdio")`.

- [ ] **Step 1: Installare** `mcp==2.3.0` e controllare che `.\.venv\Scripts\python -c "from mcp.server.mcpserver import MCPServer; from mcp.client.stdio import stdio_client, StdioServerParameters; from mcp import ClientSession"` termini senza errori. Se l'import di `ClientSession` da `mcp` fallisce, usare `mcp.client.session.ClientSession` in tutto il piano.
- [ ] **Step 2: Test che fallisce** in `tests/test_server_mcp.py`: con `asyncio.run` di una coroutine che apre `stdio_client(StdioServerParameters(command=sys.executable, args=["-m", "convertitore_mcp"], cwd=<lezione_4>))` + `ClientSession`, `initialize()`, `list_tools()`:
  - un solo tool, `converti_unita`;
  - nello `inputSchema` le proprietà `da` e `a` hanno `enum` (eventualmente tramite `$defs`/`$ref`: risolverlo nel test) uguale all'insieme di `get_args(Unita)`;
  - `call_tool("converti_unita", {"valore": 26, "da": "mi", "a": "km"})` → testo `"26 mi = 41.8429 km"`;
  - `call_tool` con `"da": "kg", "a": "m"` → testo che inizia con `"Errore:"`; con `"da": "furlong"` → `isError` vero oppure testo `Errore:` (registrare nel test quale dei due dà la 2.3.0).
- [ ] **Step 3:** pytest → FAIL. **Step 4: Implementare**: il tool chiama `descrivi_conversione` e restituisce la stringa (gli errori di dominio sono testo `Errore:`, non eccezioni). `__main__.py` non deve scrivere nulla su stdout oltre al protocollo.
- [ ] **Step 5:** pytest completo → PASS.
- [ ] **Step 6: Commit** `feat(convertitore): server MCP stdio con converti_unita`; avvisare e attendere l'ok.

### Task 6: Adattatore MCP sincrono

**Files:**
- Create: `assistente/client_mcp.py`
- Test: `tests/test_client_mcp.py`

**Interfaces:**
- Consumes: Task 5 (`python -m convertitore_mcp`).
- Produces: `class ErroreMCP(RuntimeError)`; `class ClientMCP` con `__init__(self, comando: str, argomenti: list[str], timeout: float = 15.0)`, `avvia(self) -> None` (solleva `ErroreMCP` se il server non parte o `list_tools` fallisce/scade), `strumenti(self) -> list[BaseTool]`, `chiudi(self) -> None` (idempotente), uso come context manager; `comando_convertitore() -> tuple[str, list[str]]` → `(sys.executable, ["-m", "convertitore_mcp"])`.

- [ ] **Step 1: Test che falliscono:**
  - con `ClientMCP(*comando_convertitore())` come context manager: `[s.name for s in client.strumenti()] == ["converti_unita"]`; `invoke({"valore": 26, "da": "mi", "a": "km"}) == "26 mi = 41.8429 km"`; `invoke` con `kg`→`m` inizia con `"Errore:"`; `invoke` con `"da": "furlong"` inizia con `"Errore:"`;
  - lo schema LangChain del tool espone l'enum delle unità (`tool.args["da"]` contiene `enum`, o il JSON schema passato come `args_schema`);
  - `ClientMCP(sys.executable, ["-c", "import sys; sys.exit(1)"]).avvia()` → `ErroreMCP` entro il timeout (usare `timeout=5`);
  - dopo `chiudi()` il sottoprocesso non è più vivo e una seconda `chiudi()` non solleva;
  - server ucciso a sessione aperta (l'adattatore espone il PID del sottoprocesso come `client.pid` e il test lo termina con `os.kill(pid, signal.SIGTERM)`; nessuna dipendenza in più) → `invoke` restituisce stringa che inizia con `"Errore: server MCP non disponibile"` senza bloccarsi oltre il timeout.
- [ ] **Step 2:** pytest → FAIL.
- [ ] **Step 3: Implementare**: thread demone con `asyncio.new_event_loop()`; una coroutine "custode" apre `stdio_client` + `ClientSession` in un `AsyncExitStack`, esegue `initialize()` e `list_tools()`, segnala la prontezza e attende un `asyncio.Event` di chiusura, poi esce dallo stack (così apertura e chiusura avvengono nello stesso task, come richiede anyio). Le chiamate sincrone usano `asyncio.run_coroutine_threadsafe(sessione.call_tool(...), loop).result(timeout)`. Conversione tool: `StructuredTool(name=…, description=…, args_schema=<inputSchema dict>, func=…)`; risultato: testi dei `TextContent` uniti; `isError` → prefisso `Errore: ` se non già presente; eccezioni/timeout → `Errore: server MCP non disponibile (<motivo>)` o `Errore: timeout del server MCP`. Lo stderr del server va al logging, non al terminale dell'utente.
- [ ] **Step 4:** pytest completo → PASS (lanciare due volte per escludere instabilità).
- [ ] **Step 5: Commit** `feat(mcp): adattatore sincrono per il client MCP`; avvisare e attendere l'ok.

### Task 7: Integrazione nell'assistente

**Files:**
- Modify: `assistente/__main__.py`, `assistente/grafo.py` (prompt di sistema), `tests/test_grafo.py`, `tests/test_lmstudio.py`, `tests/test_cli.py` se toccato

**Interfaces:**
- Consumes: `crea_strumenti` (Task 1), `crea_strumenti_api` (Task 4), `ClientMCP`, `comando_convertitore`, `ErroreMCP` (Task 6).
- Produces: `main()` che assembla `crea_strumenti() + client_mcp.strumenti() + crea_strumenti_api(config.scadenze_api_url)`; `prompt_di_sistema(fuso_predefinito)` aggiornato.

- [ ] **Step 1: Test che falliscono** in `tests/test_grafo.py` con `ModelloFinto` e `chiamata_strumento(None, nome=…, args=…)`:
  - `calcola` con `{"espressione": "2 + 2"}` → `ToolMessage` con `"2 + 2 = 4"`;
  - `converti_unita` con il `ClientMCP` vero (fixture di modulo) → `ToolMessage` `"26 mi = 41.8429 km"`;
  - `giorni_tra_date` con il servizio della fixture → `ToolMessage` che termina con l'avvertenza;
  - `prompt_di_sistema("Europe/Rome")` cita `calcola`, `converti_unita`, `giorni_tra_date`, `calcola_scadenza` e contiene `"non calcolare a mente"`.
- [ ] **Step 2:** pytest → FAIL. **Step 3: Implementare** il prompt (aggiungere istruzioni senza togliere quelle sull'orologio) e `main()`: avvio di `ClientMCP` in un blocco `with`, `ErroreMCP` → messaggio `"Server MCP del convertitore non avviato: <motivo>"` su stderr e `return 3`; il `with` garantisce la chiusura anche su Ctrl+C.
- [ ] **Step 4:** pytest completo → PASS.
- [ ] **Step 5: Prova LM Studio** in `tests/test_lmstudio.py` (sotto `@pytest.mark.lmstudio`, richiede servizio API avviato dalla fixture e `ClientMCP`): una domanda per strumento — «Quanto fa (12 + 8) * 3 / 4?», «Quanti chilometri sono 26 miglia?», «Quanti giorni lavorativi ci sono tra il 2026-12-20 e il 2027-01-10?» — verificando la chiamata allo strumento giusto e il risultato nel `ToolMessage`; più «Converti 5 kg in metri» verificando un `ToolMessage` che inizia con `Errore:`. Eseguire `.\.venv\Scripts\python -m pytest --lmstudio -m lmstudio -v -s` con LM Studio attivo e riportare l'esito reale (se un modello piccolo sbaglia, annotarlo, non nasconderlo).
- [ ] **Step 6: Prova manuale** locale: in un terminale `.\.venv\Scripts\python -m scadenze_api`, in un altro caricare `.env` e `.\.venv\Scripts\python -m assistente`, porre le quattro domande, uscire con `/esci` e con Ctrl+C; verificare che non restino processi `convertitore_mcp`.
- [ ] **Step 7: Commit** `feat(grafo): collega calcolatrice, convertitore MCP e API scadenze`; avvisare e attendere l'ok.

### Task 8: Docker Compose, README e CLAUDE.md

**Files:**
- Modify: `Dockerfile` (copiare `convertitore_mcp/` e `scadenze_api/`), `docker-compose.yml` (servizio `scadenze`, `SCADENZE_API_URL: http://scadenze:8000`, `depends_on`), `README.md`, `CLAUDE.md` (sezione Comandi: solo aggiunte)

- [ ] **Step 1:** Aggiornare `Dockerfile` e `docker-compose.yml`; il servizio `scadenze` usa la stessa immagine con `command: ["python", "-m", "scadenze_api"]`.
- [ ] **Step 2: Verifica Docker:** `docker compose build`; `docker compose up -d scadenze`; `"Quanto fa 2 + 2?", "Quanti giorni tra il 2026-01-01 e il 2026-01-31?", "/esci" | docker compose run --rm -T assistente` → risposte sensate; `docker compose run --rm assistente python -m pytest -v` → PASS; `docker compose down`. Riportare l'output reale.
- [ ] **Step 3: README:** tabella strumento/meccanismo; avvio separato di `python -m scadenze_api` e `python -m convertitore_mcp`; nuova variabile `SCADENZE_API_URL`; fonte delle festività; test; diagnosi (server MCP non avviato → codice 3; API non raggiungibile; anno non coperto). Solo comandi eseguiti nei task.
- [ ] **Step 4: CLAUDE.md:** aggiungere in «Comandi» l'avvio del servizio API e del server MCP; non togliere nulla.
- [ ] **Step 5:** pytest completo locale → PASS.
- [ ] **Step 6: Commit** `docs: Docker Compose, README e comandi per tool, MCP e API` (eventualmente separare `build(docker): …`); avvisare e attendere l'ok.
- [ ] **Step 7:** Resoconto finale all'utente: cosa è stato eseguito, con quale esito, cosa resta da provare. Il merge in `dev` solo su richiesta dell'utente.
