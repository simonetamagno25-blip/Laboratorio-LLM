# Handoff — lezione 6, step 1: router

Data: 2026-11-14 · Branch: `feat/lezione-6`, creato da `feat/note`, solo locale, niente push ·
`main` e `dev` non toccati.

## Contesto
- Esercitazioni della lezione 6 («Esercitazioni di laboratorio: evolvere l'agente»). La fonte di
  verità è `LLM_Lez_6.pdf`, nella cartella `lezione_4/`, non versionato (6,5 MB).
- Gli step vanno fatti uno alla volta, da 1 a 9. La checklist è in `docs/ROADMAP.md`.
- Regole fissate dall'utente:
  - specifica e piano approvati prima del codice;
  - test simulati separati dalle prove reali con LM Studio;
  - evidenze verificabili nei log o nei test;
  - README aggiornato e un commit per ogni incremento;
  - alla fine di ogni step ci si ferma e si aspetta il via.
- Il push si fa solo su richiesta esplicita. Dopo ogni commit va scritto «ho fatto il commit».
- Prima dei commit di questo step, su richiesta dell'utente è stato fatto il push di `feat/note` su
  `origin/feat/note` (17 commit). Quei commit **non** sono in `dev`: la PR o il merge vanno fatti
  solo su richiesta.

## Decisioni prese con l'utente (step 1)
| Tema | Decisione |
|---|---|
| Branch | `feat/lezione-6`, creato da `feat/note` |
| Ambito | variabile `AMBITO_AGENTE` nel `.env`, obbligatoria (codice di uscita 2 se manca) |
| Ampiezza dell'ambito | strumenti del laboratorio, temi del corso (DL, LLM, agenti, LangGraph, MCP), saluti e domande sull'assistente. Così allo step 5 `spiega "Model Context Protocol"` passa dal router |
| Output del router non valido | fail-open: la domanda va all'agente, con un `WARNING` nei log |

Documenti: `specs/2026-11-14-router-design.md` e `plans/2026-11-14-router.md`, entrambi approvati.
Esecuzione «diretta», senza sotto-agenti per ogni task.

## Commit sul branch
1. `652dbbd` docs: roadmap, specifica e piano.
2. `d4e52a8` feat(config): campo `Configurazione.ambito`, ultimo campo del dataclass, letto da
   `AMBITO_AGENTE`. La riga è in `.env.example`, senza virgolette, ed è stata aggiunta anche al
   `.env` locale, non versionato.
3. `4c8b160` feat(router): `assistente/router.py` con
   - `DecisioneRouter` (`categoria`: `conversazione` | `fuori_ambito`, più `motivo`);
   - `prompt_router(ambito)`, che non nomina gli strumenti;
   - `testo_da_classificare(messaggi, turni=3, massimo=300)`, che usa solo domande e risposte
     finali, senza tool call né `ToolMessage`, e mette la domanda corrente in fondo;
   - `messaggio_rifiuto(ambito)`.
4. `b931bae` feat(modello): helper `_chat(config)` condiviso;
   `crea_router(config) = _chat(config).with_structured_output(DecisioneRouter, method="json_schema", include_raw=True)`.
5. `7313225` feat(grafo):
   - il nodo `modello` si chiama ora `agente`;
   - nuovi nodi `router` e `rifiuto`, più `instrada_dopo_router`;
   - nuovi parametri keyword di `costruisci_grafo`: `router=None` e `ambito=""`. Senza router il
     grafo resta `START → agente`; con il router e l'ambito vuoto solleva `ValueError`;
   - nuovi campi di stato `categoria` e `motivo`;
   - `limite_ricorsione = 3 * max_passaggi + 6`;
   - `RouterFinto` in `tests/fakes.py`.
6. `9473df1` feat(cli): `__main__` passa `router=crea_router(config), ambito=config.ambito`.

Righe di log usate come evidenza:
- `router: categoria=<c> motivo=<m> -> <agente|rifiuto>`
- `agente: chiamata al modello`
- `rifiuto: domanda fuori ambito, agente non eseguito`
- `WARNING router: output non valido (...), la domanda passa all'agente`

## Verifiche eseguite
- Test automatici: `.\.venv\Scripts\python -m pytest -q` → **325 passati, 21 saltati**. I 21 sono
  le prove LM Studio, comprese le 4 nuove del router. All'inizio dello step erano 305 passati e
  17 saltati.
- I test simulati coprono:
  - in ambito: log nell'ordine router → agente;
  - fuori ambito: l'agente non viene mai chiamato e non c'è nessuna riga `agente:`;
  - output non valido: va all'agente con un `WARNING`;
  - domanda in ambito che usa uno strumento;
  - conferma delle note con il router davanti: la ripresa non riesegue il router;
  - errore del router a metà sessione: la cronologia resta intatta;
  - all'avvio il grafo ha davvero il nodo `router`.
- **Prove reali con LM Studio: non eseguite.** LM Studio era spento: connessione rifiutata su
  `127.0.0.1:1234`.

## Lavoro non committato
- `tests/test_lmstudio.py`:
  - `grafo_completo` passa ora router e ambito;
  - 4 nuovi test: `test_router_in_ambito_con_strumento`, `test_router_fuori_ambito`,
    `test_router_tema_del_corso`, `test_router_follow_up`.

  Va committato (`test(router): prove reali con LM Studio dei due percorsi`) solo dopo averli
  eseguiti con esito positivo.

## Da fare (resto del piano: Task 6 e 7, poi la revisione finale)
1. Avviare LM Studio con `google/gemma-4-e2b` caricato e il server su `:1234`, poi caricare `.env`
   nella sessione (comando nel CLAUDE.md).
2. `.\.venv\Scripts\python -m pytest --lmstudio -m lmstudio -k router -v -s` → atteso 4 PASS.
   - Se `json_schema` non funziona con il modello, **fermarsi** e concordare con l'utente il passaggio
     a `method="function_calling"`.
   - Se il router sbaglia la categoria, valutare con l'utente la formulazione del prompt o
     dell'ambito.
3. Prova manuale con i log:
   - avviare `.\.venv\Scripts\python -m scadenze_api` in un'altra finestra;
   - `$env:LOG_LEVEL="INFO"`;
   - `"Che ore sono a Tokyo?", "Dammi la ricetta della carbonara", "/esci" | .\.venv\Scripts\python -m assistente`.

   Salvare l'output come evidenza e controllare che il testo del rifiuto non contenga virgolette.
4. Commit dei test reali.
5. Task 7:
   - README: `AMBITO_AGENTE` in «Configurazione», diagramma mermaid con `router`/`agente`/`rifiuto`
     e campi `categoria`/`motivo`, comando `-k router` in «Test», righe di log e «domanda valida
     rifiutata → allargare `AMBITO_AGENTE`» in «Diagnosi», due domande in «Checklist manuale»;
   - spuntare `docs/ROADMAP.md`;
   - CLAUDE.md solo se serve.

   Poi commit `docs: router e ambito dell'agente nel README e roadmap`.
6. Revisione finale dell'intero branch: pacchetto da `git merge-base feat/note HEAD` a `HEAD`,
   revisore indipendente, correzione dei rilievi importanti con TDD.
7. Resoconto all'utente: cosa è stato eseguito e con quale esito, cosa resta da provare (suite reale
   completa, 23–29 minuti, solo su richiesta; Docker) e come verificare le evidenze. Poi **fermarsi**
   e aspettare il via per lo step 2.

## Note
- Registro di avanzamento (non versionato): `repo-lab-llm/.superpowers/sdd/2026-11-14-router/progress.md`.
- Ruling registrato: pytest raccoglieva `testo_da_classificare` importata nei test, perché il nome
  inizia con «test». Nei test si importa ora il modulo (`router.testo_da_classificare`) e il nome
  dell'interfaccia resta invariato.
- Differenze rispetto al prompt dell'utente, già segnalate:
  - il PDF non è in `docs/`;
  - il server MCP si chiama `convertitore_mcp`, non "orologio", e l'orologio è uno strumento
    locale. Conterà negli step 4–5;
  - allo step 9 serve `compose.yaml`, mentre oggi il file è `docker-compose.yml`.
- Resta aperto, da `feat/note`, il difetto «elenco delle note preso dalla cronologia» (vedi
  `handoff-2026-11-09-note.md`): fuori dallo scopo di questo step.
- Docker non è stato provato in questo step. `AMBITO_AGENTE` arriva al container tramite
  `env_file: .env`, senza modifiche a `docker-compose.yml`.
