# Handoff — strumenti con tool, MCP e API

Data: 2026-11-02 · Branch: `feat/strumenti-mcp` (da `dev`, già su GitHub) · `main` non toccato.

## Stato
- Implementati e verificati i tre strumenti: calcolatrice (tool locale), convertitore di unità
  (server MCP via stdio), giorni e scadenze (API HTTP). Dettagli in
  `specs/2026-11-02-strumenti-mcp-design.md`, `plans/2026-11-02-strumenti-tool-mcp-api.md` e README.
- Test automatici: 186 passati, 5 saltati (prove LM Studio).
- LM Studio (`google/gemma-4-e2b`): 5/5 prove reali superate.
- Docker Compose: build, domande da pipe e test nel container verificati.
- Revisione finale del branch fatta; corretti 4 problemi con test.

## Da fare
1. Aprire la Pull Request `feat/strumenti-mcp` → `dev`:
   https://github.com/simonetamagno25-blip/Laboratorio-LLM/compare/dev...feat/strumenti-mcp?expand=1
2. Prove manuali in una finestra di PowerShell normale (comandi nel README):
   - Ctrl+C durante una risposta e subito dopo l'avvio, in locale e in Docker con TTY;
   - servizio `scadenze_api` spento durante la sessione → errore spiegato, assistente aperto;
   - nessun processo `convertitore_mcp` rimasto dopo l'uscita.
3. Se le prove manuali vanno bene, aggiungerle alla «Checklist manuale» del README.

## Rilievi minori non corretti
- Timeout di avvio MCP: il sottoprocesso non viene atteso; su Linux fuori da Docker potrebbe restare
  acceso (su Windows lo chiude il sistema). `assistente/client_mcp.py`, metodo `chiudi`.
- `HEAD` e `OPTIONS` sull'API rispondono 501 in HTML invece che in JSON (`scadenze_api/servizio.py`).
- Il server MCP non eredita tutte le variabili d'ambiente dell'assistente (lista ristretta di `mcp`).
- La calcolatrice arrotonda i numeri piccolissimi a 0 (`1e-400 = 0`).

## Osservazioni sul modello
- A volte omette l'avvertenza «non ha valore normativo» nella risposta finale, anche se lo strumento
  la restituisce sempre.
- Davanti a `__import__("os")` rifiuta da solo senza chiamare la calcolatrice.

## Note
- `SCADENZE_API_URL` è ora obbligatoria: va aggiunta a ogni `.env` (vedi `.env.example`).
- Flusso Git concordato: dopo ogni commit si avvisa e si fa il push solo su conferma.
