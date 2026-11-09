"""Interfaccia da terminale: sessione con cronologia in memoria e ciclo di lettura."""

from dataclasses import dataclass
from uuid import uuid4

from langchain_core.messages import BaseMessage, HumanMessage
from langgraph.types import Command

from assistente.modello import descrivi_errore


@dataclass(frozen=True)
class Conferma:
    """Il grafo si è fermato e aspetta un sì/no dell'utente."""

    domanda: str


def domanda_conferma(dati: dict) -> str:
    return f'Eliminare la nota {dati["numero"]} ({dati["creata"]}): "{dati["testo"]}"? [sì/no]'


def e_un_si(risposta: str) -> bool:
    return risposta.strip().casefold() in {"sì", "si", "s"}


class Sessione:
    def __init__(self, grafo, recursion_limit: int):
        self._grafo = grafo
        self._recursion_limit = recursion_limit
        self._config: dict | None = None
        self.cronologia: list[BaseMessage] = []

    def chiedi(self, testo: str) -> str | Conferma:
        # Un thread nuovo per ogni domanda: il checkpointer serve solo alla pausa dentro il
        # turno, la cronologia resta in questa lista e si aggiorna solo se il turno finisce bene.
        self._config = {
            "recursion_limit": self._recursion_limit,
            "configurable": {"thread_id": uuid4().hex},
        }
        return self._esito(
            self._grafo.invoke(
                {
                    "messages": self.cronologia + [HumanMessage(testo)],
                    "passaggi_strumenti": 0,
                    "eliminazioni_confermate": [],
                },
                self._config,
            )
        )

    def conferma(self, si: bool) -> str | Conferma:
        return self._esito(self._grafo.invoke(Command(resume=si), self._config))

    def _esito(self, esito: dict) -> str | Conferma:
        if esito.get("__interrupt__"):
            return Conferma(domanda_conferma(esito["__interrupt__"][0].value))
        self.cronologia = list(esito["messages"])
        return self.cronologia[-1].content or "(risposta vuota)"


def esegui_ciclo(sessione: Sessione, base_url: str, leggi=input, scrivi=print) -> None:
    while True:
        try:
            riga = leggi("Tu> ").strip()
        except (EOFError, KeyboardInterrupt):
            scrivi("Arrivederci.")
            return
        if not riga:
            continue
        if riga == "/esci":
            scrivi("Arrivederci.")
            return
        try:
            esito = sessione.chiedi(riga)
            while isinstance(esito, Conferma):
                scrivi(esito.domanda)
                try:
                    risposta = leggi("Conferma> ")
                except (EOFError, KeyboardInterrupt):
                    scrivi("Arrivederci.")
                    return
                esito = sessione.conferma(e_un_si(risposta))
            scrivi("Assistente> " + esito)
        except KeyboardInterrupt:
            scrivi("Arrivederci.")
            return
        except Exception as errore:
            scrivi(descrivi_errore(errore, base_url))
