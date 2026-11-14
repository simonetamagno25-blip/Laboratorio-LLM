"""Modello finto condiviso dai test: risposte decise dal test, nessuna rete."""

import httpx
from langchain_core.messages import AIMessage, BaseMessage
from langchain_openai import ChatOpenAI

from assistente.router import DecisioneRouter


class ModelloFinto:
    def __init__(self, risposte: list[AIMessage | Exception]):
        self._risposte = list(risposte)
        self.chiamate: list[list[BaseMessage]] = []

    def invoke(self, messaggi, config=None) -> AIMessage:
        self.chiamate.append(list(messaggi))
        risposta = self._risposte.pop(0)
        if isinstance(risposta, Exception):
            raise risposta
        return risposta


def chiamata_strumento(
    fuso: str | None,
    id: str = "call_1",
    nome: str = "ora_corrente",
    args: dict | None = None,
) -> AIMessage:
    if args is None:
        args = {} if fuso is None else {"fuso_orario": fuso}
    return AIMessage(
        content="",
        tool_calls=[{"name": nome, "args": args, "id": id, "type": "tool_call"}],
    )


class RouterFinto:
    """Router simulato: restituisce lo stesso formato di with_structured_output(include_raw=True).

    Ogni decisione è un DecisioneRouter (output valido), None (output non valido) o
    un'eccezione da sollevare.
    """

    def __init__(self, decisioni: list[DecisioneRouter | None | Exception]):
        self._decisioni = list(decisioni)
        self.chiamate: list[list[BaseMessage]] = []

    def invoke(self, messaggi, config=None) -> dict:
        self.chiamate.append(list(messaggi))
        decisione = self._decisioni.pop(0)
        if isinstance(decisione, Exception):
            raise decisione
        if decisione is None:
            errore = ValueError("json non valido")
            return {"raw": AIMessage(""), "parsed": None, "parsing_error": errore}
        return {"raw": AIMessage(""), "parsed": decisione, "parsing_error": None}


class RevisoreFinto(RouterFinto):
    """Revisore simulato: ogni decisione è un DecisioneRevisore, None (output non valido) o
    un'eccezione."""


def risposta_del_server(contenuto: str, finish_reason: str = "stop"):
    """Gestore per httpx.MockTransport: una risposta di chat completion con questo contenuto."""

    def gestore(request):
        corpo = {
            "id": "x", "object": "chat.completion", "created": 0, "model": "m",
            "choices": [{
                "index": 0, "finish_reason": finish_reason,
                "message": {"role": "assistant", "content": contenuto},
            }],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        }
        return httpx.Response(200, json=corpo)

    return gestore


def chat_con_server_finto(gestore) -> ChatOpenAI:
    """Un vero ChatOpenAI che parla con un server finto: nessuna rete, nessun modello."""
    return ChatOpenAI(
        base_url="http://server-finto/v1", model="m", api_key="k", max_retries=0,
        http_client=httpx.Client(transport=httpx.MockTransport(gestore)),
    )
