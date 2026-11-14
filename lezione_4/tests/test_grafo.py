import logging
from datetime import datetime, timezone

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from assistente.grafo import (
    MESSAGGIO_LIMITE,
    costruisci_grafo,
    instrada_dopo_modello,
    instrada_dopo_router,
    limite_ricorsione,
    prompt_di_sistema,
)
from assistente.router import DecisioneRouter, messaggio_rifiuto
from assistente.strumenti import crea_strumenti
from tests.fakes import ModelloFinto, RouterFinto, chiamata_strumento

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


@pytest.fixture(scope="module")
def tutti_gli_strumenti(servizio_scadenze):
    from assistente.client_api import crea_strumenti_api
    from assistente.client_mcp import ClientMCP, comando_convertitore

    with ClientMCP(*comando_convertitore()) as client:
        yield crea_strumenti(AUTUNNO) + client.strumenti() + crea_strumenti_api(servizio_scadenze)


@pytest.mark.parametrize(
    "nome, args, controllo",
    [
        ("calcola", {"espressione": "2 + 2"}, lambda t: t == "2 + 2 = 4"),
        ("converti_unita", {"valore": 26, "da": "mi", "a": "km"}, lambda t: t == "26 mi = 41.8429 km"),
        (
            "giorni_tra_date",
            {"inizio": "2026-12-20", "fine": "2027-01-10", "solo_lavorativi": True},
            lambda t: t.startswith("12 giorni lavorativi") and t.endswith("normativo.)"),
        ),
        (
            "calcola_scadenza",
            {"inizio": "2026-12-23", "giorni": 3, "solo_lavorativi": True},
            lambda t: "2026-12-29" in t,
        ),
    ],
)
def test_nuovi_strumenti_passano_dal_nodo_strumenti(tutti_gli_strumenti, nome, args, controllo):
    modello = ModelloFinto([chiamata_strumento(None, nome=nome, args=args), AIMessage("Fatto.")])
    grafo = costruisci_grafo(modello, tutti_gli_strumenti, "Europe/Rome", 3)
    stato = invoca(grafo, "domanda")
    [risultato] = [m for m in stato["messages"] if isinstance(m, ToolMessage)]
    assert risultato.name == nome
    assert controllo(risultato.content), risultato.content


def test_ricerca_poi_dettaglio():
    modello, grafo = crea(
        [
            chiamata_strumento(None, id="c1", nome="cerca_articoli", args={"testo": "umidità"}),
            chiamata_strumento(None, id="c2", nome="dettaglio_articolo", args={"codice": "SEN-004"}),
            AIMessage("È nell'armadio B, ripiano 2."),
        ]
    )
    stato = invoca(grafo, "Dov'è il sensore di umidità?")
    assert len(modello.chiamate) == 3
    [ricerca] = [m for m in modello.chiamate[1] if isinstance(m, ToolMessage)]
    assert ricerca.tool_call_id == "c1" and "SEN-004" in ricerca.content
    dettaglio = [m for m in modello.chiamate[2] if isinstance(m, ToolMessage)][-1]
    assert dettaglio.tool_call_id == "c2" and "posizione:" in dettaglio.content
    assert stato["messages"][-1].content == "È nell'armadio B, ripiano 2."


def test_prompt_di_sistema_cita_il_catalogo():
    testo = prompt_di_sistema("Europe/Rome")
    assert "cerca_articoli" in testo and "dettaglio_articolo" in testo
    # Il modello reale non cercava per "Avete stampanti 3D?" e "Dov'è il sensore di umidità?".
    assert "usa sempre cerca_articoli prima di rispondere" in testo
    assert "dove si trova" in testo
    assert "anche se pensi che non ci sia" in testo


def test_prompt_di_sistema_impone_il_convertitore():
    # Con la frase del catalogo il modello rifiutava "5 kg in metri" senza chiamare lo strumento.
    testo = prompt_di_sistema("Europe/Rome")
    assert "usa sempre converti_unita" in testo
    assert "anche se le unità ti sembrano incompatibili" in testo


def test_prompt_di_sistema_cita_i_nuovi_strumenti():
    testo = prompt_di_sistema("Europe/Rome")
    for nome in ("ora_corrente", "calcola", "converti_unita", "giorni_tra_date", "calcola_scadenza"):
        assert nome in testo
    assert "non calcolare a mente" in testo


