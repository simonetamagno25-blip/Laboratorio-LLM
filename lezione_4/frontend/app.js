// Interfaccia di chat: parla solo con il back-end, tramite le funzioni generate in api.js.
import {
  creaChat,
  elencaChat,
  eliminaChat,
  inviaMessaggio,
  leggiChat,
  rispondiConferma,
} from "./api.js";
import { dataBreve, descriviStrumento, puoInviare, statoDopoRisposta, testoErrore } from "./logica.js";

// Indirizzo del back-end da config.js (BACKEND_URL); vuoto = stesso indirizzo della pagina.
const opzioni = { base: (window.CONFIG && window.CONFIG.backend) || "" };

const $ = (id) => document.getElementById(id);
const stato = { chatAperta: null, inAttesa: false };

function mostraErrore(errore) {
  $("errore-testo").textContent = testoErrore(errore);
  $("errore").hidden = false;
}

function nascondiErrore() {
  $("errore").hidden = true;
}

function impostaAttesa(inAttesa) {
  stato.inAttesa = inAttesa;
  $("attesa").hidden = !inAttesa;
  $("invia").disabled = inAttesa;
  $("domanda").disabled = inAttesa;
  $("conferma-si").disabled = inAttesa;
  $("conferma-no").disabled = inAttesa;
}

function elementoMessaggio(messaggio) {
  const voce = document.createElement("li");
  voce.className = `messaggio messaggio--${messaggio.ruolo}`;
  voce.textContent = messaggio.testo;
  if (messaggio.strumenti && messaggio.strumenti.length) {
    const strumenti = document.createElement("div");
    strumenti.className = "strumenti";
    strumenti.append("Strumenti usati: ");
    messaggio.strumenti.forEach((s, i) => {
      const codice = document.createElement("code");
      codice.textContent = descriviStrumento(s);
      if (i) strumenti.append("; ");
      strumenti.append(codice);
    });
    voce.append(strumenti);
  }
  return voce;
}

function mostraConferma(domanda) {
  $("conferma-domanda").textContent = domanda || "";
  $("conferma").hidden = !domanda;
  $("modulo").hidden = Boolean(domanda);
}

async function aggiornaElenco() {
  const elenco = await elencaChat(opzioni);
  const lista = $("elenco-chat");
  lista.replaceChildren(
    ...elenco.map((chat) => {
      const voce = document.createElement("li");
      voce.className = "elenco__voce";
      voce.setAttribute("aria-current", String(chat.id === stato.chatAperta));
      const apri = document.createElement("button");
      apri.type = "button";
      apri.className = "elenco__apri";
      const titolo = document.createElement("span");
      titolo.className = "elenco__titolo";
      titolo.textContent = chat.titolo;
      const data = document.createElement("span");
      data.className = "elenco__data";
      data.textContent = dataBreve(chat.ultimo_messaggio) || "nessun messaggio";
      apri.append(titolo, data);
      apri.addEventListener("click", () => esegui(() => apriChat(chat.id)));
      const elimina = document.createElement("button");
      elimina.type = "button";
      elimina.className = "elimina";
      elimina.textContent = "🗑";
      elimina.setAttribute("aria-label", `Elimina la chat «${chat.titolo}»`);
      elimina.addEventListener("click", () => esegui(() => cancellaChat(chat)));
      voce.append(apri, elimina);
      return voce;
    }),
  );
  $("elenco-vuoto").hidden = elenco.length > 0;
}

async function apriChat(id) {
  const chat = await leggiChat(id, opzioni);
  stato.chatAperta = chat.id;
  $("vuoto").hidden = true;
  $("chat").hidden = false;
  $("titolo-chat").textContent = chat.titolo;
  $("messaggi").replaceChildren(...chat.messaggi.map(elementoMessaggio));
  mostraConferma(chat.conferma_in_attesa ? "C'è un'eliminazione da confermare: confermi?" : null);
  $("messaggi").lastElementChild?.scrollIntoView({ block: "end" });
  await aggiornaElenco();
  $("domanda").focus();
}

async function cancellaChat(chat) {
  if (!window.confirm(`Eliminare la chat «${chat.titolo}» e tutti i suoi messaggi?`)) return;
  await eliminaChat(chat.id, opzioni);
  if (stato.chatAperta === chat.id) {
    stato.chatAperta = null;
    $("chat").hidden = true;
    $("vuoto").hidden = false;
  }
  await aggiornaElenco();
}

async function invia() {
  const testo = $("domanda").value;
  if (!puoInviare(testo, stato.inAttesa) || stato.chatAperta === null) return;
  const id = stato.chatAperta;
  // La domanda compare subito; se l'invio fallisce resta nel campo per riprovare.
  const provvisoria = elementoMessaggio({ ruolo: "utente", testo: testo.trim() });
  $("messaggi").append(provvisoria);
  provvisoria.scrollIntoView({ block: "end" });
  impostaAttesa(true);
  try {
    const risposta = await inviaMessaggio(id, { testo }, opzioni);
    $("domanda").value = "";
    await apriChat(id);
    mostraConferma(statoDopoRisposta(risposta).domandaConferma);
  } catch (errore) {
    provvisoria.remove();
    throw errore;
  } finally {
    impostaAttesa(false);
  }
}

async function conferma(si) {
  const id = stato.chatAperta;
  impostaAttesa(true);
  try {
    const risposta = await rispondiConferma(id, { conferma: si }, opzioni);
    await apriChat(id);
    mostraConferma(statoDopoRisposta(risposta).domandaConferma);
  } finally {
    impostaAttesa(false);
  }
}

// Ogni azione mostra l'errore senza bloccare l'interfaccia.
async function esegui(azione) {
  nascondiErrore();
  try {
    await azione();
  } catch (errore) {
    mostraErrore(errore);
  }
}

$("nuova-chat").addEventListener("click", () =>
  esegui(async () => {
    const chat = await creaChat(opzioni);
    await apriChat(chat.id);
  }),
);
$("modulo").addEventListener("submit", (evento) => {
  evento.preventDefault();
  esegui(invia);
});
$("domanda").addEventListener("keydown", (evento) => {
  if (evento.key === "Enter" && !evento.shiftKey) {
    evento.preventDefault();
    esegui(invia);
  }
});
$("conferma-si").addEventListener("click", () => esegui(() => conferma(true)));
$("conferma-no").addEventListener("click", () => esegui(() => conferma(false)));
$("errore-chiudi").addEventListener("click", nascondiErrore);

esegui(aggiornaElenco);
