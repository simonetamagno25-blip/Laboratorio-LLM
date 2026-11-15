"""Prova reale con LM Studio: richiede il server attivo e l'opzione --lmstudio."""

from uuid import uuid4

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.types import Command

from assistente.config import carica_configurazione
from assistente.grafo import costruisci_grafo, limite_ricorsione
from assistente.modello import crea_modello, crea_revisore, crea_router
from assistente.router import messaggio_rifiuto
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
            router=crea_router(config),
            ambito=config.ambito,
            revisore=crea_revisore(config),
            max_revisioni=config.max_revisioni,
        )
        yield grafo, limite_ricorsione(config.max_passaggi_strumenti, config.max_revisioni)


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


# --- Router ---


def turno(grafo_completo, messaggi):
    """Esegue un turno con il modello reale e stampa la decisione del router e la risposta."""
    grafo, limite = grafo_completo
    stato = grafo.invoke({"messages": messaggi, "passaggi_strumenti": 0}, config_turno(limite))
    print(f"\n{messaggi[-1].content}")
    print(f"   router: {stato.get('categoria')} — {stato.get('motivo')}")
    print(f"-> {stato['messages'][-1].content}")
    return stato


@pytest.mark.lmstudio
def test_router_in_ambito_con_strumento(grafo_completo):
    stato = turno(grafo_completo, [HumanMessage("Che ore sono adesso a Tokyo?")])
    assert stato["categoria"] == "conversazione", stato.get("motivo")
    chiamate = [c for m in stato["messages"] if isinstance(m, AIMessage) for c in m.tool_calls]
    assert any(c["name"] == "ora_corrente" for c in chiamate), stato["messages"]


@pytest.mark.lmstudio
def test_router_fuori_ambito(grafo_completo, caplog):
    import logging

    caplog.set_level(logging.INFO)
    stato = turno(grafo_completo, [HumanMessage("Dammi la ricetta della carbonara")])
    assert stato["categoria"] == "fuori_ambito", stato.get("motivo")
    risposte = [m for m in stato["messages"] if isinstance(m, AIMessage)]
    assert len(risposte) == 1
    assert risposte[0].content == messaggio_rifiuto(carica_configurazione().ambito)
    assert not any(r.getMessage().startswith("agente:") for r in caplog.records)


@pytest.mark.lmstudio
def test_router_tema_del_corso(grafo_completo):
    stato = turno(grafo_completo, [HumanMessage("Che cos'è LangGraph?")])
    assert stato["categoria"] == "conversazione", stato.get("motivo")


@pytest.mark.lmstudio
def test_router_follow_up(grafo_completo):
    primo = turno(grafo_completo, [HumanMessage("Che ore sono adesso a Tokyo?")])
    secondo = turno(grafo_completo, primo["messages"] + [HumanMessage("e a New York?")])
    assert secondo["categoria"] == "conversazione", secondo.get("motivo")


@pytest.mark.lmstudio
def test_router_seguito_fuori_ambito(grafo_completo):
    primo = turno(grafo_completo, [HumanMessage("Dammi la ricetta della carbonara")])
    assert primo["categoria"] == "fuori_ambito", primo.get("motivo")
    secondo = turno(grafo_completo, primo["messages"] + [HumanMessage("e quella dell'amatriciana?")])
    assert secondo["categoria"] == "fuori_ambito", secondo.get("motivo")


# --- Revisore ---


@pytest.mark.lmstudio
def test_revisore_risposta_coerente(grafo_completo, caplog):
    import logging

    caplog.set_level(logging.INFO)
    stato = turno(grafo_completo, [HumanMessage("Che ore sono adesso a Tokyo?")])
    righe = [r.getMessage() for r in caplog.records if r.getMessage().startswith("revisore:")]
    for riga in righe:
        print(f"   {riga}")
    assert stato.get("revisioni", 0) == 0, righe
    assert righe and righe[0].startswith("revisore: coerente=sì"), righe


class PrimaRispostaForzata:
    """Modello reale, ma la prima risposta dell'agente è decisa dal test (parziale)."""

    def __init__(self, modello, risposta: str):
        self._modello = modello
        self._risposta = risposta
        self.chiamate = 0

    def invoke(self, messaggi, config=None):
        self.chiamate += 1
        if self.chiamate == 1:
            return AIMessage(self._risposta)
        return self._modello.invoke(messaggi, config)


