"""API HTTP dell'agente con il grafo simulato: nessun modello attivo."""

from datetime import datetime, timezone

import httpx
import openai
import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, HumanMessage, messages_from_dict, messages_to_dict

from assistente.agente import Agente
from assistente.client_mcp import ArgomentoPrompt, ErroreMCP, InfoPrompt
from assistente.grafo import costruisci_grafo, limite_ricorsione
from assistente.note import apri_archivio
from assistente.servizio import crea_app
from assistente.strumenti import crea_strumenti
from tests.fakes import ModelloFinto, chiamata_strumento

AUTUNNO = lambda: datetime(2026, 10, 26, 16, 5, 12, tzinfo=timezone.utc)
BASE_URL = "http://localhost:1234/v1"


class McpFinto:
    def __init__(self, attivo=True):
        self.attivo = attivo

    def strumenti(self):
        return crea_strumenti(AUTUNNO)[:1] if self.attivo else []

    def elenca_prompt(self):
        if not self.attivo:
            raise ErroreMCP("sessione chiusa")
        return [InfoPrompt("spiega", "Spiega.", (ArgomentoPrompt("argomento", "concetto", True),))]

    def ottieni_prompt(self, nome, argomenti):
        if not self.attivo:
            raise ErroreMCP("sessione chiusa")
        return [("user", f"Spiegami {argomenti['argomento']}")]


def crea_client(risposte, *, archivio=None, modello_ok=True, mcp=None):
    modello = ModelloFinto(risposte)
    grafo = costruisci_grafo(
        modello, crea_strumenti(AUTUNNO, archivio=archivio), "Europe/Rome", 3, archivio=archivio
    )
    app = crea_app(
        Agente(grafo, limite_ricorsione(3)),
        mcp=mcp or McpFinto(),
        controlla_modello=lambda: None if modello_ok else "LM Studio non raggiungibile su x",
        base_url=BASE_URL,
    )
    return modello, TestClient(app)


def test_conversazione_con_strumento(caplog):
    import logging

    caplog.set_level(logging.INFO)
    _, client = crea_client([chiamata_strumento("Asia/Tokyo"), AIMessage("A Tokyo è l'01:05.")])
    r = client.post("/conversazione", json={"messaggio": "Che ore sono a Tokyo?"})
    assert r.status_code == 200, r.text
    corpo = r.json()
    assert corpo["tipo"] == "risposta"
    assert corpo["risposta"] == "A Tokyo è l'01:05."
    assert corpo["strumenti"] == [
        {
            "nome": "ora_corrente",
            "argomenti": {"fuso_orario": "Asia/Tokyo"},
            "risultato": "2026-10-27T01:05:12+09:00 (Asia/Tokyo)",
        }
    ]
    cronologia = messages_from_dict(corpo["cronologia"])
    assert [m.type for m in cronologia] == ["human", "ai", "tool", "ai"]
    righe = [r.getMessage() for r in caplog.records]
    assert any(r.startswith("api: POST /conversazione") for r in righe)
    assert "chiamata strumento ora_corrente con argomenti {'fuso_orario': 'Asia/Tokyo'}" in righe


def test_conversazione_senza_stato_cronologia_e_riassunto_dal_chiamante():
    modello, client = crea_client([AIMessage("Ti chiami Giulia.")])
    cronologia = messages_to_dict([HumanMessage("Mi chiamo Giulia"), AIMessage("Piacere!")])
    r = client.post(
        "/conversazione",
        json={"messaggio": "Come mi chiamo?", "cronologia": cronologia, "riassunto": "r"},
    )
    corpo = r.json()
    assert [m.content for m in modello.chiamate[0][1:]] == [
        "Mi chiamo Giulia", "Piacere!", "Come mi chiamo?"
    ]
    assert len(corpo["cronologia"]) == 4
    assert corpo["riassunto"] == "r"


def test_conversazione_con_messaggi_di_un_prompt():
    modello, client = crea_client([AIMessage("MCP è...")])
    messaggi = messages_to_dict([HumanMessage("Spiegami MCP")])
    r = client.post("/conversazione", json={"messaggi": messaggi})
    assert r.json()["risposta"] == "MCP è..."
    assert modello.chiamate[0][-1].content == "Spiegami MCP"


