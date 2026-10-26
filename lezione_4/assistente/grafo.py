"""Grafo LangGraph: stato, nodi e instradamento della conversazione."""

import logging
from typing import Annotated, Literal, TypedDict

from langchain_core.messages import (
    AIMessage,
    AnyMessage,
    RemoveMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.graph.state import CompiledStateGraph

log = logging.getLogger(__name__)

MESSAGGIO_LIMITE = (
    "Ho raggiunto il limite di passaggi con gli strumenti "
    "e non posso completare la risposta a questa domanda."
)


class StatoConversazione(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    passaggi_strumenti: int


def prompt_di_sistema(fuso_predefinito: str) -> str:
    return (
        "Sei l'assistente del laboratorio. "
        "Per qualsiasi domanda su data e ora usa sempre lo strumento ora_corrente "
        "e non inventare mai l'ora. "
        f"Se l'utente non indica un luogo, usa il fuso orario {fuso_predefinito}. "
        "Rispondi sempre in italiano."
    )


def instrada_dopo_modello(
    stato: StatoConversazione, max_passaggi: int
) -> Literal["strumenti", "limite_raggiunto", "__end__"]:
    ultimo = stato["messages"][-1]
    if not (ultimo.tool_calls or ultimo.invalid_tool_calls):
        return "__end__"
    if stato["passaggi_strumenti"] >= max_passaggi:
        return "limite_raggiunto"
    return "strumenti"


def limite_ricorsione(max_passaggi: int) -> int:
    return 2 * max_passaggi + 4


def costruisci_grafo(
    modello: Runnable,
    strumenti: list[BaseTool],
    fuso_predefinito: str,
    max_passaggi: int,
) -> CompiledStateGraph:
    per_nome = {s.name: s for s in strumenti}

    def nodo_modello(stato: StatoConversazione) -> dict:
        messaggi = [SystemMessage(prompt_di_sistema(fuso_predefinito))] + stato["messages"]
        return {"messages": [modello.invoke(messaggi)]}

    def nodo_strumenti(stato: StatoConversazione) -> dict:
        risultati = []
        # Chiamate con argomenti non JSON: vanno comunque risposte, altrimenti
        # restano senza ToolMessage nella cronologia.
        for non_valida in stato["messages"][-1].invalid_tool_calls:
            log.warning(
                "chiamata strumento %s con argomenti non validi: %s",
                non_valida["name"],
                non_valida["args"],
            )
            risultati.append(
                ToolMessage(
                    content=f"Errore: argomenti non validi: {non_valida['args']}",
                    tool_call_id=non_valida["id"],
                    name=non_valida["name"],
                )
            )
        for chiamata in stato["messages"][-1].tool_calls:
            nome, args = chiamata["name"], chiamata["args"]
            log.info("chiamata strumento %s con argomenti %s", nome, args)
            strumento = per_nome.get(nome)
            if strumento is None:
                esito = f"Errore: strumento sconosciuto '{nome}'"
            else:
                try:
                    esito = str(strumento.invoke(args))
                except Exception as errore:
                    esito = f"Errore: {errore}"
            log.info("risultato strumento %s: %s", nome, esito)
            risultati.append(ToolMessage(content=esito, tool_call_id=chiamata["id"], name=nome))
        return {"messages": risultati, "passaggi_strumenti": stato["passaggi_strumenti"] + 1}

    def nodo_limite_raggiunto(stato: StatoConversazione) -> dict:
        log.warning("limite di %d passaggi con gli strumenti raggiunto", max_passaggi)
        # Si toglie la richiesta di strumento senza risposta, per non lasciare
        # nella cronologia una chiamata priva del ToolMessage corrispondente.
        return {
            "messages": [
                RemoveMessage(id=stato["messages"][-1].id),
                AIMessage(MESSAGGIO_LIMITE),
            ]
        }

    def instrada(stato: StatoConversazione) -> str:
        return instrada_dopo_modello(stato, max_passaggi)

    grafo = StateGraph(StatoConversazione)
    grafo.add_node("modello", nodo_modello)
    grafo.add_node("strumenti", nodo_strumenti)
    grafo.add_node("limite_raggiunto", nodo_limite_raggiunto)
    grafo.add_edge(START, "modello")
    grafo.add_conditional_edges(
        "modello",
        instrada,
        {"strumenti": "strumenti", "limite_raggiunto": "limite_raggiunto", "__end__": END},
    )
    grafo.add_edge("strumenti", "modello")
    grafo.add_edge("limite_raggiunto", END)
    return grafo.compile()
