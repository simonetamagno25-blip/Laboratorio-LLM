# Step 8 · Front-end: interfaccia di chat — specifica

Data: 2026-11-14 · Branch: `feat/lezione-6` · Fonte: `LLM_Lez_6.pdf`, step 8.
Parte dallo step 7 (back-end) funzionante.

## Intento
Un'interfaccia di chat utilizzabile da chi non conosce il progetto, che comunica solo con il
back-end. Le chiamate sono generate dal documento OpenAPI del back-end, usato come contratto.

## Obiettivi
- Elenco delle chat, creazione di una nuova chat ed eliminazione (con conferma del browser).
- Vista dei messaggi della chat (con gli strumenti usati) e invio di una nuova domanda.
- Stato di attesa durante la risposta ed errori mostrati in modo comprensibile, senza bloccare.
- Indirizzo del back-end da configurazione (`BACKEND_URL` → `config.js`), non scritto nel codice.
- Conferma delle eliminazioni delle note con i pulsanti Sì/No.

## Decisioni (prese da chi implementa, su indicazione dell'utente di procedere senza fermarsi)
| Tema | Decisione | Motivo |
|---|---|---|
| Tecnologia | HTML, CSS e JavaScript (moduli ES) senza framework né build | Nessuna dipendenza nuova; i file si servono così come sono, in locale e con nginx |
| Contratto | `frontend/openapi.json` esportato dal back-end; `frontend/api.js` generato da `python -m frontend.genera_api` (una funzione per `operationId`); un test verifica che siano allineati | Il PDF chiede di generare le chiamate dal documento OpenAPI, senza indovinare gli endpoint |
| Locale | `python -m frontend` (porta `FRONTEND_PORTA`, default `8300`) serve i file e genera `config.js` da `BACKEND_URL` (default `http://localhost:8200`); il back-end consente l'origine con CORS | Nessun server aggiuntivo da installare |
| Docker (step 9) | nginx serve gli stessi file e inoltra `/api` al back-end; `BACKEND_URL` vuoto = stesso indirizzo della pagina | Il browser parla con un solo indirizzo; l'agente non è esposto |
| Test | Node (`node --test`, già installato) per le chiamate generate e la logica; pytest per contratto e server statico | Ripetibili senza browser; la prova nel browser resta una prova reale |
| Attesa | domanda mostrata subito, campo e pulsanti disabilitati, testo «L'assistente sta rispondendo…» | Con un modello locale la risposta può richiedere minuti |
| Errori | avviso in cima con il `detail` del back-end (es. «Agente non raggiungibile …: la domanda non è stata salvata»), chiudibile; la domanda resta nel campo | L'utente capisce cosa è successo e può riprovare |

## Evidenze
- Test: `node --test frontend/test/front.test.mjs` (chiamate generate, errori, logica) e
  `tests/test_frontend.py` (contratto allineato, server statico, `config.js`).
- Prova reale nel browser: conversazione completa con uno strumento; chat ancora presente dopo il
  riavvio del back-end; con l'agente spento l'interfaccia mostra l'errore senza bloccarsi.
