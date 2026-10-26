# Assistente del laboratorio — piano di implementazione

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Obiettivo:** costruire un'applicazione da terminale che conversa con `google/gemma-4-e2b` in LM Studio
attraverso un grafo LangGraph scritto a mano, con lo strumento `ora_corrente`, un limite di passaggi,
la cronologia di sessione e l'avvio anche con Docker Compose.

**Architettura:**
- `config.py` legge le variabili d'ambiente.
- `strumenti.py` definisce l'orologio, con un istante iniettabile.
- `grafo.py` contiene stato, nodi `modello`, `strumenti` e `limite_raggiunto`, e la funzione di instradamento.
  Riceve dall'esterno un oggetto con `invoke(messaggi) -> AIMessage`: in produzione è `ChatOpenAI`
  con lo strumento collegato, nei test un modello finto.
- `modello.py` costruisce quel client.
- `cli.py` tiene la cronologia e gestisce il ciclo da terminale.

**Tecnologie:** Python (3.14 in locale con `py`, 3.12 in Docker), `langgraph`, `langchain-openai`,
`tzdata`, `pytest`, Docker Compose.

**Specifica:** `lezione_4/docs/superpowers/specs/2026-10-26-assistente-laboratorio-design.md`

## Vincoli globali

- Radice del progetto: `lezione_4/`. Tutti i percorsi del piano sono relativi a questa cartella
  e tutti i comandi si lanciano da qui. Non toccare nulla fuori da `lezione_4/`.
