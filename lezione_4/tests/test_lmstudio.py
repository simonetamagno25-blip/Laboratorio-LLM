"""Prova reale con LM Studio: richiede il server attivo e l'opzione --lmstudio."""

from uuid import uuid4

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.types import Command

from assistente.config import carica_configurazione
from assistente.grafo import costruisci_grafo, limite_ricorsione
from assistente.modello import crea_modello
from assistente.note import apri_archivio
from assistente.strumenti import crea_strumenti


@pytest.mark.lmstudio
def test_il_modello_reale_usa_lo_strumento():
    config = carica_configurazione()
    strumenti = crea_strumenti()
    grafo = costruisci_grafo(
        crea_modello(config, strumenti),
        strumenti,
        config.fuso_predefinito,
        config.max_passaggi_strumenti,
    )

    stato = grafo.invoke(
        {
            "messages": [HumanMessage("Che ore sono adesso a Tokyo?")],
            "passaggi_strumenti": 0,
        },
        {"recursion_limit": limite_ricorsione(config.max_passaggi_strumenti)},
    )
    messaggi = stato["messages"]

    chiamate = [
        c for m in messaggi if isinstance(m, AIMessage) for c in m.tool_calls
    ]
    assert any(c["name"] == "ora_corrente" for c in chiamate), messaggi

    risultati = [m for m in messaggi if isinstance(m, ToolMessage)]
    assert any("(Asia/Tokyo)" in m.content for m in risultati), messaggi

    ultimo = messaggi[-1]
    assert isinstance(ultimo, AIMessage) and not ultimo.tool_calls
    assert ultimo.content.strip(), messaggi


@pytest.fixture(scope="module")
def archivio_prova(tmp_path_factory):
    archivio = apri_archivio(tmp_path_factory.mktemp("note") / "note.sqlite3")
    yield archivio
    archivio.chiudi()


@pytest.fixture(scope="module")
def grafo_completo(servizio_scadenze, archivio_prova):
    import os

    from assistente.client_api import crea_strumenti_api
    from assistente.client_mcp import ClientMCP, comando_convertitore

    os.environ.setdefault("SCADENZE_API_URL", servizio_scadenze)
    config = carica_configurazione()
    with ClientMCP(*comando_convertitore()) as client:
        strumenti = (
            crea_strumenti(archivio=archivio_prova)
            + client.strumenti()
            + crea_strumenti_api(servizio_scadenze)
        )
        grafo = costruisci_grafo(
            crea_modello(config, strumenti),
            strumenti,
            config.fuso_predefinito,
            config.max_passaggi_strumenti,
            archivio=archivio_prova,
        )
        yield grafo, limite_ricorsione(config.max_passaggi_strumenti)


@pytest.mark.lmstudio
@pytest.mark.parametrize(
    "domanda, strumento, atteso",
    [
        ("Quanto fa (12 + 8) * 3 / 4?", "calcola", "= 15"),
        ("Quanti chilometri sono 26 miglia?", "converti_unita", "41.8429 km"),
        (
            "Quanti giorni lavorativi ci sono tra il 2026-12-20 e il 2027-01-10?",
            "giorni_tra_date",
            "12 giorni lavorativi",
        ),
        ("Converti 5 kg in metri.", "converti_unita", "Errore:"),
    ],
)
def test_il_modello_reale_usa_i_nuovi_strumenti(grafo_completo, domanda, strumento, atteso):
    grafo, limite = grafo_completo
    stato = grafo.invoke(
        {"messages": [HumanMessage(domanda)], "passaggi_strumenti": 0},
        config_turno(limite),
    )
    messaggi = stato["messages"]
    risultati = [m for m in messaggi if isinstance(m, ToolMessage) and m.name == strumento]
    assert any(atteso in m.content for m in risultati), messaggi
    print(f"\n{domanda}\n-> {messaggi[-1].content}")


def config_turno(limite):
    return {"recursion_limit": limite, "configurable": {"thread_id": uuid4().hex}}


def chiedi(grafo_completo, domanda):
    """Pone la domanda al modello reale; stampa chiamate e risposta per il giudizio a occhio."""
    grafo, limite = grafo_completo
    stato = grafo.invoke(
        {"messages": [HumanMessage(domanda)], "passaggi_strumenti": 0},
        config_turno(limite),
    )
    messaggi = stato["messages"]
    chiamate = [c for m in messaggi if isinstance(m, AIMessage) for c in m.tool_calls]
    risultati = [m for m in messaggi if isinstance(m, ToolMessage)]
    print(f"\n{domanda}")
    for c in chiamate:
        print(f"   chiamata: {c['name']} {c['args']}")
    print(f"-> {messaggi[-1].content}")
    return chiamate, risultati


def codice_normalizzato(chiamata):
    return "".join(str(chiamata["args"].get("codice", "")).split()).upper()


@pytest.mark.lmstudio
def test_catalogo_ricerca(grafo_completo):
    chiamate, risultati = chiedi(grafo_completo, "Avete sensori di temperatura?")
    assert any(c["name"] == "cerca_articoli" for c in chiamate), chiamate
    assert any(
        m.name == "cerca_articoli" and "Articoli trovati:" in m.content for m in risultati
    ), risultati


@pytest.mark.lmstudio
def test_catalogo_dettaglio(grafo_completo):
    chiamate, _ = chiedi(grafo_completo, "Dimmi tutto su SEN-004")
    assert any(
        c["name"] == "dettaglio_articolo" and codice_normalizzato(c) == "SEN-004" for c in chiamate
    ), chiamate


