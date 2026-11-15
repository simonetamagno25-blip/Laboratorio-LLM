"""API del back-end con l'agente simulato (httpx.MockTransport) e l'archivio in memoria."""

import json

import httpx
import pytest
from fastapi.testclient import TestClient

from backend.__main__ import carica
from backend.agente import ClientAgente
from backend.app import crea_app
from backend.archivio import ArchivioMemoria

STRUMENTO = {"nome": "ora_corrente", "argomenti": {"fuso_orario": "Asia/Tokyo"}, "risultato": "x"}


class AgenteSimulato:
    """Risposte dell'agente decise dal test; registra le richieste ricevute."""

    def __init__(self, risposte):
        self.risposte = list(risposte)
        self.richieste = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        if request.url.path == "/stato":
            return httpx.Response(200, json={"agente": "ok", "server_mcp": "ok",
                                             "strumenti_mcp": [], "modello": "ok"})
        self.richieste.append((request.url.path, json.loads(request.content)))
        risposta = self.risposte.pop(0)
        if isinstance(risposta, Exception):
            raise risposta
        return risposta


def risposta(testo, strumenti=(), cronologia=None, riassunto=""):
    return httpx.Response(200, json={
        "tipo": "risposta", "risposta": testo, "strumenti": list(strumenti),
        "cronologia": cronologia or [{"type": "ai", "data": {"content": testo}}],
        "riassunto": riassunto,
    })


def crea(risposte):
    simulato = AgenteSimulato(risposte)
    http = httpx.Client(transport=httpx.MockTransport(simulato), base_url="http://agente:8100")
    archivio = ArchivioMemoria()
    client = TestClient(crea_app(archivio, ClientAgente("http://agente:8100", http=http)))
    return simulato, archivio, client


def test_ciclo_completo_di_una_chat():
    simulato, _, client = crea([
        risposta("A Tokyo sono le 01:05.", [STRUMENTO], cronologia=[{"turno": 1}], riassunto="r1"),
        risposta("Prego!", cronologia=[{"turno": 2}]),
    ])
    r = client.post("/api/chat")
    assert r.status_code == 201
    id_chat = r.json()["id"]
    r = client.post(f"/api/chat/{id_chat}/messaggi", json={"testo": "Che ore sono a Tokyo?"})
    assert r.json() == {"tipo": "risposta", "risposta": "A Tokyo sono le 01:05.",
                        "strumenti": [STRUMENTO], "domanda": None}
    client.post(f"/api/chat/{id_chat}/messaggi", json={"testo": "Grazie"})
    # Il secondo turno manda all'agente la cronologia e il riassunto restituiti dal primo.
    assert simulato.richieste[1] == (
        "/conversazione", {"messaggio": "Grazie", "cronologia": [{"turno": 1}], "riassunto": "r1"}
    )
    chat = client.get(f"/api/chat/{id_chat}").json()
    assert chat["titolo"] == "Che ore sono a Tokyo?"
    assert [(m["ruolo"], m["testo"]) for m in chat["messaggi"]] == [
        ("utente", "Che ore sono a Tokyo?"), ("assistente", "A Tokyo sono le 01:05."),
        ("utente", "Grazie"), ("assistente", "Prego!"),
    ]
    assert chat["messaggi"][1]["strumenti"] == [STRUMENTO]
    elenco = client.get("/api/chat").json()
    assert elenco[0]["id"] == id_chat and elenco[0]["ultimo_messaggio"]
    assert client.delete(f"/api/chat/{id_chat}").status_code == 204
    assert client.get(f"/api/chat/{id_chat}").status_code == 404
    assert client.get("/api/chat").json() == []


def test_agente_non_raggiungibile_niente_salvato():
    _, archivio, client = crea([httpx.ConnectError("rifiutata")])
    id_chat = client.post("/api/chat").json()["id"]
    r = client.post(f"/api/chat/{id_chat}/messaggi", json={"testo": "Ciao"})
    assert r.status_code == 503
    assert r.json()["detail"].startswith("Agente non raggiungibile su http://agente:8100")
    assert "non è stata salvata" in r.json()["detail"]
    assert client.get(f"/api/chat/{id_chat}").json()["messaggi"] == []


def test_errore_dell_agente_niente_salvato():
    _, _, client = crea([httpx.Response(503, json={"detail": "LM Studio non raggiungibile su x"})])
    id_chat = client.post("/api/chat").json()["id"]
    r = client.post(f"/api/chat/{id_chat}/messaggi", json={"testo": "Ciao"})
    assert r.status_code == 502
    assert r.json()["detail"].startswith("LM Studio non raggiungibile su x")
    assert client.get(f"/api/chat/{id_chat}").json()["messaggi"] == []


def test_conferma_di_un_eliminazione():
    simulato, _, client = crea([
        httpx.Response(200, json={"tipo": "conferma", "domanda": "Eliminare la nota 1?",
                                  "id_conferma": "abc"}),
        risposta("Nota eliminata."),
    ])
    id_chat = client.post("/api/chat").json()["id"]
    r = client.post(f"/api/chat/{id_chat}/messaggi", json={"testo": "elimina la nota 1"})
    assert r.json()["tipo"] == "conferma" and r.json()["domanda"] == "Eliminare la nota 1?"
    assert client.get(f"/api/chat/{id_chat}").json()["conferma_in_attesa"] is True
    # Finché la conferma è in attesa non si possono mandare altre domande.
    assert client.post(f"/api/chat/{id_chat}/messaggi", json={"testo": "x"}).status_code == 409
    r = client.post(f"/api/chat/{id_chat}/conferma", json={"conferma": True})
    assert r.json()["risposta"] == "Nota eliminata."
    assert simulato.richieste[-1] == ("/conferma", {"id_conferma": "abc", "conferma": True})
    chat = client.get(f"/api/chat/{id_chat}").json()
    assert chat["conferma_in_attesa"] is False
    assert [m["ruolo"] for m in chat["messaggi"]] == ["utente", "assistente"]


