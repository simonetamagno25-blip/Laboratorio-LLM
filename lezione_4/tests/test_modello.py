import httpx
import openai
from langchain_core.runnables import Runnable

from assistente.__main__ import main
from assistente.config import Configurazione
from assistente.modello import crea_modello, descrivi_errore
from assistente.strumenti import crea_strumenti


def test_descrivi_errore_connessione():
    exc = openai.APIConnectionError(request=httpx.Request("POST", "http://x"))
    assert descrivi_errore(exc, "http://localhost:1234/v1").startswith(
        "LM Studio non raggiungibile su http://localhost:1234/v1"
    )


def test_descrivi_errore_stato():
    risposta = httpx.Response(500, request=httpx.Request("POST", "http://x"))
    exc = openai.APIStatusError("rotto", response=risposta, body=None)
    assert descrivi_errore(exc, "u") == "LM Studio ha risposto con un errore (500): rotto"


def test_descrivi_errore_generico():
    assert descrivi_errore(RuntimeError("boh"), "u") == "Errore durante la risposta: boh"


def test_crea_modello_e_un_runnable():
    config = Configurazione("http://localhost:1234/v1", "m", "Europe/Rome", 3, "INFO")
    assert isinstance(crea_modello(config, crea_strumenti()), Runnable)


def test_main_senza_configurazione(monkeypatch, capsys):
    monkeypatch.delenv("LMSTUDIO_BASE_URL", raising=False)
    monkeypatch.delenv("LMSTUDIO_MODEL", raising=False)
    assert main() == 2
    assert "LMSTUDIO_BASE_URL" in capsys.readouterr().err
