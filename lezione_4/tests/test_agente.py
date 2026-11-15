from datetime import datetime, timezone

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from assistente.agente import (
    Agente,
    ConfermaSconosciuta,
    RichiestaConferma,
    Risposta,
    StrumentoUsato,
)
from assistente.grafo import costruisci_grafo, limite_ricorsione
from assistente.note import apri_archivio
from assistente.strumenti import crea_strumenti
from tests.fakes import ModelloFinto, chiamata_strumento

AUTUNNO = lambda: datetime(2026, 10, 26, 16, 5, 12, tzinfo=timezone.utc)


def crea_agente(risposte, archivio=None, riassuntore=None):
    modello = ModelloFinto(risposte)
    grafo = costruisci_grafo(
        modello, crea_strumenti(AUTUNNO, archivio=archivio), "Europe/Rome", 3, archivio=archivio,
        riassuntore=riassuntore, soglia_riassunto=4, messaggi_conservati=1,
    )
    return modello, Agente(grafo, limite_ricorsione(3))


def test_turno_con_strumento_restituisce_risposta_e_strumenti_usati():
    _, agente = crea_agente([chiamata_strumento("Asia/Tokyo"), AIMessage("A Tokyo è l'01:05.")])
    esito = agente.turno([HumanMessage("Che ore sono a Tokyo?")], [], "")
    assert isinstance(esito, Risposta)
    assert esito.testo == "A Tokyo è l'01:05."
    assert esito.strumenti == [
        StrumentoUsato("ora_corrente", {"fuso_orario": "Asia/Tokyo"},
                       "2026-10-27T01:05:12+09:00 (Asia/Tokyo)")
    ]
    assert [type(m) for m in esito.cronologia] == [HumanMessage, AIMessage, ToolMessage, AIMessage]


def test_turno_senza_stato_usa_la_cronologia_ricevuta():
    modello, agente = crea_agente([AIMessage("Ti chiami Giulia.")])
    cronologia = [HumanMessage("Mi chiamo Giulia"), AIMessage("Piacere!")]
    esito = agente.turno([HumanMessage("Come mi chiamo?")], cronologia, "")
    assert [m.content for m in modello.chiamate[0][1:]] == [
        "Mi chiamo Giulia", "Piacere!", "Come mi chiamo?"
    ]
    assert len(esito.cronologia) == 4
    # Gli strumenti dei turni precedenti non contano come usati in questo turno.
    assert esito.strumenti == []


def test_strumenti_dei_turni_precedenti_non_ricontati():
    _, agente = crea_agente([AIMessage("ok")])
    cronologia = [
        HumanMessage("ora?"),
        chiamata_strumento("Europe/Rome", id="vecchia"),
        ToolMessage("17:05", tool_call_id="vecchia", name="ora_corrente"),
        AIMessage("Sono le 17:05."),
    ]
    assert agente.turno([HumanMessage("grazie")], cronologia, "").strumenti == []


def test_il_riassunto_torna_aggiornato():
    riassuntore = ModelloFinto([AIMessage("L'utente si chiama Giulia.")])
    _, agente = crea_agente([AIMessage("Ti chiami Giulia.")], riassuntore=riassuntore)
    cronologia = [HumanMessage("Mi chiamo Giulia"), AIMessage("Piacere!"),
                  HumanMessage("ciao"), AIMessage("ciao!")]
    esito = agente.turno([HumanMessage("Come mi chiamo?")], cronologia, "vecchio")
    assert esito.riassunto == "L'utente si chiama Giulia."
    assert [m.content for m in esito.cronologia] == ["Come mi chiamo?", "Ti chiami Giulia."]


@pytest.fixture
def archivio(tmp_path):
    archivio = apri_archivio(tmp_path / "note.sqlite3", "Europe/Rome", AUTUNNO)
    yield archivio
    archivio.chiudi()


def elimina(numero):
    return chiamata_strumento(None, nome="elimina_nota", args={"numero": numero})


def test_conferma_delle_note(archivio):
    nota = archivio.aggiungi("comprare cavi")
    _, agente = crea_agente([elimina(nota.numero), AIMessage("Eliminata.")], archivio=archivio)
    esito = agente.turno([HumanMessage("elimina la nota sui cavi")], [], "")
    assert isinstance(esito, RichiestaConferma)
    assert "comprare cavi" in esito.domanda
    finale = agente.conferma(esito.id_conferma, True)
    assert finale.testo == "Eliminata."
    assert archivio.leggi(nota.numero) is None
    assert [s.nome for s in finale.strumenti] == ["elimina_nota"]
    # La stessa conferma non si può usare due volte.
    with pytest.raises(ConfermaSconosciuta):
        agente.conferma(esito.id_conferma, True)


def test_conferma_sconosciuta():
    _, agente = crea_agente([])
    with pytest.raises(ConfermaSconosciuta):
        agente.conferma("inesistente", True)


def test_i_checkpoint_dei_turni_conclusi_vengono_eliminati(archivio):
    # Revisione: un thread nuovo per turno faceva crescere senza limite il checkpointer in memoria.
    _, agente = crea_agente([AIMessage("uno"), AIMessage("due")], archivio=archivio)
    agente.turno([HumanMessage("a")], [], "")
    agente.turno([HumanMessage("b")], [], "")
    assert list(agente._grafo.checkpointer.list(None)) == []
