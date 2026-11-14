"""Client HTTP dell'agente: la CLI usa l'API invece del grafo nello stesso processo.

SessioneRemota ha la stessa interfaccia di cli.Sessione; PromptRemoti quella del client MCP per i
comandi /prompts e /prompt.
"""

import logging

import httpx
from langchain_core.messages import BaseMessage, HumanMessage, messages_from_dict, messages_to_dict

from assistente.client_mcp import ArgomentoPrompt, ErroreMCP, InfoPrompt

log = logging.getLogger(__name__)

# Un turno può richiedere diverse chiamate al modello locale (router, agente, revisore, strumenti).
TIMEOUT_TURNO = 600.0


class ErroreAgente(RuntimeError):
    """L'agente non risponde o ha restituito un errore (messaggio già comprensibile)."""


def _client(url: str, http: httpx.Client | None) -> httpx.Client:
    return http if http is not None else httpx.Client(base_url=url, timeout=TIMEOUT_TURNO)


def _chiama(http: httpx.Client, url: str, metodo: str, percorso: str, **kwargs) -> dict | list:
    try:
        risposta = http.request(metodo, percorso, **kwargs)
    except httpx.TransportError as errore:
        log.warning("agente non raggiungibile: %r", errore)
        raise ErroreAgente(
            f"Agente non raggiungibile su {url}. È avviato con python -m assistente.servizio?"
        ) from errore
    if risposta.is_error:
        try:
            dettaglio = risposta.json().get("detail")
        except ValueError:
            dettaglio = None
        raise ErroreAgente(str(dettaglio or f"errore {risposta.status_code} dall'agente"))
    return risposta.json()


class SessioneRemota:
    def __init__(self, url: str, http: httpx.Client | None = None):
        self._url = url
        self._http = _client(url, http)
        self._id_conferma: str | None = None
        self.cronologia: list[BaseMessage] = []
        self.riassunto = ""

    def stato(self) -> dict:
        """GET /stato: il corpo arriva anche con 503 (qualcosa non è raggiungibile)."""
        try:
            return self._http.get("/stato").json()
        except httpx.TransportError as errore:
            raise ErroreAgente(f"Agente non raggiungibile su {self._url}") from errore

    def chiedi(self, testo: str):
        return self.chiedi_messaggi([HumanMessage(testo)])

    def chiedi_messaggi(self, messaggi: list[BaseMessage]):
        corpo = {
            "messaggi": messages_to_dict(messaggi),
            "cronologia": messages_to_dict(self.cronologia),
            "riassunto": self.riassunto,
        }
        return self._esito(_chiama(self._http, self._url, "POST", "/conversazione", json=corpo))

    def conferma(self, si: bool):
        corpo = {"id_conferma": self._id_conferma, "conferma": si}
        return self._esito(_chiama(self._http, self._url, "POST", "/conferma", json=corpo))

    def _esito(self, corpo: dict):
        from assistente.cli import Conferma

        if corpo["tipo"] == "conferma":
            self._id_conferma = corpo["id_conferma"]
            return Conferma(corpo["domanda"])
        # La cronologia si aggiorna solo se il turno finisce bene, come nella sessione locale.
        self.cronologia = messages_from_dict(corpo["cronologia"])
        self.riassunto = corpo["riassunto"]
        return corpo["risposta"] or "(risposta vuota)"


class PromptRemoti:
    """prompts/list e prompts/get passando dall'agente, che ha il client MCP."""

    def __init__(self, url: str, http: httpx.Client | None = None):
        self._url = url
        self._http = _client(url, http)

    def _chiama(self, metodo: str, percorso: str, **kwargs):
        try:
            return _chiama(self._http, self._url, metodo, percorso, **kwargs)
        except ErroreAgente as errore:
            raise ErroreMCP(str(errore)) from errore

    def elenca_prompt(self) -> list[InfoPrompt]:
        return [
            InfoPrompt(
                p["nome"],
                p["descrizione"],
                tuple(
                    ArgomentoPrompt(a["nome"], a["descrizione"], a["obbligatorio"])
                    for a in p["argomenti"]
                ),
            )
            for p in self._chiama("GET", "/prompts")
        ]

    def ottieni_prompt(self, nome: str, argomenti: dict[str, str]) -> list[tuple[str, str]]:
        corpo = self._chiama("POST", f"/prompts/{nome}", json={"argomenti": argomenti})
        return [(m["ruolo"], m["testo"]) for m in corpo["messaggi"]]
