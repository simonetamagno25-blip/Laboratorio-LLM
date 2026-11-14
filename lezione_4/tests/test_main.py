"""CLI (python -m assistente): client dell'API dell'agente."""

import assistente.__main__ as punto_di_ingresso
from assistente.client_agente import ErroreAgente, PromptRemoti, SessioneRemota


def test_la_cli_usa_l_agente_indicato_da_agente_url(monkeypatch, capsys):
    monkeypatch.setenv("AGENTE_URL", "http://agente:9000/")
    ricevuti = []
    monkeypatch.setattr(SessioneRemota, "stato", lambda self: {"modello": "ok", "server_mcp": "ok"})
    monkeypatch.setattr(
        punto_di_ingresso,
        "esegui_ciclo",
        lambda sessione, url, prompt=None: ricevuti.append((sessione, url, prompt)),
    )
    assert punto_di_ingresso.main() == 0
    sessione, url, prompt = ricevuti[0]
    assert isinstance(sessione, SessioneRemota) and isinstance(prompt, PromptRemoti)
    assert url == "http://agente:9000"
    assert "agente: http://agente:9000" in capsys.readouterr().out


def test_la_cli_parte_anche_con_l_agente_spento(monkeypatch, capsys):
    monkeypatch.delenv("AGENTE_URL", raising=False)

    def spento(self):
        raise ErroreAgente("Agente non raggiungibile su http://localhost:8100")

    monkeypatch.setattr(SessioneRemota, "stato", spento)
    monkeypatch.setattr(punto_di_ingresso, "esegui_ciclo", lambda *a, **k: None)
    assert punto_di_ingresso.main() == 0
    uscita = capsys.readouterr().out
    assert "Attenzione: Agente non raggiungibile su http://localhost:8100" in uscita
    assert "python -m assistente.servizio" in uscita
