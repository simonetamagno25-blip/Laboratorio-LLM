"""Interfaccia da terminale: sessione con cronologia in memoria e ciclo di lettura."""

import sys
from dataclasses import dataclass

from langchain_core.messages import BaseMessage, HumanMessage

from assistente.agente import Agente, RichiestaConferma, Risposta
from assistente.client_mcp import ErroreMCP
from assistente.comandi import (
    ErroreComando,
    descrivi_prompt,
    in_messaggi,
    interpreta_comando_prompt,
    valida,
)
from assistente.modello import descrivi_errore


@dataclass(frozen=True)
class Conferma:
    """Il grafo si è fermato e aspetta un sì/no dell'utente."""

    domanda: str


def e_un_si(risposta: str) -> bool:
    return risposta.strip().casefold() in {"sì", "si", "s"}


ATTESA ="(attendi: il modello sta rispondendo...)"


def scarta_input_anticipato(ingresso=None) -> None:
    """Scarta il testo scritto nel terminale prima che compaia la domanda di conferma.

    Così la conferma vale solo per quello che si scrive dopo averla letta. Con l'input da pipe
    non fa nulla: lì le risposte sono scritte apposta in anticipo.
    """
    ingresso = sys.stdin if ingresso is None else ingresso
    try:
        if not ingresso.isatty():
            return
        descrittore = ingresso.fileno()
    except (AttributeError, ValueError, OSError):
        return
    if sys.platform == "win32":
        import ctypes
        import msvcrt

        ctypes.windll.kernel32.FlushConsoleInputBuffer(msvcrt.get_osfhandle(descrittore))
    else:
        import termios

        try:
            termios.tcflush(descrittore, termios.TCIFLUSH)
        except termios.error:
            pass


class Sessione:
    """Sessione locale: tiene cronologia e riassunto e usa l'Agente nello stesso processo.

    Ha la stessa interfaccia di SessioneRemota (client dell'API dell'agente).
    """

    def __init__(self, grafo, recursion_limit: int):
        self._agente = Agente(grafo, recursion_limit)
        self._id_conferma: str | None = None
        self.cronologia: list[BaseMessage] = []
        # Riassunto dei turni tolti dalla cronologia (step 3): ripassato a ogni domanda.
        self.riassunto = ""

    def chiedi(self, testo: str) -> str | Conferma:
        return self.chiedi_messaggi([HumanMessage(testo)])

    def chiedi_messaggi(self, messaggi: list[BaseMessage]) -> str | Conferma:
        """Come chiedi, con i messaggi già pronti (per esempio quelli di un prompt MCP)."""
        # La cronologia si aggiorna solo se il turno finisce bene.
        return self._esito(self._agente.turno(messaggi, self.cronologia, self.riassunto))

    def conferma(self, si: bool) -> str | Conferma:
        return self._esito(self._agente.conferma(self._id_conferma, si))

    def _esito(self, esito: Risposta | RichiestaConferma) -> str | Conferma:
        if isinstance(esito, RichiestaConferma):
            self._id_conferma = esito.id_conferma
            return Conferma(esito.domanda)
        self.cronologia = esito.cronologia
        self.riassunto = esito.riassunto
        return esito.testo or "(risposta vuota)"


def _comando_prompt(riga: str, prompt) -> list[BaseMessage]:
    """/prompt nome chiave=valore: controllo su prompts/list, poi prompts/get. Gli errori
    (ErroreComando, ErroreMCP) arrivano prima di qualsiasi chiamata al modello."""
    nome, argomenti = interpreta_comando_prompt(riga)
    valida(nome, argomenti, prompt.elenca_prompt())
    return in_messaggi(prompt.ottieni_prompt(nome, argomenti))


def esegui_ciclo(
    sessione: Sessione,
    base_url: str,
    leggi=input,
    scrivi=print,
    scarta_anticipato=scarta_input_anticipato,
    prompt=None,
) -> None:
    """Ciclo del terminale. `prompt` è il client MCP per /prompts e /prompt (facoltativo)."""
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
        if riga == "/prompts" or riga == "/prompt" or riga.startswith("/prompt "):
            if prompt is None:
                scrivi("Prompt MCP non disponibili in questa sessione.")
                continue
            try:
                if riga == "/prompts":
                    scrivi(descrivi_prompt(prompt.elenca_prompt()))
                    continue
                messaggi = _comando_prompt(riga, prompt)
            except ErroreComando as errore:
                scrivi(str(errore))
                continue
            except ErroreMCP as errore:
                scrivi(f"Prompt non disponibile: {errore}. Controlla nome e argomenti con /prompts.")
                continue
            except KeyboardInterrupt:
                scrivi("Arrivederci.")
                return
        else:
            messaggi = [HumanMessage(riga)]
        try:
            scrivi(ATTESA)
            esito = sessione.chiedi_messaggi(messaggi)
            while isinstance(esito, Conferma):
                scrivi(esito.domanda)
                try:
                    scarta_anticipato()
                    risposta = leggi("Conferma> ")
                except (EOFError, KeyboardInterrupt):
                    scrivi("Arrivederci.")
                    return
                scrivi(ATTESA)
                esito = sessione.conferma(e_un_si(risposta))
            scrivi("Assistente> " + esito)
        except KeyboardInterrupt:
            scrivi("Arrivederci.")
            return
        except Exception as errore:
            scrivi(descrivi_errore(errore, base_url))