- Branch corrente `main`. Niente branch o worktree nuovi.
- Niente push.
- Commit in stile Conventional Commits, in italiano.
  - Prima di ogni commit: `git status`, `git diff --cached` e `git add` solo dei file del task.
  - Ogni messaggio finisce con la riga `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Dipendenze fissate, solo queste:
  - `requirements.txt`: `langgraph==1.2.17`, `langchain-openai==1.7.2`, `langchain-core==1.7.0`, `tzdata==2026.5`;
  - `requirements-dev.txt`: `-r requirements.txt` e `pytest==9.1.1`.
  - Nessun'altra dipendenza, nemmeno `python-dotenv`.
- Codice sincrono. Testi per l'utente, prompt di sistema e log in italiano.
- Nessun identificativo di modello nel codice. Il modello viene solo da `LMSTUDIO_MODEL`.
- Nodi e instradamento scritti a mano. Vietati `create_react_agent`, `ToolNode` e `tools_condition`.
- La cronologia vive solo in memoria. Nessun checkpointer.
- Mai versionare `.env`, `.venv/`, `__pycache__/`, `.pytest_cache/`.
- Nella documentazione vanno solo comandi PowerShell verificati.

## Scelte di questo piano (rispetto alla specifica)

1. **Pacchetto in `assistente/` alla radice, invece che in `src/assistente/`**
   (la specifica dava la struttura come indicativa). Così `py -m assistente` e `pytest` funzionano
   senza `PYTHONPATH` e senza installare il pacchetto.
2. **Caricamento del `.env` in locale:** niente `python-dotenv`. Il README documenta una riga
   PowerShell che lo carica nella sessione. In Docker lo carica `env_file`.
3. **Parametri di `ChatOpenAI`:** `temperature=0`, che aiuta il tool calling di un modello piccolo,
   `max_retries=0`, così un LM Studio spento produce subito un messaggio chiaro, e `timeout=120`.
4. **`recursion_limit` del grafo:** `2 * max_passaggi_strumenti + 4`.
5. **Log di `httpx`** portati a `WARNING`, perché a livello `INFO` scriverebbe una riga per ogni richiesta HTTP.

## Punti di attenzione per la revisione

1. **Fuso vuoto o malformato**, per esempio `""` o `"Europe/../Rome"`: lo strumento restituisce
   il messaggio d'errore e non solleva eccezioni. Test nel Task 2.
2. **Argomenti sbagliati nella chiamata**: il modello piccolo può chiamare lo strumento senza argomenti
   o con un nome sbagliato (`{"timezone": "Europe/Rome"}`). Il nodo `strumenti` restituisce un
   messaggio d'errore come risultato e la sessione continua. Test nel Task 3.
3. **Più chiamate nella stessa risposta**: ognuna viene eseguita e riceve il proprio `ToolMessage`
   con il `tool_call_id` giusto. Test nel Task 3.
4. **Errore di LM Studio a metà turno**, anche dopo che uno strumento è già stato eseguito:
   il turno non entra nella cronologia e la sessione continua. Test nel Task 4.
5. **Ctrl+C o fine input durante la sessione**: uscita pulita, senza traceback. Test nel Task 4.

---

### Task 1: Struttura del progetto e configurazione

**File:**
- Crea: `.gitignore`, `requirements.txt`, `requirements-dev.txt`, `pyproject.toml`, `.env.example`
- Crea: `assistente/__init__.py` (vuoto), `assistente/config.py`
- Crea: `tests/__init__.py` (vuoto), `tests/conftest.py`, `tests/test_config.py`

**Interfacce:**
- Produce:
  - `class ErroreConfigurazione(ValueError)`;
  - `@dataclass(frozen=True) class Configurazione` con i campi `base_url: str`, `modello: str`,
    `fuso_predefinito: str`, `max_passaggi_strumenti: int`, `log_level: str`;
  - `carica_configurazione(env: Mapping[str, str] | None = None) -> Configurazione`.
    Con `None` usa `os.environ`.
  - In `tests/conftest.py`: l'opzione `--lmstudio` e il marker `lmstudio`. I test marcati vengono
    saltati se l'opzione manca.

**Contenuto dei file di supporto:**
- `.gitignore`: `.env`, `.venv/`, `__pycache__/`, `*.pyc`, `.pytest_cache/`.
- `pyproject.toml`: solo `[tool.pytest.ini_options]` con `testpaths = ["tests"]` e
  `markers = ["lmstudio: prova reale con LM Studio, richiede --lmstudio"]`.
- `.env.example`, con commenti in italiano:

  ```
  # Copiare in .env. In Docker LMSTUDIO_BASE_URL viene sovrascritto da docker-compose.yml.
  LMSTUDIO_BASE_URL=http://localhost:1234/v1
  # Identificativo restituito da GET /v1/models
  LMSTUDIO_MODEL=google/gemma-4-e2b
  FUSO_ORARIO_PREDEFINITO=Europe/Rome
  MAX_PASSAGGI_STRUMENTI=3
  LOG_LEVEL=INFO
  ```

- [ ] **Passo 1: creare l'ambiente virtuale e installare le dipendenze**

  Comando: `py -m venv .venv; .\.venv\Scripts\python -m pip install -r requirements-dev.txt`
  (dopo aver creato i due file `requirements`).

  Atteso: installazione riuscita su Python 3.14. Se una dipendenza fissata non si installa
  su 3.14, **fermarsi e riferire all'utente**: non cambiare versioni di propria iniziativa.

- [ ] **Passo 2: scrivere i test in `tests/test_config.py`**

  ```python
  BASE = {"LMSTUDIO_BASE_URL": "http://localhost:1234/v1", "LMSTUDIO_MODEL": "google/gemma-4-e2b"}

  def test_valori_predefiniti():
      c = carica_configurazione(BASE)
      assert c.fuso_predefinito == "Europe/Rome"
      assert c.max_passaggi_strumenti == 3
      assert c.log_level == "INFO"

  @pytest.mark.parametrize("mancante", ["LMSTUDIO_BASE_URL", "LMSTUDIO_MODEL"])
  def test_variabile_obbligatoria_mancante(mancante):
      env = {k: v for k, v in BASE.items() if k != mancante}
      with pytest.raises(ErroreConfigurazione, match=mancante):
          carica_configurazione(env)

  def test_variabile_obbligatoria_vuota():
      # anche "   " conta come mancante
      ...  # LMSTUDIO_MODEL="   " → ErroreConfigurazione con "LMSTUDIO_MODEL"

  def test_fuso_predefinito_non_valido():
      # FUSO_ORARIO_PREDEFINITO="Marte/Base" → ErroreConfigurazione con "FUSO_ORARIO_PREDEFINITO"

  @pytest.mark.parametrize("valore", ["0", "-1", "tre"])
  def test_max_passaggi_non_valido(valore):
      # → ErroreConfigurazione con "MAX_PASSAGGI_STRUMENTI"
  ```

- [ ] **Passo 3: eseguire i test e verificare che falliscano**

  Comando: `.\.venv\Scripts\python -m pytest tests/test_config.py -v`

  Atteso: errore di import (`carica_configurazione` non esiste).

- [ ] **Passo 4: implementare `assistente/config.py` e `tests/conftest.py`**
  - Togliere gli spazi iniziali e finali dai valori.
  - Validare il fuso con `zoneinfo.ZoneInfo`, intercettando `ZoneInfoNotFoundError` e `ValueError`.
  - `log_level` passa in maiuscolo.
  - In `conftest.py`, usare `pytest_addoption` per aggiungere `--lmstudio` (`action="store_true"`)
    e `pytest_collection_modifyitems` per aggiungere `skip` agli item con il marker `lmstudio`
    quando l'opzione è assente.

- [ ] **Passo 5: eseguire i test e verificare che passino**

  Comando: `.\.venv\Scripts\python -m pytest -v`

  Atteso: tutti PASS.

- [ ] **Passo 6: commit**

  Prima: `git status` e `git diff --cached`. Controllare che `.venv/` non compaia.

  Commit dei file del task con il messaggio `feat(config): struttura del progetto e lettura della configurazione`.

---

### Task 2: Strumento orologio

**File:**
- Crea: `assistente/strumenti.py`
- Test: `tests/test_strumenti.py`

**Interfacce:**
- Usa: nulla dai task precedenti.
- Produce:
  - `Orologio = Callable[[], datetime]`, che restituisce un `datetime` con fuso, in UTC;
  - `adesso_utc() -> datetime`;
  - `formatta_ora(fuso_orario: str, adesso: Orologio) -> str`;
  - `crea_strumenti(adesso: Orologio = adesso_utc) -> list[BaseTool]`, che restituisce un solo
    strumento, chiamato `ora_corrente`, con l'unico parametro obbligatorio `fuso_orario: str`.
    La descrizione è in italiano e dice di passare un nome IANA, per esempio `Europe/Rome`.

- [ ] **Passo 1: scrivere i test**

  Valori esatti:

  ```python
  AUTUNNO = lambda: datetime(2026, 10, 26, 16, 5, 12, tzinfo=timezone.utc)
  ESTATE  = lambda: datetime(2026, 7, 1, 10, 0, 0, tzinfo=timezone.utc)

  def test_ora_solare_roma():
      assert formatta_ora("Europe/Rome", AUTUNNO) == "2026-10-26T17:05:12+01:00 (Europe/Rome)"
  def test_ora_legale_roma():
      assert formatta_ora("Europe/Rome", ESTATE) == "2026-07-01T12:00:00+02:00 (Europe/Rome)"
  def test_new_york_ancora_in_ora_legale():
      assert formatta_ora("America/New_York", AUTUNNO) == "2026-10-26T12:05:12-04:00 (America/New_York)"
  def test_tokyo_giorno_dopo():
      assert formatta_ora("Asia/Tokyo", AUTUNNO) == "2026-10-27T01:05:12+09:00 (Asia/Tokyo)"

  @pytest.mark.parametrize("fuso", ["Marte/Base", "", "Europe/../Rome"])
  def test_fuso_non_valido(fuso):
      assert formatta_ora(fuso, AUTUNNO) == f"Fuso orario non valido: {fuso!r}"

  def test_strumento_esposto():
      [s] = crea_strumenti(AUTUNNO)
      assert s.name == "ora_corrente"
      assert set(s.args) == {"fuso_orario"}
      assert s.invoke({"fuso_orario": "Europe/Rome"}) == "2026-10-26T17:05:12+01:00 (Europe/Rome)"
  ```

- [ ] **Passo 2: eseguire e verificare che falliscano**

  Comando: `.\.venv\Scripts\python -m pytest tests/test_strumenti.py -v`

  Atteso: errore di import.

- [ ] **Passo 3: implementare**
  - `formatta_ora` converte `adesso()` con `astimezone(ZoneInfo(fuso))` e usa
    `isoformat(timespec="seconds")`.
  - Intercetta `ZoneInfoNotFoundError` e `ValueError`.
  - Lo strumento si crea con `StructuredTool.from_function`, chiudendo `adesso` dentro una funzione
    interna `ora_corrente(fuso_orario: str) -> str`.

- [ ] **Passo 4: eseguire e verificare che passino**

  Comando: `.\.venv\Scripts\python -m pytest -v`

  Atteso: tutti PASS.

- [ ] **Passo 5: commit**

  Messaggio: `feat(strumenti): strumento ora_corrente con fuso orario esplicito`

---

### Task 3: Grafo con instradamento, limite e log

**File:**
- Crea: `assistente/grafo.py`
- Crea: `tests/fakes.py`, con il modello finto condiviso dai test
- Test: `tests/test_grafo.py`

**Interfacce:**
- Usa: `crea_strumenti`, `Orologio` (Task 2).
- Produce:
  - `class StatoConversazione(TypedDict)`:
    `messages: Annotated[list[AnyMessage], add_messages]` e `passaggi_strumenti: int`.
  - `MESSAGGIO_LIMITE: str`. Testo esatto:
    `"Ho raggiunto il limite di passaggi con gli strumenti e non posso completare la risposta a questa domanda."`
  - `prompt_di_sistema(fuso_predefinito: str) -> str`. Il testo, in italiano, dice:
    - sei l'assistente del laboratorio;
    - per data e ora usa sempre `ora_corrente` e non inventare mai l'ora;
    - se l'utente non indica un luogo usa il fuso `{fuso_predefinito}`;
    - rispondi in italiano.
  - `instrada_dopo_modello(stato: StatoConversazione, max_passaggi: int) -> Literal["strumenti", "limite_raggiunto", "__end__"]`.
  - `costruisci_grafo(modello: Runnable, strumenti: list[BaseTool], fuso_predefinito: str, max_passaggi: int) -> CompiledStateGraph`.
    - `modello` riceve una lista di messaggi e restituisce un `AIMessage`; gli strumenti sono già collegati.
    - Nodi con nome `"modello"`, `"strumenti"`, `"limite_raggiunto"`.
    - Archi: `START → modello`; condizionale da `modello` tramite `instrada_dopo_modello`;
      `strumenti → modello`; `limite_raggiunto → END`.
  - `limite_ricorsione(max_passaggi: int) -> int`, che restituisce `2 * max_passaggi + 4`.
  - `tests/fakes.py`:
    - `class ModelloFinto` con `__init__(self, risposte: list[AIMessage | Exception])`;
    - `invoke(self, messaggi, config=None) -> AIMessage`: registra in
      `self.chiamate: list[list[BaseMessage]]` una copia dei messaggi ricevuti, poi restituisce
      la risposta successiva o solleva l'eccezione successiva;
    - `chiamata_strumento(fuso: str | None, id: str = "call_1", nome: str = "ora_corrente", args: dict | None = None) -> AIMessage`.

- [ ] **Passo 1: scrivere i test** (`invoca(grafo, testo)` è un piccolo helper locale che chiama
  `grafo.invoke({"messages": [HumanMessage(testo)], "passaggi_strumenti": 0}, {"recursion_limit": ...})`)

  ```python
  def test_instradamento_senza_chiamate_finisce():          # → "__end__"
  def test_instradamento_con_chiamate_va_agli_strumenti():  # passaggi 0, max 3 → "strumenti"
  def test_instradamento_al_limite():                       # passaggi 3, max 3 → "limite_raggiunto"

  def test_risposta_diretta():
      # ModelloFinto([AIMessage("Ciao!")]) → ultimo messaggio "Ciao!", 1 chiamata al modello
      # il primo messaggio inviato al modello è un SystemMessage che contiene "Europe/Rome"
      # il SystemMessage NON compare nello stato restituito

  def test_ciclo_con_strumento():
      # risposte: chiamata_strumento("Europe/Rome"), AIMessage("Sono le 17:05.")
      # orologio fisso AUTUNNO del Task 2
      # → 2 chiamate al modello; la seconda contiene un ToolMessage con
      #   content "2026-10-26T17:05:12+01:00 (Europe/Rome)" e tool_call_id "call_1"
      # → ultimo messaggio "Sono le 17:05."

  def test_due_chiamate_nella_stessa_risposta():
      # un AIMessage con due tool_calls (Europe/Rome id "a", Asia/Tokyo id "b")
      # → due ToolMessage con tool_call_id "a" e "b" e i rispettivi orari

  @pytest.mark.parametrize("nome,args", [("ora_corrente", {}), ("ora_corrente", {"timezone": "Europe/Rome"}), ("meteo", {"citta": "Roma"})])
  def test_chiamata_errata_diventa_messaggio_di_errore(nome, args):
      # → il ToolMessage ha content che inizia con "Errore" e il grafo arriva alla risposta finale

  def test_limite_passaggi():
      # max_passaggi=2; il modello chiede SEMPRE lo strumento (4 risposte con chiamata)
      # → 3 chiamate al modello, 2 esecuzioni dello strumento
      # → ultimo messaggio == MESSAGGIO_LIMITE
      # → nessun AIMessage nello stato con tool_calls privi del ToolMessage corrispondente

  def test_log_della_chiamata(caplog):
      # a livello INFO, il log del logger "assistente.grafo" contiene "ora_corrente",
      # "Europe/Rome" e il risultato "2026-10-26T17:05:12+01:00"
  ```

- [ ] **Passo 2: eseguire e verificare che falliscano**

  Comando: `.\.venv\Scripts\python -m pytest tests/test_grafo.py -v`

  Atteso: errore di import.

- [ ] **Passo 3: implementare `assistente/grafo.py`**

  I nodi sono funzioni interne a `costruisci_grafo`.

  `modello`:
  - invoca il modello con `[SystemMessage(prompt_di_sistema(...))] + stato["messages"]`;
  - restituisce `{"messages": [risposta]}`.

  `strumenti`:
  - per ogni elemento di `ultimo.tool_calls` cerca lo strumento per nome e chiama `.invoke(args)`;
  - strumento assente → `"Errore: strumento sconosciuto '<nome>'"`;
  - qualunque eccezione → `"Errore: <eccezione>"`;
  - produce `ToolMessage(content=..., tool_call_id=..., name=...)`;
  - scrive i log a livello `INFO`: `chiamata strumento %s con argomenti %s` e `risultato strumento %s: %s`;
  - restituisce i messaggi e `passaggi_strumenti + 1`.

  `limite_raggiunto`:
  - scrive un log a livello `WARNING`;
  - restituisce `{"messages": [RemoveMessage(id=ultimo.id), AIMessage(MESSAGGIO_LIMITE)]}`;
  - `add_messages` assegna l'id agli `AIMessage` che ne sono privi.

- [ ] **Passo 4: eseguire e verificare che passino**

  Comando: `.\.venv\Scripts\python -m pytest -v`

  Atteso: tutti PASS.

- [ ] **Passo 5: commit**

  Messaggio: `feat(grafo): grafo con nodi modello, strumenti e limite di passaggi`

---

### Task 4: Collegamento al modello e interfaccia da terminale

**File:**
- Crea: `assistente/modello.py`, `assistente/cli.py`, `assistente/__main__.py`
- Test: `tests/test_cli.py`, `tests/test_modello.py`

**Interfacce:**
- Usa: `Configurazione`, `carica_configurazione`, `ErroreConfigurazione` (Task 1);
  `crea_strumenti` (Task 2); `costruisci_grafo`, `limite_ricorsione` (Task 3); `ModelloFinto` (Task 3).
- Produce:
  - `crea_modello(config: Configurazione, strumenti: list[BaseTool]) -> Runnable`:
    `ChatOpenAI(base_url=config.base_url, model=config.modello, api_key="lm-studio", temperature=0, max_retries=0, timeout=120).bind_tools(strumenti)`.
  - `descrivi_errore(exc: Exception, base_url: str) -> str`:
    - `openai.APIConnectionError` → `"LM Studio non raggiungibile su <base_url>. È avviato con il server attivo?"`;
    - `openai.APIStatusError` → `"LM Studio ha risposto con un errore (<status_code>): <message>"`;
    - qualunque altra eccezione → `"Errore durante la risposta: <exc>"`.
  - `class Sessione`, in `cli.py`:
    - `__init__(self, grafo, recursion_limit: int)`;
    - `cronologia: list[BaseMessage]`;
    - `chiedi(self, testo: str) -> str`. Invoca il grafo con `cronologia + [HumanMessage(testo)]`
      e `passaggi_strumenti=0`. Solo se l'invocazione riesce, sostituisce la cronologia con i
      `messages` restituiti e ne restituisce l'ultimo contenuto (`"(risposta vuota)"` se è vuoto).
      Se fallisce, rilancia l'eccezione e la cronologia resta invariata.
  - `esegui_ciclo(sessione: Sessione, base_url: str, leggi=input, scrivi=print) -> None`:
    - prompt `"Tu> "`; ignora le righe vuote; `/esci` termina;
    - `EOFError` e `KeyboardInterrupt` terminano senza traceback, stampando `"Arrivederci."`;
    - una risposta si stampa come `"Assistente> " + risposta`;
    - un'eccezione di `chiedi` si stampa con `descrivi_errore` e il ciclo continua.
  - `main() -> int`, in `__main__.py`:
    - carica la configurazione; con un `ErroreConfigurazione` stampa il messaggio su stderr e restituisce `2`;
    - configura il `logging` su stderr con il formato `"%(asctime)s %(levelname)s %(name)s: %(message)s"`
      e porta `httpx` a `WARNING`;
    - costruisce strumenti, modello e grafo;
    - stampa un benvenuto che indica il modello e come uscire;
    - esegue il ciclo e restituisce `0`;
    - si chiude con `raise SystemExit(main())`.

- [ ] **Passo 1: scrivere i test**

  ```python
  # test_cli.py — grafo vero costruito con ModelloFinto e orologio fisso
  def test_la_cronologia_passa_al_turno_successivo():
      # due chiedi(); la seconda chiamata al modello contiene il primo HumanMessage e la prima risposta
  def test_turno_fallito_non_entra_in_cronologia():
      # risposte: chiamata_strumento("Europe/Rome"), RuntimeError("giù"), AIMessage("ok")
      # primo chiedi() solleva RuntimeError e lascia la cronologia vuota
      # il secondo chiedi() restituisce "ok" e la cronologia contiene solo 2 messaggi
  def test_ciclo_esce_con_esci():
      # leggi da una lista ["", "ciao", "/esci"] → una sola chiamata al modello, nessun errore
  @pytest.mark.parametrize("eccezione", [EOFError, KeyboardInterrupt])
  def test_ciclo_esce_senza_traceback(eccezione):
      # leggi solleva l'eccezione → esegui_ciclo ritorna normalmente, l'output contiene "Arrivederci."
  def test_errore_mostrato_e_ciclo_continua():
      # risposte: RuntimeError("giù"), AIMessage("ok"); input ["a", "b", "/esci"]
      # → l'output contiene "Errore durante la risposta: giù" e poi "Assistente> ok"

  # test_modello.py
  def test_descrivi_errore_connessione():
      exc = openai.APIConnectionError(request=httpx.Request("POST", "http://x"))
      assert descrivi_errore(exc, "http://localhost:1234/v1").startswith("LM Studio non raggiungibile su http://localhost:1234/v1")
  def test_descrivi_errore_generico():
      assert descrivi_errore(RuntimeError("boh"), "u") == "Errore durante la risposta: boh"
  def test_main_senza_configurazione(monkeypatch, capsys):
      # cancella LMSTUDIO_BASE_URL e LMSTUDIO_MODEL → main() == 2; stderr contiene "LMSTUDIO_BASE_URL"
  ```

- [ ] **Passo 2: eseguire e verificare che falliscano**

  Comando: `.\.venv\Scripts\python -m pytest tests/test_cli.py tests/test_modello.py -v`

  Atteso: errori di import.

- [ ] **Passo 3: implementare `modello.py`, `cli.py` e `__main__.py` secondo le interfacce**

- [ ] **Passo 4: eseguire tutti i test**

  Comando: `.\.venv\Scripts\python -m pytest -v`

  Atteso: tutti PASS.

- [ ] **Passo 5: prova di avvio senza configurazione**

  Comando: `.\.venv\Scripts\python -m assistente`, in una shell senza le variabili.

  Atteso: messaggio che nomina `LMSTUDIO_BASE_URL`, codice di uscita 2 (`$LASTEXITCODE`), nessun traceback.

- [ ] **Passo 6: commit**

  Messaggio: `feat(cli): collegamento a LM Studio e sessione da terminale`

---

### Task 5: Docker e Docker Compose

**File:**
- Crea: `Dockerfile`, `docker-compose.yml`, `.dockerignore`

**Interfacce:**
- Usa: `python -m assistente` (Task 4) e la suite `pytest`.
- Produce: il servizio Compose `assistente`.

**Contenuto:**
- `Dockerfile`:
  - immagine base `python:3.12-slim`, fissata alla patch esatta trovata con
    `docker run --rm python:3.12-slim python --version`, per esempio `python:3.12.N-slim`;
  - `ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1`;
  - `WORKDIR /app`;
  - copia dei due file `requirements` e `pip install --no-cache-dir -r requirements-dev.txt`,
    con le dipendenze di sviluppo incluse perché i test devono girare anche nel container;
  - copia di `assistente/`, `tests/` e `pyproject.toml`;
  - un utente non root;
  - `CMD ["python", "-m", "assistente"]`.
- `.dockerignore`: `.env`, `.venv`, `__pycache__`, `.pytest_cache`, `.git`, `docs`.
- `docker-compose.yml`, con il servizio `assistente`:
  - `build: .`;
  - `env_file: .env`;
  - `environment: LMSTUDIO_BASE_URL: http://host.docker.internal:1234/v1`;
  - `extra_hosts: ["host.docker.internal:host-gateway"]`;
  - `stdin_open: true` e `tty: true`.

