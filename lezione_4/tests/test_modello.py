import pytest
import httpx
import openai
from langchain_core.runnables import Runnable

from assistente.servizio import main
from assistente.config import Configurazione
from assistente.modello import crea_modello, crea_router, descrivi_errore
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


CONFIG = Configurazione(
    "http://localhost:1234/v1",
    "m",
    "Europe/Rome",
    3,
    "INFO",
    "http://localhost:8000",
    "note.sqlite3",
    "ora e date",
)


def test_crea_modello_e_un_runnable():
    assert isinstance(crea_modello(CONFIG, crea_strumenti()), Runnable)


def test_crea_router_e_un_runnable():
    # La costruzione non contatta il server: nessuna rete.
    assert isinstance(crea_router(CONFIG), Runnable)


def test_main_senza_configurazione(monkeypatch, capsys):
    monkeypatch.delenv("LMSTUDIO_BASE_URL", raising=False)
    monkeypatch.delenv("LMSTUDIO_MODEL", raising=False)
    assert main() == 2
    assert "LMSTUDIO_BASE_URL" in capsys.readouterr().err


# --- Revisore: contratto con la libreria, con un server finto ---

import json

from langchain_core.messages import HumanMessage

from assistente import modello as modulo_modello
from assistente.revisore import DecisioneRevisore
from tests.fakes import chat_con_server_finto, risposta_del_server


def revisore_con_server(monkeypatch, contenuto, finish_reason="stop"):
    chat = chat_con_server_finto(risposta_del_server(contenuto, finish_reason))
    monkeypatch.setattr(modulo_modello, "_chat", lambda config: chat)
    return modulo_modello.crea_revisore(CONFIG)


def test_crea_revisore_output_valido(monkeypatch):
    revisore = revisore_con_server(
        monkeypatch, json.dumps({"coerente": False, "motivo": "manca il calcolo"})
    )
    esito = revisore.invoke([HumanMessage("x")])
    assert esito["parsed"] == DecisioneRevisore(coerente=False, motivo="manca il calcolo")


@pytest.mark.parametrize(
    "contenuto, finish_reason",
    [
        (json.dumps({"coerente": "forse", "motivo": "x"}), "stop"),
        ('{"coerente": tr', "stop"),
        (json.dumps({"coerente": True, "motivo": "x"}), "length"),
    ],
)
def test_crea_revisore_output_non_valido_non_solleva(monkeypatch, contenuto, finish_reason):
    revisore = revisore_con_server(monkeypatch, contenuto, finish_reason)
    esito = revisore.invoke([HumanMessage("x")])
    assert esito["parsed"] is None
    assert esito["parsing_error"] is not None


def test_crea_riassuntore_e_il_modello_senza_strumenti():
    from langchain_openai import ChatOpenAI

    riassuntore = modulo_modello.crea_riassuntore(CONFIG)
    assert isinstance(riassuntore, ChatOpenAI)


def test_timeout_del_modello_abbastanza_lungo_per_le_spiegazioni():
    # Prova reale: /prompt spiega con gemma-4-e2b superava i 120 secondi (ReadTimeout).
    assert modulo_modello._chat(CONFIG).request_timeout >= 300
