// Funzioni pure dell'interfaccia (senza DOM): testate con `node --test frontend/`.

const FORMATO_DATA = new Intl.DateTimeFormat("it-IT", {
  day: "2-digit",
  month: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
});

// "26/10, 17:05" oppure "" se la chat non ha ancora messaggi.
export function dataBreve(iso) {
  if (!iso) return "";
  const data = new Date(iso);
  return Number.isNaN(data.getTime()) ? "" : FORMATO_DATA.format(data);
}

// Riga leggibile per uno strumento usato: "ora_corrente(fuso_orario=Asia/Tokyo) → 01:05".
export function descriviStrumento(strumento) {
  const argomenti = Object.entries(strumento.argomenti || {})
    .map(([chiave, valore]) => `${chiave}=${typeof valore === "string" ? valore : JSON.stringify(valore)}`)
    .join(", ");
  const risultato = (strumento.risultato || "").trim();
  const breve = risultato.length > 80 ? `${risultato.slice(0, 79)}…` : risultato;
  return `${strumento.nome}(${argomenti})${breve ? ` → ${breve}` : ""}`;
}

// Testo da mostrare per un errore di rete o del back-end.
export function testoErrore(errore) {
  if (errore && typeof errore.message === "string" && errore.message) return errore.message;
  return "Errore imprevisto: riprova.";
}

// Il testo può essere inviato? (non vuoto e nessuna richiesta in corso)
export function puoInviare(testo, inAttesa) {
  return !inAttesa && typeof testo === "string" && testo.trim().length > 0;
}

// Dopo una risposta "conferma" il front-end mostra la domanda e i pulsanti Sì/No.
export function statoDopoRisposta(risposta) {
  if (risposta.tipo === "conferma") {
    return { confermaInAttesa: true, domandaConferma: risposta.domanda };
  }
  return { confermaInAttesa: false, domandaConferma: null };
}
