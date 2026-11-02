import sys

import assistente.__main__ as punto_di_ingresso

ENV = {
    "LMSTUDIO_BASE_URL": "http://localhost:1234/v1",
    "LMSTUDIO_MODEL": "m",
    "SCADENZE_API_URL": "http://localhost:8000",
}


def test_server_mcp_che_non_parte_blocca_l_avvio(monkeypatch, capsys):
    for nome, valore in ENV.items():
        monkeypatch.setenv(nome, valore)
    monkeypatch.setattr(
        punto_di_ingresso,
        "comando_convertitore",
        lambda: (sys.executable, ["-c", "import sys; sys.exit(1)"]),
    )
    assert punto_di_ingresso.main() == 3
    assert "Server MCP del convertitore non avviato" in capsys.readouterr().err


def test_avvio_con_tutti_gli_strumenti(monkeypatch, capsys):
    for nome, valore in ENV.items():
        monkeypatch.setenv(nome, valore)
    nomi = []

    def ciclo_finto(sessione, base_url):
        nomi.extend(sessione.nomi_strumenti)

    class SessioneFinta:
        def __init__(self, grafo, limite):
            pass

    def crea_modello_finto(config, strumenti):
        SessioneFinta.nomi_strumenti = [s.name for s in strumenti]
        return object()

    monkeypatch.setattr(punto_di_ingresso, "crea_modello", crea_modello_finto)
    monkeypatch.setattr(punto_di_ingresso, "Sessione", SessioneFinta)
    monkeypatch.setattr(punto_di_ingresso, "esegui_ciclo", ciclo_finto)
    assert punto_di_ingresso.main() == 0
    assert nomi == [
        "ora_corrente",
        "calcola",
        "converti_unita",
        "giorni_tra_date",
        "calcola_scadenza",
    ]