@pytest.mark.lmstudio
def test_revisore_risposta_parziale_corretta(caplog):
    import logging

    caplog.set_level(logging.INFO)
    config = carica_configurazione()
    strumenti = crea_strumenti()
    agente = PrimaRispostaForzata(
        crea_modello(config, strumenti), "Adesso a Tokyo sono le 00:49 del 15 novembre."
    )
    grafo = costruisci_grafo(
        agente,
        strumenti,
        config.fuso_predefinito,
        config.max_passaggi_strumenti,
        revisore=crea_revisore(config),
        max_revisioni=config.max_revisioni,
    )
    # «17 * 23» e non «17 per 23»: il modello ha letto «per» come una divisione.
    domanda = "Che ore sono a Tokyo e quanto fa 17 * 23?"
    stato = grafo.invoke(
        {"messages": [HumanMessage(domanda)], "passaggi_strumenti": 0, "revisioni": 0},
        {"recursion_limit": limite_ricorsione(config.max_passaggi_strumenti, config.max_revisioni)},
    )
    righe = [r.getMessage() for r in caplog.records if r.getMessage().startswith("revisore:")]
    print(f"\n{domanda}")
    for riga in righe:
        print(f"   {riga}")
    print(f"-> {stato['messages'][-1].content}")
    # Il revisore reale rifiuta la risposta parziale con un motivo...
    assert righe[0].startswith("revisore: coerente=no"), righe
    assert stato["revisioni"] >= 1
    # ...e l'agente reale completa la risposta con il calcolo. Con la prima risposta forzata
    # (senza strumenti) il modello tende a calcolare a mente: si stampa se ha usato calcola,
    # ma l'evidenza dello step è la risposta completa dopo il rifiuto.
    chiamate = [c for m in stato["messages"] if isinstance(m, AIMessage) for c in m.tool_calls]
    print(f"   strumenti chiamati: {[c['name'] for c in chiamate]}")
    assert "391" in stato["messages"][-1].content, stato["messages"][-1].content


# --- Riassunto ---


@pytest.mark.lmstudio
def test_riassunto_conserva_il_nome(caplog):
    import logging

    from assistente.cli import Sessione
    from assistente.modello import crea_riassuntore

    caplog.set_level(logging.INFO)
    config = carica_configurazione()
    strumenti = crea_strumenti()
    # Soglia bassa per arrivare alla compressione in pochi turni.
    grafo = costruisci_grafo(
        crea_modello(config, strumenti),
        strumenti,
        config.fuso_predefinito,
        config.max_passaggi_strumenti,
        router=crea_router(config),
        ambito=config.ambito,
        revisore=crea_revisore(config),
        max_revisioni=config.max_revisioni,
        riassuntore=crea_riassuntore(config),
        soglia_riassunto=6,
        messaggi_conservati=2,
    )
    sessione = Sessione(
        grafo, limite_ricorsione(config.max_passaggi_strumenti, config.max_revisioni)
    )
    for domanda in ["Ciao, mi chiamo Giulia.", "Quanto fa 12 * 7?", "Che ore sono a Tokyo?"]:
        print(f"\n{domanda}\n-> {sessione.chiedi(domanda)}")
    risposta = sessione.chiedi("Come mi chiamo?")
    righe = [r.getMessage() for r in caplog.records if r.getMessage().startswith("riassunto:")]
    print(f"\nCome mi chiamo?\n-> {risposta}")
    for riga in righe:
        print(f"   {riga}")
    print(f"   riassunto: {sessione.riassunto}")
    assert righe, "nessuna compressione nei log"
    assert not any(m.text == "Ciao, mi chiamo Giulia." for m in sessione.cronologia)
    assert "Giulia" in risposta, risposta


# --- Preferenze (resource MCP) ---