# --- Note: conferma dell'eliminazione ---

from langgraph.types import Command

from assistente.note import apri_archivio

CONFIG_NOTE = {"recursion_limit": limite_ricorsione(3), "configurable": {"thread_id": "t"}}


@pytest.fixture
def archivio(tmp_path):
    archivio = apri_archivio(tmp_path / "note.sqlite3", "Europe/Rome", AUTUNNO)
    yield archivio
    archivio.chiudi()


def crea_con_note(risposte, archivio):
    modello = ModelloFinto(risposte)
    strumenti = crea_strumenti(AUTUNNO, archivio=archivio)
    grafo = costruisci_grafo(modello, strumenti, "Europe/Rome", 3, archivio=archivio)
    return modello, grafo


def elimina(numero, id="call_1"):
    return chiamata_strumento(None, id=id, nome="elimina_nota", args={"numero": numero})


def avvia(grafo, testo="elimina"):
    return grafo.invoke({"messages": [HumanMessage(testo)], "passaggi_strumenti": 0}, CONFIG_NOTE)


def esiti(stato):
    return {m.tool_call_id: m.content for m in stato["messages"] if isinstance(m, ToolMessage)}


def test_instradamento_elimina_va_alla_conferma():
    stato = {"messages": [elimina(1)], "passaggi_strumenti": 0}
    assert instrada_dopo_modello(stato, 3) == "conferma_eliminazione"


def test_instradamento_elimina_al_limite():
    stato = {"messages": [elimina(1)], "passaggi_strumenti": 3}
    assert instrada_dopo_modello(stato, 3) == "limite_raggiunto"


def test_elimina_si_ferma_con_i_dati_dell_archivio(archivio):
    archivio.aggiungi("sensore SEN-004 da ricalibrare")
    _, grafo = crea_con_note([elimina(1), AIMessage("fatto")], archivio)
    esito = avvia(grafo)
    assert esito["__interrupt__"][0].value == {
        "numero": 1,
        "creata": "2026-10-26 17:05",
        "testo": "sensore SEN-004 da ricalibrare",
    }
    assert archivio.leggi(1) is not None


def test_elimina_confermata(archivio):
    archivio.aggiungi("sensore SEN-004 da ricalibrare")
    _, grafo = crea_con_note([elimina(1), AIMessage("fatto")], archivio)
    avvia(grafo)
    stato = grafo.invoke(Command(resume=True), CONFIG_NOTE)
    assert archivio.leggi(1) is None
    assert esiti(stato) == {"call_1": "Nota 1 eliminata."}
    assert stato["messages"][-1].content == "fatto"


def test_elimina_rifiutata(archivio):
    archivio.aggiungi("sensore SEN-004 da ricalibrare")
    _, grafo = crea_con_note([elimina(1), AIMessage("lasciata")], archivio)
    avvia(grafo)
    stato = grafo.invoke(Command(resume=False), CONFIG_NOTE)
    assert archivio.leggi(1) is not None
    assert esiti(stato) == {
        "call_1": "Eliminazione annullata dall'utente: la nota 1 non è stata eliminata."
    }


def test_elimina_con_numero_stringa(archivio):
    archivio.aggiungi("sensore")
    _, grafo = crea_con_note([elimina("1"), AIMessage("fatto")], archivio)
    assert "__interrupt__" in avvia(grafo)
    grafo.invoke(Command(resume=True), CONFIG_NOTE)
    assert archivio.leggi(1) is None


@pytest.mark.parametrize("numero", [7, 0, -1, True, "tre"])
def test_elimina_numero_non_valido_senza_pausa(archivio, numero):
    archivio.aggiungi("sensore")
    _, grafo = crea_con_note([elimina(numero), AIMessage("niente")], archivio)
    stato = avvia(grafo)
    assert "__interrupt__" not in stato
    assert archivio.leggi(1) is not None
    esito = esiti(stato)["call_1"]
    assert "non trovata" in esito or esito.startswith("Errore"), esito


