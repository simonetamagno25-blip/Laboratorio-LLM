"""Prova reale con LM Studio: richiede il server attivo e l'opzione --lmstudio."""

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from assistente.config import carica_configurazione
from assistente.grafo import costruisci_grafo, limite_ricorsione
from assistente.modello import crea_modello
from assistente.strumenti import crea_strumenti


@pytest.mark.lmstudio
def test_il_modello_reale_usa_lo_strumento():
    config = carica_configurazione()
    strumenti = crea_strumenti()
    grafo = costruisci_grafo(
        crea_modello(config, strumenti),
        strumenti,
        config.fuso_predefinito,
        config.max_passaggi_strumenti,
    )

    stato = grafo.invoke(
        {
            "messages": [HumanMessage("Che ore sono adesso a Tokyo?")],
            "passaggi_strumenti": 0,
        },
        {"recursion_limit": limite_ricorsione(config.max_passaggi_strumenti)},
    )
    messaggi = stato["messages"]

    chiamate = [
        c for m in messaggi if isinstance(m, AIMessage) for c in m.tool_calls
    ]
    assert any(c["name"] == "ora_corrente" for c in chiamate), messaggi

    risultati = [m for m in messaggi if isinstance(m, ToolMessage)]
    assert any("(Asia/Tokyo)" in m.content for m in risultati), messaggi

    ultimo = messaggi[-1]
    assert isinstance(ultimo, AIMessage) and not ultimo.tool_calls
    assert ultimo.content.strip(), messaggi