@pytest.mark.lmstudio
def test_catalogo_ricerca_poi_dettaglio(grafo_completo):
    chiamate, risultati = chiedi(grafo_completo, "Dov'è il sensore di umidità?")
    nomi = [c["name"] for c in chiamate]
    assert "cerca_articoli" in nomi and "dettaglio_articolo" in nomi, chiamate
    assert nomi.index("cerca_articoli") < nomi.index("dettaglio_articolo"), chiamate
    testo_ricerche = "\n".join(m.content for m in risultati if m.name == "cerca_articoli")
    dettagli = [c for c in chiamate if c["name"] == "dettaglio_articolo"]
    assert any(codice_normalizzato(c) in testo_ricerche for c in dettagli), chiamate


@pytest.mark.lmstudio
def test_catalogo_nessun_risultato(grafo_completo):
    chiamate, risultati = chiedi(grafo_completo, "Avete stampanti 3D?")
    assert any(c["name"] == "cerca_articoli" for c in chiamate), chiamate
    assert any(
        m.name == "cerca_articoli" and "Nessun articolo trovato" in m.content for m in risultati
    ), risultati


@pytest.mark.lmstudio
def test_catalogo_codice_inesistente(grafo_completo):
    chiamate, risultati = chiedi(grafo_completo, "Dammi il dettaglio dell'articolo XYZ-999")
    assert any(c["name"] == "dettaglio_articolo" for c in chiamate), chiamate
    assert any(
        m.name == "dettaglio_articolo" and "Codice non trovato" in m.content for m in risultati
    ), risultati


# --- Note personali ---


def chiedi_con_conferma(grafo_completo, domanda, risposta):
    """Come chiedi, ma a ogni pausa per la conferma riprende con la risposta data."""
    grafo, limite = grafo_completo
    config = config_turno(limite)
    pause = []
    stato = grafo.invoke({"messages": [HumanMessage(domanda)], "passaggi_strumenti": 0}, config)
    while stato.get("__interrupt__"):
        pause.append(stato["__interrupt__"][0].value)
        stato = grafo.invoke(Command(resume=risposta), config)
    messaggi = stato["messages"]
    chiamate = [c for m in messaggi if isinstance(m, AIMessage) for c in m.tool_calls]
    print(f"\n{domanda}")
    for c in chiamate:
        print(f"   chiamata: {c['name']} {c['args']}")
    for p in pause:
        print(f"   conferma chiesta: {p} -> {risposta}")
    print(f"-> {messaggi[-1].content}")
    return chiamate, pause


@pytest.fixture
def note_di_prova(archivio_prova):
    for nota in archivio_prova.tutte():
        archivio_prova.elimina(nota.numero)
    sensore = archivio_prova.aggiungi("il sensore SEN-004 va ricalibrato")
    cavi = archivio_prova.aggiungi("comprare cavi USB")
    return sensore.numero, cavi.numero


@pytest.mark.lmstudio
def test_note_aggiunta(grafo_completo, archivio_prova):
    for nota in archivio_prova.tutte():
        archivio_prova.elimina(nota.numero)
    chiamate, _ = chiedi(grafo_completo, "Annota che il saldatore va pulito")
    assert any(c["name"] == "aggiungi_nota" for c in chiamate), chiamate
    assert any("saldatore" in n.testo for n in archivio_prova.tutte()), archivio_prova.tutte()


@pytest.mark.lmstudio
def test_note_ricerca(grafo_completo, note_di_prova):
    chiamate, risultati = chiedi(grafo_completo, "Cosa avevo scritto sul sensore?")
    assert any(c["name"] == "cerca_note" for c in chiamate), chiamate
    assert any(m.name == "cerca_note" and "SEN-004" in m.content for m in risultati), risultati


@pytest.mark.lmstudio
def test_note_elenco(grafo_completo, note_di_prova):
    chiamate, _ = chiedi(grafo_completo, "Quali note ho?")
    assert any(c["name"] == "elenca_note" for c in chiamate), chiamate


@pytest.mark.lmstudio
def test_note_nessun_risultato(grafo_completo, note_di_prova):
    chiamate, risultati = chiedi(grafo_completo, "Cosa avevo scritto sulla stampante?")
    assert any(c["name"] == "cerca_note" for c in chiamate), chiamate
    assert any(
        m.name == "cerca_note" and "Nessuna nota trovata" in m.content for m in risultati
    ), risultati


@pytest.mark.lmstudio
def test_note_eliminazione_confermata(grafo_completo, archivio_prova, note_di_prova):
    sensore, cavi = note_di_prova
    chiamate, pause = chiedi_con_conferma(grafo_completo, "Elimina la nota sul sensore", True)
    assert [p["numero"] for p in pause] == [sensore], (pause, chiamate)
    assert archivio_prova.leggi(sensore) is None
    assert archivio_prova.leggi(cavi) is not None


@pytest.mark.lmstudio
def test_note_eliminazione_annullata(grafo_completo, archivio_prova, note_di_prova):
    sensore, cavi = note_di_prova
    chiamate, pause = chiedi_con_conferma(grafo_completo, "Elimina la nota sul sensore", False)
    assert [p["numero"] for p in pause] == [sensore], (pause, chiamate)
    assert archivio_prova.leggi(sensore) is not None
    assert archivio_prova.leggi(cavi) is not None
