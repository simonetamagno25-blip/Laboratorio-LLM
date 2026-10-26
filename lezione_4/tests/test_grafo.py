import logging
from datetime import datetime, timezone

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from assistente.grafo import (
    MESSAGGIO_LIMITE,
    costruisci_grafo,
    instrada_dopo_modello,
    limite_ricorsione,
)
from assistente.strumenti import crea_strumenti
from tests.fakes import ModelloFinto, chiamata_strumento

AUTUNNO = lambda: datetime(2026, 10, 26, 16, 5, 12, tzinfo=timezone.utc)


def crea(risposte, max_passaggi=3):
    modello = ModelloFinto(risposte)
    grafo = costruisci_grafo(modello, crea_strumenti(AUTUNNO), "Europe/Rome", max_passaggi)
    return modello, grafo


def invoca(grafo, testo, max_passaggi=3):
    return grafo.invoke(
        {"messages": [HumanMessage(testo)], "passaggi_strumenti": 0},
        {"recursion_limit": limite_ricorsione(max_passaggi)},
    )


def test_instradamento_senza_chiamate_finisce():
    stato = {"messages": [AIMessage("Ciao")], "passaggi_strumenti": 0}
    assert instrada_dopo_modello(stato, 3) == "__end__"


def test_instradamento_con_chiamate_va_agli_strumenti():
    stato = {"messages": [chiamata_strumento("Europe/Rome")], "passaggi_strumenti": 0}
    assert instrada_dopo_modello(stato, 3) == "strumenti"


def test_instradamento_al_limite():
    stato = {"messages": [chiamata_strumento("Europe/Rome")], "passaggi_strumenti": 3}
    assert instrada_dopo_modello(stato, 3) == "limite_raggiunto"


def test_risposta_diretta():
    modello, grafo = crea([AIMessage("Ciao!")])
    stato = invoca(grafo, "Ciao")
    assert stato["messages"][-1].content == "Ciao!"
    assert len(modello.chiamate) == 1
    primo = modello.chiamate[0][0]
    assert isinstance(primo, SystemMessage)
    assert "Europe/Rome" in primo.content
    assert not any(isinstance(m, SystemMessage) for m in stato["messages"])


def test_ciclo_con_strumento():
    modello, grafo = crea([chiamata_strumento("Europe/Rome"), AIMessage("Sono le 17:05.")])
    stato = invoca(grafo, "Che ore sono?")
    assert len(modello.chiamate) == 2
    risultati = [m for m in modello.chiamate[1] if isinstance(m, ToolMessage)]
    assert len(risultati) == 1
    assert risultati[0].content == "2026-10-26T17:05:12+01:00 (Europe/Rome)"
    assert risultati[0].tool_call_id == "call_1"
    assert stato["messages"][-1].content == "Sono le 17:05."


def test_due_chiamate_nella_stessa_risposta():
    due = AIMessage(
        content="",
        tool_calls=[
            {"name": "ora_corrente", "args": {"fuso_orario": "Europe/Rome"}, "id": "a", "type": "tool_call"},
            {"name": "ora_corrente", "args": {"fuso_orario": "Asia/Tokyo"}, "id": "b", "type": "tool_call"},
        ],
    )
    _, grafo = crea([due, AIMessage("Fatto.")])
    stato = invoca(grafo, "Ora a Roma e Tokyo?")
    risultati = [m for m in stato["messages"] if isinstance(m, ToolMessage)]
    assert [m.tool_call_id for m in risultati] == ["a", "b"]
    assert risultati[0].content == "2026-10-26T17:05:12+01:00 (Europe/Rome)"
    assert risultati[1].content == "2026-10-27T01:05:12+09:00 (Asia/Tokyo)"


@pytest.mark.parametrize(
    "nome,args",
    [
        ("ora_corrente", {}),
        ("ora_corrente", {"timezone": "Europe/Rome"}),
        ("meteo", {"citta": "Roma"}),
    ],
)
def test_chiamata_errata_diventa_messaggio_di_errore(nome, args):
    _, grafo = crea([chiamata_strumento(None, nome=nome, args=args), AIMessage("Non ci riesco.")])
    stato = invoca(grafo, "Che ore sono?")
    risultati = [m for m in stato["messages"] if isinstance(m, ToolMessage)]
    assert len(risultati) == 1
    assert risultati[0].content.startswith("Errore")
    assert stato["messages"][-1].content == "Non ci riesco."


def test_limite_passaggi():
    risposte = [chiamata_strumento("Europe/Rome", id=f"call_{i}") for i in range(4)]
    modello, grafo = crea(risposte, max_passaggi=2)
    stato = invoca(grafo, "Che ore sono?", max_passaggi=2)
    messaggi = stato["messages"]
    assert len(modello.chiamate) == 3
    assert sum(isinstance(m, ToolMessage) for m in messaggi) == 2
    assert messaggi[-1].content == MESSAGGIO_LIMITE
    risposti = {m.tool_call_id for m in messaggi if isinstance(m, ToolMessage)}
    for m in messaggi:
        if isinstance(m, AIMessage):
            assert all(c["id"] in risposti for c in m.tool_calls)


def test_log_della_chiamata(caplog):
    _, grafo = crea([chiamata_strumento("Europe/Rome"), AIMessage("Fatto.")])
    with caplog.at_level(logging.INFO, logger="assistente.grafo"):
        invoca(grafo, "Che ore sono?")
    testo = caplog.text
    assert "ora_corrente" in testo
    assert "Europe/Rome" in testo
    assert "2026-10-26T17:05:12+01:00" in testo


def chiamata_non_valida(id: str = "bad_1") -> AIMessage:
    return AIMessage(
        content="",
        invalid_tool_calls=[
            {
                "name": "ora_corrente",
                "args": "{fuso_orario: Europe/Rome",
                "id": id,
                "error": "JSON non valido",
                "type": "invalid_tool_call",
            }
        ],
    )


def test_instradamento_con_chiamate_non_valide_va_agli_strumenti():
    stato = {"messages": [chiamata_non_valida()], "passaggi_strumenti": 0}
    assert instrada_dopo_modello(stato, 3) == "strumenti"


def test_instradamento_con_chiamate_non_valide_al_limite():
    stato = {"messages": [chiamata_non_valida()], "passaggi_strumenti": 3}
    assert instrada_dopo_modello(stato, 3) == "limite_raggiunto"


def test_chiamata_non_valida_diventa_messaggio_di_errore(caplog):
    modello, grafo = crea([chiamata_non_valida(), AIMessage("ok")])
    with caplog.at_level(logging.WARNING, logger="assistente.grafo"):
        stato = invoca(grafo, "Che ore sono?")
    assert len(modello.chiamate) == 2
    risultati = [m for m in modello.chiamate[1] if isinstance(m, ToolMessage)]
    assert len(risultati) == 1
    assert risultati[0].tool_call_id == "bad_1"
    assert risultati[0].name == "ora_corrente"
    assert risultati[0].content.startswith("Errore")
    assert stato["messages"][-1].content == "ok"
    assert "argomenti non validi" in caplog.text


def test_limite_con_chiamata_non_valida_non_lascia_chiamate_senza_risposta():
    _, grafo = crea([chiamata_non_valida()], max_passaggi=1)
    stato = {"messages": [HumanMessage("Che ore sono?")], "passaggi_strumenti": 1}
    risultato = grafo.invoke(stato, {"recursion_limit": limite_ricorsione(1)})
    messaggi = risultato["messages"]
    assert messaggi[-1].content == MESSAGGIO_LIMITE
    assert not any(isinstance(m, AIMessage) and m.invalid_tool_calls for m in messaggi)