def test_due_eliminazioni_una_conferma(archivio):
    archivio.aggiungi("prima")
    archivio.aggiungi("seconda")
    doppia = AIMessage(
        content="",
        tool_calls=[
            {"name": "elimina_nota", "args": {"numero": 1}, "id": "a", "type": "tool_call"},
            {"name": "elimina_nota", "args": {"numero": 2}, "id": "b", "type": "tool_call"},
        ],
    )
    _, grafo = crea_con_note([doppia, AIMessage("fatto")], archivio)
    esito = avvia(grafo)
    assert [i.value["numero"] for i in esito["__interrupt__"]] == [1]
    stato = grafo.invoke(Command(resume=True), CONFIG_NOTE)
    assert archivio.leggi(1) is None
    assert archivio.leggi(2) is not None
    assert esiti(stato) == {"a": "Nota 1 eliminata.", "b": "Errore: elimina una nota alla volta."}


def test_aggiunta_senza_pausa(archivio):
    aggiunta = chiamata_strumento(None, nome="aggiungi_nota", args={"testo": "cavi"})
    _, grafo = crea_con_note([aggiunta, AIMessage("salvata")], archivio)
    stato = avvia(grafo, "annota cavi")
    assert "__interrupt__" not in stato
    assert archivio.leggi(1).testo == "cavi"


def test_elimina_senza_archivio_rifiutato():
    archivio = apri_archivio(":memory:")
    try:
        with pytest.raises(ValueError):
            costruisci_grafo(
                ModelloFinto([]), crea_strumenti(AUTUNNO, archivio=archivio), "Europe/Rome", 3
            )
    finally:
        archivio.chiudi()


def test_prompt_di_sistema_cita_le_note():
    testo = prompt_di_sistema("Europe/Rome")
    for nome in ("aggiungi_nota", "cerca_note", "elenca_note", "elimina_nota"):
        assert nome in testo


def test_prompt_di_sistema_impone_le_chiamate_delle_note():
    # Il modello reale rispondeva «Ho annotato» senza chiamare aggiungi_nota e, per eliminare,
    # chiedeva lui la conferma invece di chiamare elimina_nota (conferma doppia).
    testo = prompt_di_sistema("Europe/Rome")
    assert "chiama sempre aggiungi_nota" in testo
    # «Annota che …» e «Prendi nota che …» venivano presi come frasi di conversazione.
    assert "«annota», «prendi nota», «segna», «segnati» e «ricordami»" in testo
    assert "non dire mai di aver salvato una nota senza averlo chiamato" in testo
    assert "chiama subito elimina_nota" in testo
    assert "non chiedere tu la conferma" in testo


@pytest.mark.parametrize("id_ripetuto", ["x", ""])
def test_id_ripetuti_una_sola_eliminazione(archivio, id_ripetuto):
    # Due elimina_nota con lo stesso id: un solo «sì» non deve eliminare anche la seconda nota.
    archivio.aggiungi("prima")
    archivio.aggiungi("seconda")
    doppia = AIMessage(
        content="",
        tool_calls=[
            {"name": "elimina_nota", "args": {"numero": 1}, "id": id_ripetuto, "type": "tool_call"},
            {"name": "elimina_nota", "args": {"numero": 2}, "id": id_ripetuto, "type": "tool_call"},
        ],
    )
    _, grafo = crea_con_note([doppia, AIMessage("fatto")], archivio)
    esito = avvia(grafo)
    assert [i.value["numero"] for i in esito["__interrupt__"]] == [1]
    stato = grafo.invoke(Command(resume=True), CONFIG_NOTE)
    assert archivio.leggi(1) is None
    assert archivio.leggi(2) is not None
    contenuti = [m.content for m in stato["messages"] if isinstance(m, ToolMessage)]
    assert contenuti == ["Nota 1 eliminata.", "Errore: elimina una nota alla volta."]


# --- Router ---

AMBITO = "ora e date"


def decisione(categoria, motivo="motivo"):
    return DecisioneRouter(categoria=categoria, motivo=motivo)


def crea_con_router(decisioni, risposte):
    router = RouterFinto(decisioni)
    modello = ModelloFinto(risposte)
    grafo = costruisci_grafo(
        modello, crea_strumenti(AUTUNNO), "Europe/Rome", 3, router=router, ambito=AMBITO
    )
    return router, modello, grafo


