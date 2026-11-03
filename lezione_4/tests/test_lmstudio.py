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


@pytest.fixture(scope="module")
def grafo_completo(servizio_scadenze):
    import os

    from assistente.client_api import crea_strumenti_api
    from assistente.client_mcp import ClientMCP, comando_convertitore

    os.environ.setdefault("SCADENZE_API_URL", servizio_scadenze)
    config = carica_configurazione()
    with ClientMCP(*comando_convertitore()) as client:
        strumenti = crea_strumenti() + client.strumenti() + crea_strumenti_api(servizio_scadenze)
        grafo = costruisci_grafo(
            crea_modello(config, strumenti),
            strumenti,
            config.fuso_predefinito,
            config.max_passaggi_strumenti,
        )
        yield grafo, limite_ricorsione(config.max_passaggi_strumenti)


@pytest.mark.lmstudio
@pytest.mark.parametrize(
    "domanda, strumento, atteso",
    [
        ("Quanto fa (12 + 8) * 3 / 4?", "calcola", "= 15"),
        ("Quanti chilometri sono 26 miglia?", "converti_unita", "41.8429 km"),
        (
            "Quanti giorni lavorativi ci sono tra il 2026-12-20 e il 2027-01-10?",
            "giorni_tra_date",
            "12 giorni lavorativi",
        ),
        ("Converti 5 kg in metri.", "converti_unita", "Errore:"),
    ],
)
def test_il_modello_reale_usa_i_nuovi_strumenti(grafo_completo, domanda, strumento, atteso):
    grafo, limite = grafo_completo
    stato = grafo.invoke(
        {"messages": [HumanMessage(domanda)], "passaggi_strumenti": 0},
        {"recursion_limit": limite},
    )
    messaggi = stato["messages"]
    risultati = [m for m in messaggi if isinstance(m, ToolMessage) and m.name == strumento]
    assert any(atteso in m.content for m in risultati), messaggi
    print(f"\n{domanda}\n-> {messaggi[-1].content}")
