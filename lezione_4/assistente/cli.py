"""Interfaccia da terminale: sessione con cronologia in memoria e ciclo di lettura."""

from langchain_core.messages import BaseMessage, HumanMessage

from assistente.modello import descrivi_errore


class Sessione:
    def __init__(self, grafo, recursion_limit: int):
        self._grafo = grafo
        self._recursion_limit = recursion_limit
        self.cronologia: list[BaseMessage] = []

    def chiedi(self, testo: str) -> str:
        esito = self._grafo.invoke(
            {
                "messages": self.cronologia + [HumanMessage(testo)],
                "passaggi_strumenti": 0,
            },
            {"recursion_limit": self._recursion_limit},
        )
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
            scrivi("Assistente> " + sessione.chiedi(riga))
        except KeyboardInterrupt:
            scrivi("Arrivederci.")
            return
        except Exception as errore:
            scrivi(descrivi_errore(errore, base_url))
