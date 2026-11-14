// GENERATO da frontend/genera_api.py a partire da frontend/openapi.json: non modificare a mano.
// Ogni funzione corrisponde a un'operazione del back-end (operationId).

export class ErroreApi extends Error {
  constructor(stato, messaggio) {
    super(messaggio);
    this.stato = stato;
  }
}

// Messaggio leggibile dal corpo di errore di FastAPI ({"detail": ...}).
export function messaggioErrore(stato, corpo) {
  const dettaglio = corpo && corpo.detail;
  if (typeof dettaglio === "string") return dettaglio;
  if (Array.isArray(dettaglio) && dettaglio.length) {
    return dettaglio.map((d) => d.msg).join("; ");
  }
  return `Errore ${stato} dal back-end`;
}

async function chiama(base, metodo, percorso, corpo, fetchFn) {
  let risposta;
  try {
    risposta = await fetchFn(base + percorso, {
      method: metodo,
      headers: corpo === undefined ? {} : { "Content-Type": "application/json" },
      body: corpo === undefined ? undefined : JSON.stringify(corpo),
    });
  } catch (errore) {
    throw new ErroreApi(0, `Back-end non raggiungibile su ${base || "questo indirizzo"}.`);
  }
  if (risposta.status === 204) return null;
  let dati = null;
  try {
    dati = await risposta.json();
  } catch (errore) {
    dati = null;
  }
  if (!risposta.ok) throw new ErroreApi(risposta.status, messaggioErrore(risposta.status, dati));
  return dati;
}

// GET /api/chat — Elenca le chat
export function elencaChat({ base = "", fetchFn = fetch } = {}) {
  return chiama(base, "GET", `/api/chat`, undefined, fetchFn);
}

// POST /api/chat — Crea una chat
export function creaChat({ base = "", fetchFn = fetch } = {}) {
  return chiama(base, "POST", `/api/chat`, undefined, fetchFn);
}

// DELETE /api/chat/{id_chat} — Elimina la chat e i suoi messaggi
export function eliminaChat(id_chat, { base = "", fetchFn = fetch } = {}) {
  return chiama(base, "DELETE", `/api/chat/${encodeURIComponent(id_chat)}`, undefined, fetchFn);
}

// GET /api/chat/{id_chat} — Legge una chat
export function leggiChat(id_chat, { base = "", fetchFn = fetch } = {}) {
  return chiama(base, "GET", `/api/chat/${encodeURIComponent(id_chat)}`, undefined, fetchFn);
}

// POST /api/chat/{id_chat}/conferma — Risponde sì o no alla conferma chiesta dall'agente
export function rispondiConferma(id_chat, corpo, { base = "", fetchFn = fetch } = {}) {
  return chiama(base, "POST", `/api/chat/${encodeURIComponent(id_chat)}/conferma`, corpo, fetchFn);
}

// POST /api/chat/{id_chat}/messaggi — Invia un messaggio: chiama l'agente, salva domanda e risposta
export function inviaMessaggio(id_chat, corpo, { base = "", fetchFn = fetch } = {}) {
  return chiama(base, "POST", `/api/chat/${encodeURIComponent(id_chat)}/messaggi`, corpo, fetchFn);
}

// GET /api/stato — Back-end, database e agente
export function statoBackend({ base = "", fetchFn = fetch } = {}) {
  return chiama(base, "GET", `/api/stato`, undefined, fetchFn);
}
