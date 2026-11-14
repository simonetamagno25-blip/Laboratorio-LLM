# Step 4 · Resource: preferenze dell'utente — specifica

Data: 2026-11-14 · Branch: `feat/lezione-6` · Fonte: `LLM_Lez_6.pdf`, step 4.
Parte dagli step 1–3 funzionanti.

## Intento
Il server MCP espone le preferenze dell'utente come resource `utente://preferenze`. L'host
(l'assistente) la legge una volta a inizio sessione e la mette in cima al prompt di sistema:
modificando il file delle preferenze il comportamento cambia senza toccare il codice. Il modello non
decide se leggerla: non è un tool.

## Obiettivi
- Resource `utente://preferenze` (JSON) con lingua delle risposte, fuso orario predefinito e stile
  (`sintetico` o `dettagliato`).
- Lettura da parte dell'host a inizio sessione e inserimento in cima al prompt di sistema.
- La resource non compare tra i tool passati a `bind_tools`.
- Resource non disponibile o non valida: valori predefiniti, segnalati nei log.

## Non obiettivi
- Ricaricare le preferenze durante la sessione (vale la «sessione successiva», come nel PDF).
- Tradurre i testi fissi del programma (rifiuto del router, messaggi di limite, conferma delle note):
  restano in italiano.

## Decisioni (prese da chi implementa, su indicazione dell'utente di procedere senza fermarsi)
| Tema | Decisione | Motivo |
|---|---|---|
| Server | la resource va nel server MCP esistente `convertitore_mcp` (nel PDF si chiama «orologio») | È l'unico server MCP del progetto; un secondo server per una resource sarebbe un processo in più senza beneficio |
| File | `preferenze.json` nella cartella del progetto, versionato con i valori predefiniti; percorso alternativo con `PERCORSO_PREFERENZE` | Non contiene credenziali; i test usano un file temporaneo |
| Variabile al server | il client passa `PERCORSO_PREFERENZE` nell'ambiente del sottoprocesso | Il client stdio di MCP passa al server solo un sottoinsieme sicuro dell'ambiente |
| Lettura | il server legge il file a ogni `resources/read` | Il file può cambiare tra una sessione e l'altra senza riavviare nulla |
| Valori predefiniti | lingua `italiano`, fuso `FUSO_ORARIO_PREDEFINITO`, stile `sintetico` | Comportamento identico a prima quando la resource manca |
| Campo non valido | si scarta solo quel campo (valore predefinito + `WARNING`) | Un errore in un campo non deve far perdere gli altri |
| Precedenza del fuso | il fuso delle preferenze sostituisce `FUSO_ORARIO_PREDEFINITO` | Il PDF chiede che «Che ore sono?» usi il fuso delle preferenze |

## Progetto

### Server (`convertitore_mcp/server.py`)
- `@server.resource("utente://preferenze", name="preferenze", mime_type="application/json")`:
  restituisce il testo del file indicato da `PERCORSO_PREFERENZE` (default `preferenze.json`,
  relativo alla cartella del progetto).

### Client (`assistente/client_mcp.py`)
- `ClientMCP(..., ambiente: dict | None = None)`: variabili aggiunte all'ambiente predefinito del
  sottoprocesso.
- `leggi_risorsa(uri) -> str`: `resources/read` sincrono; log
  `INFO resources/read utente://preferenze: <n> caratteri`; errori → `ErroreMCP`.

### Preferenze (`assistente/preferenze.py`, modulo nuovo)
- `Preferenze(lingua, fuso_orario, stile)` (dataclass immutabile).
- `interpreta(testo, predefinite) -> Preferenze`: JSON → valori, con `WARNING` per ogni campo
  mancante o non valido (fuso non riconosciuto, stile fuori elenco, lingua vuota).
- `carica_preferenze(client, predefinite) -> Preferenze`: legge la resource; se non disponibile
  `WARNING preferenze: resource utente://preferenze non disponibile (...), uso i valori predefiniti`.
  Log finale `INFO preferenze: lingua=<l> fuso_orario=<f> stile=<s>`.
- `blocco_preferenze(p) -> str`: il blocco da mettere in cima al prompt di sistema.

### Grafo
- `costruisci_grafo(..., preferenze: Preferenze | None = None)`: se presenti, il prompt di sistema
  dell'agente inizia con il blocco delle preferenze; il fuso predefinito e la lingua del prompt
  vengono dalle preferenze («Rispondi sempre in <lingua>»).

### Avvio
- Dopo l'avvio del server MCP: `carica_preferenze` e passaggio al grafo. Gli strumenti restano quelli
  di `list_tools`: la resource non è uno strumento.

### Configurazione
- `PERCORSO_PREFERENZE` (facoltativa) è letta dall'host e passata al server.

## Evidenze

### Test automatici (senza LM Studio)
- Server reale via stdio: `resources/list` contiene `utente://preferenze`; la lettura restituisce il
  file indicato da `PERCORSO_PREFERENZE`; gli strumenti restano solo `converti_unita`.
- `interpreta`: valori validi, campi mancanti o non validi → predefiniti con `WARNING`, JSON rotto.
- `carica_preferenze` con resource non disponibile → predefinite e `WARNING`.
- Grafo: il blocco delle preferenze è in cima al prompt di sistema; il fuso delle preferenze è nel
  prompt; nessun tool con il nome della resource.
- Avvio: le preferenze lette arrivano al grafo; lettura nei log prima della prima domanda.

### Prove reali con LM Studio
- Preferenze con `America/New_York`: «Che ore sono?» chiama `ora_corrente` con `America/New_York`.
- Preferenze con lingua inglese e stile dettagliato: la risposta è in inglese.