def messaggi_log(caplog):
    return [r.getMessage() for r in caplog.records]


def test_instradamento_dopo_router():
    assert instrada_dopo_router({"categoria": "conversazione"}) == "agente"
    assert instrada_dopo_router({"categoria": "fuori_ambito"}) == "rifiuto"


def test_in_ambito_passa_all_agente(caplog):
    caplog.set_level(logging.INFO)
    _, modello, grafo = crea_con_router(
        [decisione("conversazione", "domanda sull'ora")], [AIMessage("Sono le 17:05.")]
    )
    stato = invoca(grafo, "Che ore sono?")
    assert stato["messages"][-1].content == "Sono le 17:05."
    assert len(modello.chiamate) == 1
    assert stato["categoria"] == "conversazione"
    righe = messaggi_log(caplog)
    instradamento = righe.index("router: categoria=conversazione motivo=domanda sull'ora -> agente")
    assert righe.index("agente: chiamata al modello") > instradamento


def test_fuori_ambito_rifiutato_senza_agente(caplog):
    caplog.set_level(logging.INFO)
    _, modello, grafo = crea_con_router([decisione("fuori_ambito", "ricetta")], [])
    stato = invoca(grafo, "Dammi la ricetta della carbonara")
    assert modello.chiamate == []
    assert stato["messages"][-1].content == messaggio_rifiuto(AMBITO)
    assert stato["categoria"] == "fuori_ambito"
    assert stato["motivo"] == "ricetta"
    righe = messaggi_log(caplog)
    assert "router: categoria=fuori_ambito motivo=ricetta -> rifiuto" in righe
    assert "rifiuto: domanda fuori ambito, agente non eseguito" in righe
    assert not any(r.startswith("agente:") for r in righe)


def test_router_riceve_prompt_e_testo():
    router, _, grafo = crea_con_router([decisione("conversazione")], [AIMessage("Ciao!")])
    invoca(grafo, "Ciao")
    sistema, domanda = router.chiamate[0]
    assert isinstance(sistema, SystemMessage)
    assert AMBITO in sistema.content
    assert domanda.content.endswith("Domanda da classificare: Ciao")


def test_output_non_valido_passa_all_agente(caplog):
    caplog.set_level(logging.INFO)
    _, modello, grafo = crea_con_router([None], [AIMessage("Ciao!")])
    stato = invoca(grafo, "Ciao")
    assert len(modello.chiamate) == 1
    assert stato["messages"][-1].content == "Ciao!"
    avvisi = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert any("output non valido" in a for a in avvisi)


def test_in_ambito_con_strumento():
    router, _, grafo = crea_con_router(
        [decisione("conversazione")],
        [chiamata_strumento("Europe/Rome"), AIMessage("Sono le 17:05.")],
    )
    stato = invoca(grafo, "Che ore sono?")
    assert any(
        isinstance(m, ToolMessage) and m.name == "ora_corrente" for m in stato["messages"]
    )
    assert stato["messages"][-1].content == "Sono le 17:05."
    assert len(router.chiamate) == 1


def test_router_senza_ambito_rifiutato():
    with pytest.raises(ValueError):
        costruisci_grafo(
            ModelloFinto([]), crea_strumenti(AUTUNNO), "Europe/Rome", 3,
            router=RouterFinto([]), ambito="",
        )


def test_limite_ricorsione_basta_nel_caso_peggiore(archivio):
    # Caso peggiore: router davanti e ogni passaggio passa anche da conferma_eliminazione
    # (note inesistenti, quindi nessuna pausa). Deve finire su limite_raggiunto,
    # non con GraphRecursionError.
    max_passaggi = 3
    risposte = [elimina(99, id=f"call_{i}") for i in range(max_passaggi + 1)]
    modello = ModelloFinto(risposte)
    grafo = costruisci_grafo(
        modello, crea_strumenti(AUTUNNO, archivio=archivio), "Europe/Rome", max_passaggi,
        archivio=archivio, router=RouterFinto([decisione("conversazione")]), ambito=AMBITO,
    )
    stato = grafo.invoke(
        {"messages": [HumanMessage("elimina")], "passaggi_strumenti": 0},
        {"recursion_limit": limite_ricorsione(max_passaggi), "configurable": {"thread_id": "t"}},
    )
    assert stato["messages"][-1].content == MESSAGGIO_LIMITE
    assert len(modello.chiamate) == max_passaggi + 1


