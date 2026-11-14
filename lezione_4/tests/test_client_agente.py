"""CLI come client dell'API: SessioneRemota e PromptRemoti contro l'app vera, con il grafo simulato."""

from datetime import datetime, timezone

import httpx
import openai
import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, HumanMessage

from assistente.agente import Agente
from assistente.cli import Conferma, Sessione, esegui_ciclo
from assistente.client_agente import ErroreAgente, PromptRemoti, SessioneRemota
from assistente.client_mcp import ErroreMCP
from assistente.grafo import costruisci_grafo, limite_ricorsione
from assistente.note import apri_archivio
from assistente.servizio import crea_app
from assistente.strumenti import crea_strumenti
from tests.fakes import ModelloFinto, chiamata_strumento
from tests.test_servizio import McpFinto

AUTUNNO = lambda: datetime(2026, 10, 26, 16, 5, 12, tzinfo=timezone.utc)


def grafo_con(risposte, archivio=None):
    modello = ModelloFinto(risposte)
    grafo = costruisci_grafo(
        modello, crea_strumenti(AUTUNNO, archivio=archivio), "Europe/Rome", 3, archivio=archivio
    )
    return modello, grafo


def remota(risposte, archivio=None, mcp=None):
    modello, grafo = grafo_con(risposte, archivio)
    app = crea_app(
        Agente(grafo, limite_ricorsione(3)),
        mcp=mcp or McpFinto(),
        controlla_modello=lambda: None,
        base_url="http://lm/v1",
    )
    http = TestClient(app)
    return modello, SessioneRemota("http://testserver", http=http), PromptRemoti(
        "http://testserver", http=http
    )


def test_stessa_risposta_dalla_cli_locale_e_dall_api():
    risposte = lambda: [chiamata_strumento("Asia/Tokyo"), AIMessage("A Tokyo è l'01:05.")]
    _, grafo = grafo_con(risposte())
    locale = Sessione(grafo, limite_ricorsione(3))
    _, sessione_remota, _ = remota(risposte())
    assert locale.chiedi("Che ore sono a Tokyo?") == sessione_remota.chiedi("Che ore sono a Tokyo?")
    assert [m.content for m in locale.cronologia] == [m.content for m in sessione_remota.cronologia]


def test_la_cronologia_resta_nel_client_e_torna_all_agente():
    modello, sessione, _ = remota([AIMessage("Piacere!"), AIMessage("Ti chiami Giulia.")])
    sessione.chiedi("Mi chiamo Giulia")
    assert sessione.chiedi("Come mi chiamo?") == "Ti chiami Giulia."
    assert [m.content for m in modello.chiamate[1][1:]] == [
        "Mi chiamo Giulia", "Piacere!", "Come mi chiamo?"
    ]
    assert len(sessione.cronologia) == 4


def test_conferma_via_api(tmp_path):
    archivio = apri_archivio(tmp_path / "n.sqlite3", "Europe/Rome", AUTUNNO)
    try:
        nota = archivio.aggiungi("comprare cavi")
        _, sessione, _ = remota(
            [chiamata_strumento(None, nome="elimina_nota", args={"numero": nota.numero}),
             AIMessage("Eliminata.")],
            archivio=archivio,
        )
        esito = sessione.chiedi("elimina la nota sui cavi")
        assert isinstance(esito, Conferma) and "comprare cavi" in esito.domanda
        assert sessione.conferma(True) == "Eliminata."
        assert archivio.leggi(nota.numero) is None
    finally:
        archivio.chiudi()


def test_errore_del_modello_mostrato_dalla_cli():
    errore = openai.APIConnectionError(request=httpx.Request("POST", "http://lm/v1"))
    _, sessione, _ = remota([errore])
    with pytest.raises(ErroreAgente, match="LM Studio non raggiungibile su http://lm/v1"):
        sessione.chiedi("Ciao")
    assert sessione.cronologia == []


def test_agente_non_raggiungibile():
    def rifiuta(request):
        raise httpx.ConnectError("rifiutata", request=request)

    http = httpx.Client(transport=httpx.MockTransport(rifiuta), base_url="http://agente:8100")
    sessione = SessioneRemota("http://agente:8100", http=http)
    with pytest.raises(ErroreAgente, match="Agente non raggiungibile su http://agente:8100"):
        sessione.chiedi("Ciao")
    with pytest.raises(ErroreMCP, match="Agente non raggiungibile"):
        PromptRemoti("http://agente:8100", http=http).elenca_prompt()


def test_prompt_remoti():
    _, _, prompt = remota([])
    (info,) = prompt.elenca_prompt()
    assert info.nome == "spiega" and info.argomenti[0].obbligatorio
    assert prompt.ottieni_prompt("spiega", {"argomento": "MCP"}) == [("user", "Spiegami MCP")]


def test_ciclo_della_cli_con_l_api():
    modello, sessione, prompt = remota([AIMessage("MCP è un protocollo.")])
    voci = iter(["/prompts", "/prompt spiega argomento=MCP", "/esci"])
    uscite = []
    esegui_ciclo(
        sessione, "http://testserver", leggi=lambda _: next(voci), scrivi=uscite.append,
        scarta_anticipato=lambda: None, prompt=prompt,
    )
    testo = "\n".join(uscite)
    assert "spiega — Spiega." in testo
    assert "Assistente> MCP è un protocollo." in testo
    assert modello.chiamate[0][-1].content == "Spiegami MCP"


def test_ciclo_mostra_l_errore_dell_agente_e_resta_aperto():
    errore = openai.APIConnectionError(request=httpx.Request("POST", "http://lm/v1"))
    _, sessione, _ = remota([errore, AIMessage("ciao")])
    voci = iter(["Ciao", "Ciao", "/esci"])
    uscite = []
    esegui_ciclo(sessione, "http://testserver", leggi=lambda _: next(voci), scrivi=uscite.append,
                 scarta_anticipato=lambda: None)
    assert any(u.startswith("LM Studio non raggiungibile su http://lm/v1") for u in uscite)
    assert "Assistente> ciao" in uscite
