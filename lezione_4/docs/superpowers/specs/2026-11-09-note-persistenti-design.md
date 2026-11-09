# Note persistenti — specifica

Data: 2026-11-09 · Esercizio «Intermedio: Note persistenti» · Stato: approvata dall'utente il 2026-11-09.

Secondo dei tre esercizi intermedi (catalogo, note persistenti, meteo). Il catalogo è concluso
(PR #2); il meteo seguirà con specifica e piano propri.

## 1. Intento

L'assistente del laboratorio (`lezione_4/`) ha orologio, calcolatrice e catalogo (tool locali),
convertitore (MCP) e giorni/scadenze (API). Si aggiungono le **note personali**: promemoria che
l'utente detta quando gli viene in mente qualcosa e ritrova quando gli serve, anche in una
sessione successiva.

Uso descritto dall'utente:
- «devo notare qualcosa che mi serve e poi, nel momento del bisogno, ritrovo la nota»;
- per ritrovarla **descrive quella che cerca** (non scorre tutto l'elenco);
- per cancellarla «gli dico la nota da cancellare, lui mi dice la nota così vedo se è quella
  corretta e poi gli dico sì, elimina questa».

L'esercizio allena **tool con effetti e conferme**: per la prima volta uno strumento scrive dati
che sopravvivono alla sessione, e un'azione distruttiva (l'eliminazione) avviene solo dopo un «sì»
esplicito dell'utente, chiesto dal programma e non affidato alla buona volontà del modello.

**Persistenza e `CLAUDE.md`.** La regola «nessuna persistenza» del `CLAUDE.md` riguarda la
**cronologia della conversazione**, che continua a sparire alla chiusura. Le note sono un dato
diverso e sono persistenti per definizione dell'esercizio.

Successo, con il modello reale di LM Studio (archivio di prova vuoto all'inizio):

| Richiesta dell'utente | Comportamento atteso |
|---|---|
| «Annota che il sensore SEN-004 va ricalibrato» | chiama `aggiungi_nota`; la nota è salvata, senza conferma |
| «Cosa avevo scritto sul sensore?» | chiama `cerca_note` con una parola chiave; risponde con la nota trovata |
| «Quali note ho?» | chiama `elenca_note`; elenca le note salvate |
| «Cosa avevo scritto sulla stampante?» | `cerca_note` senza risultati; dice che non c'è, senza inventare |
| «Elimina la nota sul sensore» + «sì» | trova la nota (`cerca_note`), chiede `elimina_nota`; il programma mostra la nota e chiede conferma; con «sì» la nota sparisce |
| come sopra + «no» | la nota resta; l'assistente dice che non è stata eliminata |

E fuori dal modello: una nota aggiunta, chiusa e riaperta l'applicazione, è ancora lì (in locale e
in Docker con il volume).

## 2. Obiettivi, non obiettivi, anti-obiettivi

**Obiettivi**
- Archivio SQLite su file, con `sqlite3` della libreria standard (nessuna dipendenza nuova).
- Quattro tool locali: `aggiungi_nota`, `elenca_note`, `cerca_note`, `elimina_nota`.
- Conferma dell'eliminazione **nel grafo LangGraph**: il grafo si ferma prima di eseguire
  `elimina_nota`, il terminale mostra la nota presa dall'archivio e chiede sì/no.
- Percorso del file da variabile d'ambiente; in Docker il file sta su un volume e sopravvive
  alla ricreazione del container.

**Non obiettivi**
- Modificare una nota esistente (si elimina e se ne aggiunge un'altra).
- Conferma per l'aggiunta: l'utente ha scelto che l'aggiunta avvenga subito.
- Eliminare più note in un colpo solo, o «elimina tutte».
- Ricerca «intelligente» (sinonimi, errori di battitura, embedding/RAG).
- Categorie, etichette, scadenze o promemoria a orario sulle note.
- Persistenza della cronologia della conversazione.

**Anti-obiettivi** (fallimento anche se «funziona»)
- Una nota eliminata senza un «sì» dell'utente, anche se il modello «dice» di aver chiesto.
- La conferma mostra il testo scritto dal modello invece di quello salvato nell'archivio.
- Un risultato vuoto muto (stringa o lista vuota) che lascia il modello libero di inventare note.
- Il modello cita note che gli strumenti non hanno restituito.
- Il file del database finisce in Git o nell'immagine Docker.
- Un numero di nota riusato dopo un'eliminazione (si rischia di confermare la nota sbagliata).

## 3. Vincoli

Valgono tutti quelli del `CLAUDE.md` di `lezione_4/`: codice sincrono, moduli piccoli, test senza
modello attivo, prove LM Studio separate e attivate esplicitamente, comandi PowerShell, README
aggiornato con soli comandi verificati, Conventional Commits in italiano.

## 4. Archivio

**File e configurazione.** Variabile d'ambiente facoltativa `PERCORSO_DB_NOTE` (nome mio, in linea
con le altre variabili in italiano). Predefinito: `note.sqlite3` nella cartella da cui si avvia
l'assistente (`lezione_4/`). La cartella che contiene il file viene creata se manca. Il valore va
in `Configurazione` e in `.env.example`.

**Tabella** (scelta mia):

| Colonna | Tipo | Note |
|---|---|---|
| `id` | `INTEGER PRIMARY KEY AUTOINCREMENT` | il «numero» della nota; `AUTOINCREMENT` impedisce il riuso dopo un'eliminazione |
| `testo` | `TEXT NOT NULL` | testo della nota, spazi iniziali e finali tolti |
| `creata` | `TEXT NOT NULL` | data e ora di creazione, ISO 8601 con fuso (`2026-11-09T10:30:00+01:00`) |

La data di creazione è nel fuso `FUSO_ORARIO_PREDEFINITO`. L'orologio è iniettabile, come per
`ora_corrente`, così i test controllano l'istante.

**Apertura.** All'avvio l'archivio si apre e crea la tabella se non c'è (`CREATE TABLE IF NOT
EXISTS`). Se l'apertura fallisce (cartella non creabile, file non scrivibile, file che non è un
database SQLite) l'assistente non parte e stampa `Archivio note non disponibile: <motivo>`, codice
di uscita 5, come per gli altri errori di avvio. L'apertura avviene prima del server MCP, come il
catalogo, così non resta nessun sottoprocesso da chiudere.

**Connessione** (lasciato al builder): una connessione aperta all'avvio e chiusa all'uscita,
oppure una per operazione; in ogni caso ogni scrittura è confermata (`commit`) subito, così una
chiusura brusca (Ctrl+C) non perde le note già salvate. Le query usano sempre parametri (`?`),
mai testo concatenato.

**Ricerca.** Le note sono poche: si leggono tutte e si filtrano in Python, con la stessa regola
del catalogo (sottostringa, tutte le parole, `casefold` e accenti tolti con `unicodedata`). SQLite
`LIKE` non gestisce gli accenti, quindi non si usa per il confronto. Se il catalogo ha già una
funzione di normalizzazione riusabile, la si riusa (eventualmente spostandola in un modulo
comune); il builder decide.

## 5. Strumenti

Le operazioni sull'archivio stanno in un modulo proprio (per esempio `assistente/note.py`),
testato a parte con file temporanei; i tool LangChain in `crea_strumenti` sono un involucro
sottile. Restituiscono testo, come gli strumenti esistenti. Formato di una nota nei risultati
(scelta mia): `Nota 3 (2026-11-02 14:05): il sensore SEN-004 va ricalibrato`.

### `aggiungi_nota(testo: str)`
Descrizione per il modello: salva una nota personale dell'utente, che resta disponibile anche
nelle sessioni successive; il testo va riportato come l'utente l'ha detto.
- Testo vuoto o di soli spazi → `Errore: il testo della nota è vuoto.`
- Testo oltre 500 caratteri → errore con il limite (scelta mia).
- Esito: `Nota 3 salvata: il sensore SEN-004 va ricalibrato`.

### `elenca_note()`
Descrizione: elenca le note salvate, dalla più vecchia alla più recente.
- Ordine per numero. Al massimo 20 note; se ce ne sono di più, le **20 più recenti** e una riga
  finale che dice quante sono state omesse e suggerisce `cerca_note` (scelta mia).
- Nessuna nota → `Non ci sono note salvate.`

### `cerca_note(testo: str)`
Descrizione: cerca tra le note salvate quelle che contengono tutte le parole indicate; usare una
o due parole chiave brevi, al singolare.
- Regola di confronto del §4. Ordine per numero, al massimo 20 risultati con riga di omissione.
- Testo vuoto → errore che suggerisce `elenca_note`.
- Nessun risultato → `Nessuna nota trovata per "stampante". Non ci sono note corrispondenti.`

### `elimina_nota(numero: int)`
Descrizione: elimina una nota dato il suo numero; se non conosci il numero usa prima `cerca_note`
o `elenca_note`. Il programma chiederà conferma all'utente prima di eliminare.
- Lo strumento in sé elimina e basta: **la conferma non è nello strumento** ma nel grafo (§6).
  La funzione dell'archivio resta comunque testabile da sola.
- Numero inesistente → `Nota 7 non trovata. Usa cerca_note o elenca_note per trovare il numero giusto.`
- Esito: `Nota 3 eliminata.`

## 6. Conferma nel grafo

Meccanismo (scelta mia): **`interrupt()` di LangGraph** con un checkpointer in memoria
(`InMemorySaver`, già incluso nell'installazione di `langgraph`, nessuna dipendenza nuova). È il
meccanismo di LangGraph per l'intervento umano: il grafo si ferma, il programma raccoglie la
risposta e riprende con `Command(resume=...)`. Il checkpointer è in memoria e sparisce alla
chiusura, quindi la cronologia resta non persistente. Alternativa scartata: passare al grafo una
funzione che legge dal terminale; più semplice, ma mette l'input/output dentro un nodo e la pausa
non si vede nel grafo.

**Forma del grafo.** Si aggiunge un nodo `conferma_eliminazione` fra `modello` e `strumenti`:

```
modello --(chiamate, sotto il limite, c'è elimina_nota)--> conferma_eliminazione --> strumenti
modello --(chiamate, sotto il limite, nessuna elimina_nota)--> strumenti
```

Il resto (limite dei passaggi, `limite_raggiunto`, ritorno a `modello`) resta com'è; il controllo
del limite viene prima di quello dell'eliminazione.

**Comportamento del nodo.**
1. Per la chiamata `elimina_nota` legge la nota **dall'archivio** con il numero richiesto.
2. Numero inesistente o non valido: nessuna pausa; lo strumento risponderà «non trovata».
3. Nota esistente: `interrupt` con i dati della nota (numero, data, testo salvato). Il terminale
   mostra: `Eliminare la nota 3 (2026-11-02 14:05): "il sensore SEN-004 va ricalibrato"? [sì/no]`.
4. La decisione viene registrata nello stato (per esempio un campo con gli id delle chiamate
   confermate); il nodo `strumenti` esegue `elimina_nota` **solo** se confermata, altrimenti
   produce il `ToolMessage` `Eliminazione annullata dall'utente: la nota 3 non è stata eliminata.`
5. Una nota alla volta: se nello stesso messaggio il modello chiede più `elimina_nota`, solo la
   prima va in conferma; le altre ricevono `Errore: elimina una nota alla volta.` (scelta mia).
6. Le altre chiamate dello stesso messaggio (per esempio una `cerca_note`) si eseguono normalmente.

Garanzia da rispettare comunque lo si implementi: **nessun percorso del grafo esegue
`elimina_nota` senza una conferma registrata per quella chiamata.**

**Risposta di conferma.** «sì», «si», «s» (maiuscole e spazi non contano) confermano; qualunque
altra risposta, compresa una riga vuota, annulla. Ctrl+C o fine dell'input durante la conferma:
nessuna eliminazione, l'assistente si chiude con «Arrivederci.» come oggi.

**Ambiguità.** Se la descrizione dell'utente corrisponde a più note, il modello le elenca e chiede
quale; la conferma sì/no arriva solo con un numero preciso. È un comportamento chiesto al modello
dal prompt e dalle descrizioni dei tool, non imposto dal codice; nella prova reale si osserva.

## 7. Sessione e terminale

- **Un `thread_id` nuovo per ogni domanda** (scelta mia). La cronologia resta nella lista
  `Sessione.cronologia`, passata al grafo come oggi e aggiornata solo quando il turno finisce bene;
  il checkpointer serve soltanto a fermare e riprendere il grafo *dentro* il turno. Così resta
  vero il comportamento attuale: un turno fallito (LM Studio spento, errore del modello) non entra
  nella cronologia (`test_turno_fallito_non_entra_in_cronologia` resta valido così com'è).
  Alternativa scartata: un `thread_id` fisso con la cronologia nel checkpointer, che salva lo stato
  dopo ogni passo e lascerebbe nella cronologia i turni falliti a metà.
- Caso limite accettato: l'utente conferma, la nota viene eliminata, poi la chiamata successiva al
  modello fallisce. La cronologia non conserva quel turno, ma l'archivio sì: la nota è eliminata
  davvero e una domanda successiva lo mostra tramite gli strumenti. L'archivio, non la cronologia,
  è la fonte di verità sulle note.
- Quando il grafo si ferma per la conferma, la sessione restituisce al ciclo una richiesta di
  conferma invece di una risposta; il ciclo stampa la domanda, legge la risposta con il prompt
  `Conferma> ` e fa riprendere il grafo. La forma esatta (valore di ritorno, metodo separato) è
  lasciata al builder.
- Funziona anche con input da pipe (`"Elimina la nota 1", "sì", "/esci" | docker compose run --rm -T assistente`).
- Prompt di sistema: una frase che dice di usare `aggiungi_nota` quando l'utente chiede di
  annotare o ricordare qualcosa, `cerca_note`/`elenca_note` per ritrovare le note, `elimina_nota`
  con il numero per cancellarle (la conferma la chiede il programma), e di non citare note che gli
  strumenti non hanno restituito. Dopo la modifica si rieseguono **tutte** le prove reali (lezione
  del catalogo: ogni frase nuova può peggiorare altri strumenti).

## 8. Docker e Git

- `docker-compose.yml`: volume con nome (per esempio `note`) montato nel servizio `assistente`
  (per esempio su `/app/note`), e `PERCORSO_DB_NOTE` impostato in `environment` sul file dentro il
  volume.
- `Dockerfile`: la cartella di montaggio esiste nell'immagine ed è dell'utente `app`, così il volume
  nuovo eredita i permessi e il processo non root può scrivere.
- `.gitignore` e `.dockerignore`: escludono `*.sqlite3` (e i file temporanei di SQLite
  `*.sqlite3-journal`), così l'archivio locale non entra né in Git né nell'immagine.
- `docker compose down` non tocca il volume; `docker compose down -v` lo cancella con le note:
  va scritto nel README.

## 9. Test

Automatici (senza modello), con file temporanei (`tmp_path`):
- archivio: aggiunta, elenco, ricerca (una parola, più parole, maiuscole, accenti, nessun
  risultato), eliminazione esistente e inesistente, numero non riusato dopo un'eliminazione,
  testo vuoto e troppo lungo, limite di 20 con riga di omissione, data con orologio controllato;
- persistenza: aggiunta con un'istanza, chiusura, riapertura con una nuova istanza sullo stesso
  file → la nota c'è;
- apertura fallita: file che non è un database, percorso non scrivibile → errore chiaro;
  `__main__` esce con codice 5;
- configurazione: `PERCORSO_DB_NOTE` predefinito e personalizzato;
- i quattro tool compaiono in `crea_strumenti` con nome e descrizione;
- grafo con modello simulato:
  - `elimina_nota` su nota esistente → il grafo si ferma con i dati presi dall'archivio;
    ripresa con «sì» → nota eliminata e `ToolMessage` di esito; ripresa con «no» → nota ancora
    presente e `ToolMessage` di annullamento;
  - `elimina_nota` su numero inesistente → nessuna pausa, «non trovata»;
  - due `elimina_nota` nello stesso messaggio → una sola conferma, la seconda riceve l'errore;
  - `aggiungi_nota` → nessuna pausa;
  - i test esistenti del grafo (limite dei passaggi, chiamate non valide, strumenti sconosciuti)
    restano verdi;
- terminale: flusso di conferma con `leggi` finto (sì, no, riga vuota, Ctrl+C/EOF durante la
  conferma), cronologia conservata fra le domande.

Prova reale con LM Studio (marcatore `lmstudio`, opzione `--lmstudio`), su un archivio temporaneo:
le richieste del §1, con **asserzioni** sulle chiamate agli strumenti (nome e, dove conta,
argomento: il numero giusto in `elimina_nota`) e sullo stato dell'archivio dopo la conferma
(«sì» → nota sparita, «no» → nota presente); la conferma nella prova è data dal test riprendendo il
grafo. Le risposte finali si stampano (`-s`) e si giudicano a mano. Si rieseguono anche tutte le
prove reali esistenti, per il prompt cambiato.

Docker: test nel container; poi una nota aggiunta da pipe con un `docker compose run --rm -T`, e
in un secondo `run` separato la nota si ritrova (prova del volume); un'eliminazione con conferma
da pipe.

## 10. Documentazione

- README: sezione «Note personali» (dove sta il file, `PERCORSO_DB_NOTE`, i quattro strumenti, come
  funziona la conferma, esempi di richieste), schema del grafo aggiornato con
  `conferma_eliminazione`, volume Docker e avvertenza su `down -v`, voce «Archivio note non
  disponibile» nella diagnosi, voci nuove nella checklist manuale (compresa la conferma in
  sessione interattiva con TTY).
- `CLAUDE.md`: aggiornato solo se cambiano comandi stabili (per esempio la nota sul volume).
- `.env.example`: `PERCORSO_DB_NOTE` commentato con il valore predefinito.