def test_chat_inesistente_e_richieste_non_valide():
    _, _, client = crea([])
    assert client.post("/api/chat/42/messaggi", json={"testo": "x"}).status_code == 404
    assert client.delete("/api/chat/42").status_code == 404
    assert client.post("/api/chat/42/conferma", json={"conferma": True}).status_code == 404
    id_chat = client.post("/api/chat").json()["id"]
    assert client.post(f"/api/chat/{id_chat}/messaggi", json={"testo": "  "}).status_code == 422
    assert client.post(f"/api/chat/{id_chat}/conferma", json={"conferma": True}).status_code == 409


def test_stato_e_openapi():
    _, _, client = crea([])
    assert client.get("/api/stato").json() == {"backend": "ok", "database": "ok", "agente": "ok"}
    schema = client.get("/api/openapi.json").json()
    assert {"/api/chat", "/api/chat/{id_chat}", "/api/chat/{id_chat}/messaggi",
            "/api/chat/{id_chat}/conferma", "/api/stato"} <= set(schema["paths"])
    assert client.get("/api/docs").status_code == 200


def test_stato_con_agente_spento():
    def rifiuta(request):
        raise httpx.ConnectError("rifiutata", request=request)

    http = httpx.Client(transport=httpx.MockTransport(rifiuta), base_url="http://agente:8100")
    client = TestClient(crea_app(ArchivioMemoria(), ClientAgente("http://agente:8100", http=http)))
    assert client.get("/api/stato").json()["agente"] == "non raggiungibile"


def test_configurazione():
    config = carica({"DATABASE_URL": "postgresql://a:b@db/chat"})
    assert (config.agente_url, config.host, config.porta) == ("http://localhost:8100", "127.0.0.1", 8200)
    assert config.origini == ["http://localhost:8300"]
    with pytest.raises(ValueError, match="DATABASE_URL"):
        carica({})
    with pytest.raises(ValueError, match="BACKEND_PORTA"):
        carica({"DATABASE_URL": "x", "BACKEND_PORTA": "0"})


def test_conferma_scaduta_sblocca_la_chat():
    # L'agente è stato riavviato (o la ripresa è fallita): non conosce più la conferma.
    _, _, client = crea([
        httpx.Response(200, json={"tipo": "conferma", "domanda": "Eliminare la nota 1?",
                                  "id_conferma": "abc"}),
        httpx.Response(404, json={"detail": "nessuna conferma in attesa con id abc"}),
        risposta("Ecco le tue note."),
    ])
    id_chat = client.post("/api/chat").json()["id"]
    client.post(f"/api/chat/{id_chat}/messaggi", json={"testo": "elimina la nota 1"})
    r = client.post(f"/api/chat/{id_chat}/conferma", json={"conferma": True})
    assert r.status_code == 409
    assert "non è più valida" in r.json()["detail"]
    assert client.get(f"/api/chat/{id_chat}").json()["conferma_in_attesa"] is False
    # La chat è di nuovo utilizzabile.
    r = client.post(f"/api/chat/{id_chat}/messaggi", json={"testo": "Quali note ho?"})
    assert r.json()["risposta"] == "Ecco le tue note."


def test_la_domanda_di_conferma_resta_dopo_il_ricaricamento():
    _, _, client = crea([
        httpx.Response(200, json={"tipo": "conferma", "domanda": "Eliminare la nota 1: \"cavi\"?",
                                  "id_conferma": "abc"}),
    ])
    id_chat = client.post("/api/chat").json()["id"]
    client.post(f"/api/chat/{id_chat}/messaggi", json={"testo": "elimina la nota 1"})
    chat = client.get(f"/api/chat/{id_chat}").json()
    assert chat["domanda_conferma"] == "Eliminare la nota 1: \"cavi\"?"


def test_errore_su_conferma_non_parla_di_domanda_non_salvata():
    _, _, client = crea([
        httpx.Response(200, json={"tipo": "conferma", "domanda": "Eliminare?", "id_conferma": "abc"}),
        httpx.Response(503, json={"detail": "LM Studio non raggiungibile su x"}),
    ])
    id_chat = client.post("/api/chat").json()["id"]
    client.post(f"/api/chat/{id_chat}/messaggi", json={"testo": "elimina la nota 1"})
    r = client.post(f"/api/chat/{id_chat}/conferma", json={"conferma": True})
    assert r.status_code == 502
    assert "domanda non è stata salvata" not in r.json()["detail"]


def test_timeout_dell_agente_non_e_agente_spento():
    _, _, client = crea([httpx.ReadTimeout("lento")])
    id_chat = client.post("/api/chat").json()["id"]
    r = client.post(f"/api/chat/{id_chat}/messaggi", json={"testo": "Ciao"})
    assert r.status_code == 504
    assert "non ha risposto in tempo" in r.json()["detail"]
    assert "non raggiungibile" not in r.json()["detail"]