# Contratto con la libreria: il vero crea_router (ChatOpenAI.with_structured_output con
# json_schema) davanti a risposte malformate del server, simulate con httpx.MockTransport.
# Nessun modello attivo: serve a verificare che il fail-open copra anche i casi in cui la
# libreria solleva un'eccezione invece di restituire parsed=None.

import json

import httpx
import openai
from langchain_openai import ChatOpenAI

from assistente import modello as modulo_modello
from assistente.config import Configurazione


def risposta_del_server(contenuto, finish_reason="stop"):
    def gestore(request):
        corpo = {
            "id": "x", "object": "chat.completion", "created": 0, "model": "m",
            "choices": [{
                "index": 0, "finish_reason": finish_reason,
                "message": {"role": "assistant", "content": contenuto},
            }],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        }
        return httpx.Response(200, json=corpo)

    return gestore


def router_reale(monkeypatch, gestore):
    """Il vero crea_router, con un ChatOpenAI che parla con un server finto."""
    chat = ChatOpenAI(
        base_url="http://server-finto/v1", model="m", api_key="k", max_retries=0,
        http_client=httpx.Client(transport=httpx.MockTransport(gestore)),
    )
    monkeypatch.setattr(modulo_modello, "_chat", lambda config: chat)
    config = Configurazione(
        "http://server-finto/v1", "m", "Europe/Rome", 3, "INFO",
        "http://localhost:8000", "note.sqlite3", AMBITO,
    )
    return modulo_modello.crea_router(config)


@pytest.mark.parametrize(
    "contenuto, finish_reason",
    [
        pytest.param(json.dumps({"categoria": "altro", "motivo": "x"}), "stop", id="fuori_schema"),
        pytest.param('{"categoria": "conv', "stop", id="json_troncato"),
        pytest.param("", "stop", id="vuoto"),
        pytest.param(
            json.dumps({"categoria": "fuori_ambito", "motivo": "x"}), "length", id="troncato_length"
        ),
    ],
)
def test_router_reale_output_non_valido_passa_all_agente(
    monkeypatch, caplog, contenuto, finish_reason
):
    caplog.set_level(logging.INFO)
    router = router_reale(monkeypatch, risposta_del_server(contenuto, finish_reason))
    modello = ModelloFinto([AIMessage("Ciao!")])
    grafo = costruisci_grafo(
        modello, crea_strumenti(AUTUNNO), "Europe/Rome", 3, router=router, ambito=AMBITO
    )
    stato = invoca(grafo, "Ciao")
    assert stato["messages"][-1].content == "Ciao!"
    assert stato["categoria"] == "conversazione"
    avvisi = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert any("output non valido" in a for a in avvisi), avvisi


def test_router_reale_output_valido(monkeypatch):
    router = router_reale(
        monkeypatch, risposta_del_server(json.dumps({"categoria": "fuori_ambito", "motivo": "ricetta"}))
    )
    modello = ModelloFinto([])
    grafo = costruisci_grafo(
        modello, crea_strumenti(AUTUNNO), "Europe/Rome", 3, router=router, ambito=AMBITO
    )
    stato = invoca(grafo, "Dammi la ricetta della carbonara")
    assert stato["categoria"] == "fuori_ambito"
    assert stato["messages"][-1].content == messaggio_rifiuto(AMBITO)
    assert modello.chiamate == []


def test_router_reale_errore_di_connessione_non_e_fail_open(monkeypatch):
    # Solo i guasti di formato sono fail-open: LM Studio irraggiungibile resta un errore.
    def rifiuta(request):
        raise httpx.ConnectError("connessione rifiutata", request=request)

    grafo = costruisci_grafo(
        ModelloFinto([]), crea_strumenti(AUTUNNO), "Europe/Rome", 3,
        router=router_reale(monkeypatch, rifiuta), ambito=AMBITO,
    )
    with pytest.raises(openai.APIConnectionError):
        invoca(grafo, "Ciao")
