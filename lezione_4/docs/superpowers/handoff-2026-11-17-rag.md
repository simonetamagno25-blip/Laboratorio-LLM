# Handoff — lezione 7, RAG: specifica e piano pronti

Data: 2026-11-17 · Branch: `feat/rag`, creato da `feat/agente-web` (su `dev` manca il lavoro della
lezione 6). `main` e `dev` non toccati.

Fonte: `slide lezioni/LLM_Lez_7.pdf` («Dai documenti alla ricerca semantica: introduzione al RAG e
ingestion»), fuori da Git di proposito.

## Stato
- `CLAUDE.md` aggiornato con le regole stabili del RAG (commit `59f238f`); `.gitignore` esclude
  `dati/` e `slide lezioni/`.
- Specifica dell'esercizio 1 approvata: `specs/2026-11-17-rag-ingestion-design.md` (commit `cc91ca1`).
- Piano scritto e verificato sulla libreria: `plans/2026-11-17-rag-ingestion.md` (10 task).
- **Nessun codice scritto.** L'implementazione non è iniziata.
- Le modifiche A (`contiene_dosi`) e B (titolo nel testo indicizzato) dell'esercizio 2 avranno
  ciascuna il proprio ciclo: specifica, piano, implementazione, nuova valutazione.

## Decisioni prese con l'utente
- Pacchetto `rag/` dentro `lezione_4/`, separato da `assistente/`.
- Una ricetta = un documento; chunking **per paragrafi interi** accorpati fino a 1200 caratteri
  con overlap 200, senza superare il confine della ricetta (consigliato e accettato).
- Chiamate dirette: `httpx` verso `/v1/embeddings` e `qdrant-client==1.20.0`, niente wrapper
  LangChain.
- ID stabili (`uuid5` di `documento_id:posizione`) e upsert; rimozione dei punti orfani.
- Esecuzione del piano: **diretta** (implementa la sessione principale), con una revisione
  indipendente dopo il task 3 (corpus e chunking, controllati anche con `--solo-analisi` sul
  file reale) e una revisione dell'intero branch alla fine. Proposta in conversazione, l'utente
  ha chiesto handoff, commit e push prima di partire: confermarla alla ripresa.

## Fatti verificati (2026-11-17)
- LM Studio: `GET /v1/models` restituisce `google/gemma-4-e2b` e
  `text-embedding-nomic-embed-text-v1.5`; `/v1/embeddings` con una lista di testi restituisce
  vettori di **768** dimensioni con `index`.
- `qdrant-client` 1.20.0 (Python 3.14): metadati della collezione funzionanti anche in `:memory:`;
  upsert idempotente, filtro in `query_points`, `count`, `scroll`, `delete`, `collection_exists`
  provati. In `:memory:` l'indice sul payload non ha effetto (avviso atteso): si verifica sul
  server. Qdrant spento → `ResponseHandlingException` in circa 4 s.
- Immagine `qdrant/qdrant:v1.20.2` presente su Docker Hub.
- Corpus: `www.gutenberg.org` era in manutenzione (503); il mirror
  `https://gutenberg.pglaf.org/5/9/0/4/59047/59047-0.txt` funziona. 790 ricette senza buchi,
  23 capitoli (elenco e prima ricetta di ciascuno nel piano, Task 2). Trappole del testo: il
  sovratitolo `MINESTRE` con la sua introduzione, le introduzioni dei capitoli (es. la lettera prima
  della 637), le righe maiuscole interne alle ricette (`PASTA FROLLA`, `RICETTA A`), i rimandi
  «N. 14», l'appendice e l'indice dopo la 790.
- Fonti delle domande in aula: 7, 89, 208 (capitolo Fritti), 455/456; domande nuove: 222, 71, 675;
  senza risposta: tiramisù, carbonara.

## Come riprendere
1. `git status` e `git log --oneline -5` su `feat/rag`.
2. Leggere specifica e piano; confermare con l'utente la modalità di esecuzione.
3. Scaricare il corpus in `dati/artusi.txt` (comando nel piano, Task 9 Step 1).
4. Eseguire il piano dal Task 1 con `superpowers:executing-plans`.
5. Per i task 9–10: Docker Desktop acceso (oggi era spento), LM Studio con il modello di
   embedding caricato, `.env` con `LMSTUDIO_EMBEDDING_MODEL=text-embedding-nomic-embed-text-v1.5`.

## Attenzioni
- Dopo ogni commit scrivere «ho fatto il commit»; push solo su richiesta dell'utente.
- Pytest raccoglie le funzioni importate che iniziano con `test` (`testo_da_indicizzare`): nei
  test importare il modulo.
- Per i commit usare `git commit -- <percorsi>`.