def grafo_con_preferenze(tmp_path, dati):
    import json

    from assistente.client_mcp import ClientMCP, comando_convertitore
    from assistente.preferenze import carica_preferenze, predefinite

    file = tmp_path / "preferenze.json"
    file.write_text(json.dumps(dati), encoding="utf-8")
    config = carica_configurazione()
    with ClientMCP(*comando_convertitore(), ambiente={"PERCORSO_PREFERENZE": str(file)}) as client:
        preferenze = carica_preferenze(client, predefinite(config.fuso_predefinito))
    strumenti = crea_strumenti()
    grafo = costruisci_grafo(
        crea_modello(config, strumenti),
        strumenti,
        config.fuso_predefinito,
        config.max_passaggi_strumenti,
        preferenze=preferenze,
    )
    return grafo, limite_ricorsione(config.max_passaggi_strumenti)


@pytest.mark.lmstudio
def test_preferenze_fuso_predefinito_new_york(tmp_path):
    grafo = grafo_con_preferenze(
        tmp_path, {"lingua": "italiano", "fuso_orario": "America/New_York", "stile": "sintetico"}
    )
    stato = turno(grafo, [HumanMessage("Che ore sono?")])
    chiamate = [c for m in stato["messages"] if isinstance(m, AIMessage) for c in m.tool_calls]
    assert any(
        c["name"] == "ora_corrente" and c["args"].get("fuso_orario") == "America/New_York"
        for c in chiamate
    ), chiamate


@pytest.mark.lmstudio
def test_preferenze_lingua_inglese(tmp_path):
    grafo = grafo_con_preferenze(
        tmp_path, {"lingua": "inglese", "fuso_orario": "Europe/Rome", "stile": "dettagliato"}
    )
    stato = turno(grafo, [HumanMessage("Che ore sono a Tokyo?")])
    risposta = stato["messages"][-1].content.casefold()
    # Lettura a occhio della risposta stampata; qui un controllo grezzo sulla lingua.
    assert any(parola in risposta for parola in (" the ", " is ", "it's", "time")), risposta
    assert "sono le" not in risposta, risposta


# --- Prompt MCP ---


@pytest.fixture(scope="module")
def sessione_con_prompt():
    from assistente.cli import Sessione
    from assistente.client_mcp import ClientMCP, comando_convertitore

    config = carica_configurazione()
    strumenti = crea_strumenti()
    grafo = costruisci_grafo(
        crea_modello(config, strumenti),
        strumenti,
        config.fuso_predefinito,
        config.max_passaggi_strumenti,
        router=crea_router(config),
        ambito=config.ambito,
        revisore=crea_revisore(config),
        max_revisioni=config.max_revisioni,
    )
    with ClientMCP(*comando_convertitore()) as client:
        yield (
            Sessione(grafo, limite_ricorsione(config.max_passaggi_strumenti, config.max_revisioni)),
            client,
        )


@pytest.mark.lmstudio
def test_prompt_spiega_livello_base(sessione_con_prompt, caplog):
    import logging

    from assistente.comandi import in_messaggi, interpreta_comando_prompt, valida

    caplog.set_level(logging.INFO)
    sessione, client = sessione_con_prompt
    riga = '/prompt spiega argomento="Model Context Protocol" livello=base'
    nome, argomenti = interpreta_comando_prompt(riga)
    valida(nome, argomenti, client.elenca_prompt())
    risposta = sessione.chiedi_messaggi(in_messaggi(client.ottieni_prompt(nome, argomenti)))
    righe = [
        r.getMessage() for r in caplog.records
        if r.getMessage().startswith(("prompts/", "router:", "revisore:"))
    ]
    print(f"\n{riga}")
    for riga_log in righe:
        print(f"   {riga_log}")
    print(f"-> {risposta}")
    assert any(r.startswith("router: categoria=conversazione") for r in righe), righe
    assert "protocol" in risposta.casefold(), risposta


@pytest.mark.lmstudio
def test_prompt_riassumi_conversazione(sessione_con_prompt):
    from assistente.comandi import in_messaggi

    sessione, client = sessione_con_prompt
    for domanda in ["Che ore sono a Tokyo?", "Quanto fa 12 * 7?"]:
        print(f"\n{domanda}\n-> {sessione.chiedi(domanda)}")
    messaggi = in_messaggi(client.ottieni_prompt("riassumi_conversazione", {"stile": "sintetico"}))
    risposta = sessione.chiedi_messaggi(messaggi)
    print(f"\n/prompt riassumi_conversazione stile=sintetico\n-> {risposta}")
    assert "Tokyo" in risposta, risposta
    assert "84" in risposta or "12" in risposta, risposta
