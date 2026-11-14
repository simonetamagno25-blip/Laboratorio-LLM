# Step 3 · Riassunto della cronologia — piano di implementazione

**Obiettivo:** nodo `riassunto` all'inizio del turno che, sopra una soglia di messaggi, sostituisce i
turni vecchi con un riassunto aggiornato nello stato, senza separare strumenti e risultati.

**Specifica:** `docs/superpowers/specs/2026-11-14-riassunto-design.md` · **Stack:** invariato.

## Vincoli globali
- Solo dentro `lezione_4/`, branch `feat/lezione-6`, TDD, un commit per incremento.
- Nomi esatti: nodo `riassunto`, campo `riassunto`, variabili `SOGLIA_RIASSUNTO`, `MESSAGGI_CONSERVATI`.
- Righe di log esatte: vedi la specifica.

### Task 1: configurazione
- [ ] Test: default 20/6, valori letti, non interi o < 1 → errore, conservati ≥ soglia → errore.
- [ ] Campi con default nel dataclass, righe in `.env.example`; ambito di esempio con «presentazioni e
      domande sulla conversazione in corso».
- [ ] Commit `feat(config): soglia del riassunto e messaggi conservati`.

### Task 2: modulo `assistente/riassunto.py`
- [ ] Test: `punto_di_taglio` (sotto N, turni con strumenti, turno unico lungo → 0, indicazioni del
      revisore), `testo_da_riassumere` (riassunto precedente, righe, esclusioni), prompt.
- [ ] Commit `feat(riassunto): punto di taglio, prompt e testo da riassumere`.

### Task 3: nodo nel grafo
- [ ] Test con `RiassuntoreFinto`: sotto soglia nessuna chiamata, sopra soglia compressione e log,
      riassunto nel prompt dell'agente, riassunto aggiornato e non accumulato, nessuna tool call
      separata, errore → cronologia invariata, conferma delle note non riesegue il riassunto.
- [ ] Commit `feat(grafo): nodo riassunto all'inizio del turno`.

### Task 4: CLI e avvio
- [ ] Test: `Sessione` conserva e ripassa il riassunto; l'avvio ha il nodo `riassunto`.
- [ ] `crea_riassuntore(config)` in `modello.py`.
- [ ] Commit `feat(cli): riassunto della cronologia attivo all'avvio`.

### Task 5: prove reali e documentazione
- [ ] Prova reale `test_riassunto_conserva_il_nome` con soglia bassa; prova manuale con i log.
- [ ] README, ROADMAP; commit `test(riassunto): ...` e `docs: ...`.