@pytest.mark.parametrize(
    "corpo",
    [{}, {"messaggio": "a", "messaggi": []}, {"messaggio": "  "}, {"messaggi": [{"x": 1}]}],
)
def test_richiesta_non_valida(corpo):
    modello, client = crea_client([])
    r = client.post("/conversazione", json=corpo)
    assert r.status_code == 422
    assert modello.chiamate == []


def test_modello_non_raggiungibile_503():
    errore = openai.APIConnectionError(request=httpx.Request("POST", BASE_URL))
    _, client = crea_client([errore])
    r = client.post("/conversazione", json={"messaggio": "Ciao"})
    assert r.status_code == 503
    assert r.json()["detail"].startswith(f"LM Studio non raggiungibile su {BASE_URL}")


def test_errore_del_modello_502():
    risposta = httpx.Response(500, request=httpx.Request("POST", BASE_URL))
    _, client = crea_client([openai.APIStatusError("rotto", response=risposta, body=None)])
    r = client.post("/conversazione", json={"messaggio": "Ciao"})
    assert r.status_code == 502
    assert "LM Studio ha risposto con un errore (500)" in r.json()["detail"]


@pytest.fixture
def archivio(tmp_path):
    archivio = apri_archivio(tmp_path / "note.sqlite3", "Europe/Rome", AUTUNNO)
    yield archivio
    archivio.chiudi()


def test_conferma_delle_note(archivio):
    nota = archivio.aggiungi("comprare cavi")
    _, client = crea_client(
        [chiamata_strumento(None, nome="elimina_nota", args={"numero": nota.numero}),
         AIMessage("Eliminata.")],
        archivio=archivio,
    )
    r = client.post("/conversazione", json={"messaggio": "elimina la nota sui cavi"})
    corpo = r.json()
    assert corpo["tipo"] == "conferma"
    assert "comprare cavi" in corpo["domanda"]
    r = client.post("/conferma", json={"id_conferma": corpo["id_conferma"], "conferma": True})
    assert r.json()["risposta"] == "Eliminata."
    assert archivio.leggi(nota.numero) is None
    r = client.post("/conferma", json={"id_conferma": corpo["id_conferma"], "conferma": True})
    assert r.status_code == 404


def test_stato_tutto_ok():
    _, client = crea_client([])
    r = client.get("/stato")
    assert r.status_code == 200
    assert r.json() == {
        "agente": "ok", "server_mcp": "ok", "strumenti_mcp": ["ora_corrente"], "modello": "ok"
    }


def test_stato_con_modello_e_mcp_giu():
    _, client = crea_client([], modello_ok=False, mcp=McpFinto(attivo=False))
    r = client.get("/stato")
    assert r.status_code == 503
    corpo = r.json()
    assert corpo["modello"] == "LM Studio non raggiungibile su x"
    assert corpo["server_mcp"] == "non disponibile"


def test_prompt():
    _, client = crea_client([])
    elenco = client.get("/prompts").json()
    assert elenco == [
        {
            "nome": "spiega",
            "descrizione": "Spiega.",
            "argomenti": [{"nome": "argomento", "descrizione": "concetto", "obbligatorio": True}],
        }
    ]
    r = client.post("/prompts/spiega", json={"argomenti": {"argomento": "MCP"}})
    assert r.json() == {"messaggi": [{"ruolo": "user", "testo": "Spiegami MCP"}]}


def test_prompt_con_mcp_giu_502():
    _, client = crea_client([], mcp=McpFinto(attivo=False))
    r = client.post("/prompts/spiega", json={"argomenti": {"argomento": "MCP"}})
    assert r.status_code == 502
    assert "sessione chiusa" in r.json()["detail"]


def test_documentazione_openapi():
    _, client = crea_client([])
    schema = client.get("/openapi.json").json()
    assert {"/conversazione", "/conferma", "/stato", "/prompts", "/prompts/{nome}"} <= set(
        schema["paths"]
    )
    assert client.get("/docs").status_code == 200