- [ ] **Passo 1: costruire l'immagine**

  Comando: `docker compose build`

  Atteso: build riuscita.

- [ ] **Passo 2: eseguire i test nel container**

  Comando: `docker compose run --rm assistente python -m pytest -v`

  Atteso: tutti PASS e i test `lmstudio` saltati. Se `.env` manca, crearlo prima con
  `Copy-Item .env.example .env`, che resta fuori da Git.

- [ ] **Passo 3: verificare la configurazione effettiva**

  Comando: `docker compose run --rm assistente python -c "import os; print(os.environ['LMSTUDIO_BASE_URL'])"`

  Atteso: `http://host.docker.internal:1234/v1`.

- [ ] **Passo 4: commit**

  Messaggio: `feat(docker): immagine e servizio Compose per l'assistente`. Controllare che `.env` non sia nello staging.

---

### Task 6: Prova reale, README e CLAUDE.md

**File:**
- Crea: `tests/test_lmstudio.py`, `README.md`
- Modifica: `CLAUDE.md`. Oggi non è tracciato; questo task lo aggiunge a Git.

**Interfacce:**
- Usa: `carica_configurazione`, `crea_strumenti`, `crea_modello`, `costruisci_grafo`, `limite_ricorsione`.

- [ ] **Passo 1: scrivere `tests/test_lmstudio.py`, marcato `lmstudio`**

  ```python
  @pytest.mark.lmstudio
  def test_il_modello_reale_usa_lo_strumento():
      # configurazione dalle variabili d'ambiente; grafo reale
      # domanda: "Che ore sono adesso a Tokyo?"
      # assert: almeno un AIMessage con una tool_call di nome "ora_corrente"
      # assert: almeno un ToolMessage il cui content contiene "(Asia/Tokyo)"
      # assert: l'ultimo messaggio è un AIMessage senza tool_calls e con testo non vuoto
  ```

