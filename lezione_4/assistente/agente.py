"""Agente: un turno della conversazione sopra il grafo, senza stato tra un turno e l'altro.

Cronologia e riassunto arrivano dal chiamante (CLI o API HTTP) e tornano aggiornati. L'unica
eccezione è la conferma di un'eliminazione: il turno fermo con interrupt() resta qui finché il
chiamante non risponde.
"""

import threading
from dataclasses import dataclass, field
from uuid import uuid4

from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
from langgraph.types import Command


class ConfermaSconosciuta(KeyError):
    """Nessun turno in attesa con questo identificativo (mai esistito o già concluso)."""


@dataclass(frozen=True)
class StrumentoUsato:
    nome: str
    argomenti: dict
    risultato: str


@dataclass(frozen=True)
class Risposta:
    testo: str
    strumenti: list[StrumentoUsato]
    cronologia: list[BaseMessage]
    riassunto: str


@dataclass(frozen=True)
class RichiestaConferma:
    domanda: str
    id_conferma: str
    dati: dict = field(default_factory=dict)


def domanda_conferma(dati: dict) -> str:
    return f'Eliminare la nota {dati["numero"]} ({dati["creata"]}): "{dati["testo"]}"? [sì/no]'


def _id_chiamate(messaggi: list[BaseMessage]) -> set[str]:
    return {c["id"] for m in messaggi if isinstance(m, AIMessage) for c in m.tool_calls}


@dataclass
class _InSospeso:
    config: dict
    gia_presenti: set[str]
    riassunto: str


class Agente:
    def __init__(self, grafo, recursion_limit: int):
        self._grafo = grafo
        self._recursion_limit = recursion_limit
        self._in_sospeso: dict[str, _InSospeso] = {}
        self._lucchetto = threading.Lock()

    def turno(
        self, nuovi: list[BaseMessage], cronologia: list[BaseMessage], riassunto: str = ""
    ) -> Risposta | RichiestaConferma:
        # Un thread nuovo per ogni turno: il checkpointer serve solo alla pausa della conferma.
        id_turno = uuid4().hex
        sospeso = _InSospeso(
            config={
                "recursion_limit": self._recursion_limit,
                "configurable": {"thread_id": id_turno},
            },
            gia_presenti=_id_chiamate(cronologia),
            riassunto=riassunto,
        )
        esito = self._grafo.invoke(
            {
                "messages": list(cronologia) + list(nuovi),
                "passaggi_strumenti": 0,
                "revisioni": 0,
                "riassunto": riassunto,
                "eliminazioni_confermate": [],
            },
            sospeso.config,
        )
        return self._esito(esito, id_turno, sospeso)

    def conferma(self, id_conferma: str, si: bool) -> Risposta | RichiestaConferma:
        with self._lucchetto:
            sospeso = self._in_sospeso.pop(id_conferma, None)
        if sospeso is None:
            raise ConfermaSconosciuta(id_conferma)
        esito = self._grafo.invoke(Command(resume=si), sospeso.config)
        return self._esito(esito, id_conferma, sospeso)

    def _esito(self, esito: dict, id_turno: str, sospeso: _InSospeso):
        if esito.get("__interrupt__"):
            with self._lucchetto:
                self._in_sospeso[id_turno] = sospeso
            dati = esito["__interrupt__"][0].value
            return RichiestaConferma(domanda_conferma(dati), id_turno, dati)
        # Turno concluso: il suo checkpoint non serve più (altrimenti la memoria cresce a ogni turno).
        checkpointer = getattr(self._grafo, "checkpointer", None)
        if checkpointer is not None:
            checkpointer.delete_thread(id_turno)
        messaggi = list(esito["messages"])
        risultati = {m.tool_call_id: m.text for m in messaggi if isinstance(m, ToolMessage)}
        strumenti = [
            StrumentoUsato(c["name"], c["args"], risultati.get(c["id"], ""))
            for m in messaggi
            if isinstance(m, AIMessage)
            for c in m.tool_calls
            if c["id"] not in sospeso.gia_presenti
        ]
        return Risposta(
            testo=messaggi[-1].text if messaggi else "",
            strumenti=strumenti,
            cronologia=messaggi,
            riassunto=esito.get("riassunto", sospeso.riassunto) or "",
        )
