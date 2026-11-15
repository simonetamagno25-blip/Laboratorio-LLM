# Step 4 · Resource preferenze — piano di implementazione

**Obiettivo:** resource MCP `utente://preferenze` letta dall'host a inizio sessione e messa in cima
al prompt di sistema, con valori predefiniti se non disponibile.

**Specifica:** `docs/superpowers/specs/2026-11-14-preferenze-design.md` · **Stack:** invariato.

## Vincoli globali
- Solo dentro `lezione_4/`, branch `feat/agente-web`, TDD, un commit per incremento.
- Nomi esatti: URI `utente://preferenze`, campi `lingua`, `fuso_orario`, `stile`
  (`sintetico`|`dettagliato`), variabile `PERCORSO_PREFERENZE`, file `preferenze.json`.

### Task 1: resource nel server MCP
- [ ] Test (server reale via stdio): resource elencata, contenuto dal file di `PERCORSO_PREFERENZE`,
      strumenti invariati.
- [ ] `preferenze.json` predefinito; `ClientMCP(ambiente=...)`, `leggi_risorsa`.
- [ ] Commit `feat(mcp): resource utente://preferenze nel server e lettura dal client`.

### Task 2: modulo `assistente/preferenze.py`
- [ ] Test: `interpreta`, `carica_preferenze` (non disponibile), `blocco_preferenze`.
- [ ] Commit `feat(preferenze): interpretazione e valori predefiniti`.

### Task 3: grafo e avvio
- [ ] Test: blocco in cima al prompt, fuso e lingua dalle preferenze; avvio che legge la resource e
      la passa al grafo; nessun tool `preferenze`.
- [ ] Commit `feat(grafo): preferenze dell'utente in cima al prompt di sistema`.

### Task 4: prove reali e documentazione
- [ ] Prove reali (fuso America/New_York, lingua inglese); prova manuale con i log.
- [ ] README, ROADMAP, `.env.example`; commit `test(preferenze): ...` e `docs: ...`.