- [ ] **Passo 2: verificare che senza opzione il test venga saltato**

  Comando: `.\.venv\Scripts\python -m pytest -v`

  Atteso: tutti PASS, 1 skipped.

- [ ] **Passo 3: prova reale in locale**

  Comando: caricare `.env` con la riga PowerShell del README, poi
  `.\.venv\Scripts\python -m pytest --lmstudio -m lmstudio -v -s`.

  Atteso: PASS. Se fallisce, una sola iterazione per migliorare la descrizione dello strumento o il
  prompt di sistema, senza cambiare modello. Se fallisce ancora, **registrare l'esito e i log
  così come sono** e riferire all'utente.

- [ ] **Passo 4: sessione reale in locale**

  Comando: `"Che ore sono?", "E a New York?", "/esci" | .\.venv\Scripts\python -m assistente`

  Atteso:
  - nei log, due righe `chiamata strumento ora_corrente`, la prima con `Europe/Rome`
    e la seconda con `America/New_York`, perché la seconda domanda si capisce solo con la cronologia;
  - risposte coerenti con i risultati dello strumento.

  Riportare l'esito reale.

- [ ] **Passo 5: sessione reale in Docker**

  Comando: `"Che ore sono?", "/esci" | docker compose run --rm -T assistente`

  Atteso: chiamata allo strumento nei log e risposta. Se la connessione fallisce, verificare in
  LM Studio l'opzione per servire sulla rete locale e documentarla. Riportare l'esito reale.

