import os
import subprocess
import sys
import time

import pytest

from assistente.client_mcp import ClientMCP, ErroreMCP, comando_convertitore


def _vivo(pid: int) -> bool:
    if os.name == "nt":
        uscita = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True
        ).stdout
        return str(pid) in uscita
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


def _per_nome(client):
    return {s.name: s for s in client.strumenti()}


@pytest.fixture(scope="module")
def convertitore():
    with ClientMCP(*comando_convertitore()) as client:
        yield _per_nome(client)["converti_unita"]


def test_strumenti_del_convertitore():
    with ClientMCP(*comando_convertitore()) as client:
        assert [s.name for s in client.strumenti()] == ["converti_unita"]


def test_schema_con_elenco_chiuso(convertitore):
    assert "km" in str(convertitore.args["da"])
    assert "furlong" not in str(convertitore.args["da"])


def test_conversione(convertitore):
    assert convertitore.invoke({"valore": 26, "da": "mi", "a": "km"}) == "26 mi = 41.8429 km"


def test_grandezze_incompatibili(convertitore):
    assert convertitore.invoke({"valore": 5, "da": "kg", "a": "m"}).startswith("Errore:")


def test_unita_fuori_elenco(convertitore):
    risultato = convertitore.invoke({"valore": 1, "da": "furlong", "a": "m"})
    assert risultato.startswith("Errore:")
    assert "furlong" in risultato


def test_server_che_non_parte():
    client = ClientMCP(sys.executable, ["-c", "import sys; sys.exit(1)"], timeout_avvio=5)
    inizio = time.monotonic()
    with pytest.raises(ErroreMCP):
        client.avvia()
    assert time.monotonic() - inizio < 10


def test_server_inesistente():
    with pytest.raises(ErroreMCP):
        ClientMCP("comando-che-non-esiste-xyz", [], timeout_avvio=5).avvia()


def test_chiusura_termina_il_sottoprocesso():
    client = ClientMCP(sys.executable, ["-m", "tests.server_mcp_prova"])
    client.avvia()
    pid = int(_per_nome(client)["pid"].invoke({}))
    assert _vivo(pid)
    client.chiudi()
    client.chiudi()
    assert not _vivo(pid)


def test_server_caduto_durante_la_sessione():
    with ClientMCP(sys.executable, ["-m", "tests.server_mcp_prova"], timeout=5) as client:
        strumenti = _per_nome(client)
        assert strumenti["termina"].invoke({}).startswith("Errore: server MCP non disponibile")
        assert strumenti["pid"].invoke({}).startswith("Errore: server MCP non disponibile")


def test_timeout_della_chiamata():
    with ClientMCP(sys.executable, ["-m", "tests.server_mcp_prova"], timeout=1) as client:
        dormi = _per_nome(client)["dormi"]
        assert dormi.invoke({"secondi": 5}) == "Errore: timeout del server MCP"


def test_server_muto_scade_al_timeout_di_avvio():
    muto = ["-c", "import time; time.sleep(30)"]
    with pytest.raises(ErroreMCP, match="entro 2 secondi"):
        ClientMCP(sys.executable, muto, timeout_avvio=2).avvia()
