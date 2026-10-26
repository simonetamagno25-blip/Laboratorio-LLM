"""Modello finto condiviso dai test: risposte decise dal test, nessuna rete."""

from langchain_core.messages import AIMessage, BaseMessage


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