- [ ] **Passo 6: scrivere `README.md` con i soli comandi verificati nei passi precedenti**
  - **Requisiti:** LM Studio con `google/gemma-4-e2b` caricato e il server avviato; Python con `py`; Docker Desktop.
  - **Configurazione:** `Copy-Item .env.example .env`; come leggere l'id con
    `Invoke-RestMethod http://localhost:1234/v1/models`; la riga per caricare `.env` in PowerShell:

    ```powershell
    Get-Content .env | Where-Object { $_ -match '^\s*[^#\s][^=]*=' } | ForEach-Object { $k, $v = $_ -split '=', 2; Set-Item "env:$($k.Trim())" $v.Trim() }
    ```

  - **Avvio:** in locale e in Docker.
  - **Test:** suite normale, suite nel container, prova reale con `--lmstudio`.
  - **Checklist manuale**, dalla specifica §7: domanda senza luogo, domanda con luogo, domanda di
    seguito, fuso inesistente, LM Studio spento.
  - **Struttura del grafo** in un diagramma Mermaid scritto a mano.
  - **Diagnosi:** LM Studio non raggiungibile, in locale e da Docker; modello che non chiama lo
    strumento; variabile mancante.

- [ ] **Passo 7: aggiornare `CLAUDE.md`**
  - La cartella del progetto è `lezione_4/` e i documenti stanno in `lezione_4/docs/superpowers/`.
  - Aggiungere una sezione «Comandi» con gli stessi comandi verificati di test e avvio.

- [ ] **Passo 8: commit**

  Due commit separati:
  - `test(lmstudio): prova reale dello strumento con il modello locale`
  - `docs: README con configurazione, avvio, test e diagnosi; aggiorna CLAUDE.md`

- [ ] **Passo 9: resoconto all'utente**
  - Che cosa è stato eseguito e con quale esito: suite locale, suite in Docker, prova `--lmstudio`,
    sessione locale, sessione Docker.
  - Che cosa resta da provare a mano: la checklist interattiva con TTY in Docker, il caso di LM Studio spento.
