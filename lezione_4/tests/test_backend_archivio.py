"""Test di contratto dell'archivio delle chat: stesse prove per memoria e PostgreSQL."""

import os

import pytest

from backend.archivio import (
    TITOLO_INIZIALE,
    ArchivioMemoria,
    ArchivioPostgres,
    ErroreDatabase,
    StatoAgente,
    titolo_da,
)


def _postgres():
    url = os.environ.get("POSTGRES_TEST_URL", "").strip()
    if not url:
        pytest.skip("POSTGRES_TEST_URL non impostata")
    archivio = ArchivioPostgres(url)
    archivio.prepara(attesa=10)
    with archivio._connetti() as conn:
        conn.execute("TRUNCATE chat, messaggio RESTART IDENTITY")
    return archivio


@pytest.fixture(
    params=[
        pytest.param("memoria"),
        pytest.param("postgres", marks=pytest.mark.postgres),
    ]
)
def archivio(request):
    return ArchivioMemoria() if request.param == "memoria" else _postgres()


STATO = StatoAgente([{"type": "human", "data": {"content": "ciao"}}], "riassunto", None)


def test_crea_ed_elenca(archivio):
    prima = archivio.crea()
    seconda = archivio.crea()
    assert prima.titolo == TITOLO_INIZIALE and prima.ultimo_messaggio is None
    assert {c.id for c in archivio.elenca()} == {prima.id, seconda.id}


def test_scambio_salvato_in_ordine_con_titolo(archivio):
    chat = archivio.crea()
    strumenti = [{"nome": "ora_corrente", "argomenti": {"fuso_orario": "Asia/Tokyo"}, "risultato": "x"}]
    archivio.salva_scambio(
        chat.id, domanda="Che ore sono a Tokyo?", risposta="Sono le 01:05.",
        strumenti=strumenti, stato=STATO,
    )
    archivio.salva_scambio(chat.id, domanda="Grazie", risposta="Prego", strumenti=[], stato=STATO)
    vista, messaggi = archivio.leggi(chat.id)
    assert vista.titolo == "Che ore sono a Tokyo?"
    assert [(m.ruolo, m.testo) for m in messaggi] == [
        ("utente", "Che ore sono a Tokyo?"),
        ("assistente", "Sono le 01:05."),
        ("utente", "Grazie"),
        ("assistente", "Prego"),
    ]
    assert messaggi[1].strumenti == strumenti
    assert vista.ultimo_messaggio is not None
    assert archivio.stato_agente(chat.id) == STATO


def test_elenco_dal_piu_recente(archivio):
    vecchia = archivio.crea()
    nuova = archivio.crea()
    archivio.salva_scambio(vecchia.id, domanda="a", risposta="b", strumenti=[], stato=STATO)
    assert archivio.elenca()[0].id == vecchia.id
    archivio.salva_scambio(nuova.id, domanda="c", risposta="d", strumenti=[], stato=STATO)
    assert archivio.elenca()[0].id == nuova.id


def test_conferma_in_attesa(archivio):
    chat = archivio.crea()
    archivio.salva_scambio(
        chat.id, domanda="elimina la nota", risposta=None, strumenti=[],
        stato=StatoAgente([], "", "id-123"),
    )
    assert archivio.stato_agente(chat.id).id_conferma == "id-123"
    assert [m.ruolo for m in archivio.leggi(chat.id)[1]] == ["utente"]


def test_elimina_chat_e_messaggi(archivio):
    chat = archivio.crea()
    archivio.salva_scambio(chat.id, domanda="a", risposta="b", strumenti=[], stato=STATO)
    assert archivio.elimina(chat.id) is True
    assert archivio.leggi(chat.id) is None
    assert archivio.stato_agente(chat.id) is None
    assert archivio.elimina(chat.id) is False


def test_chat_inesistente(archivio):
    assert archivio.leggi(999) is None
    assert archivio.stato_agente(999) is None


@pytest.mark.postgres
def test_postgres_chat_presenti_dopo_il_riavvio():
    archivio = _postgres()
    chat = archivio.crea()
    archivio.salva_scambio(chat.id, domanda="Mi chiamo Giulia", risposta="Piacere!",
                           strumenti=[], stato=STATO)
    # «Riavvio»: un archivio nuovo, nuove connessioni, schema già presente.
    nuovo = ArchivioPostgres(os.environ["POSTGRES_TEST_URL"])
    nuovo.prepara(attesa=5)
    vista, messaggi = nuovo.leggi(chat.id)
    assert vista.titolo == "Mi chiamo Giulia"
    assert [m.testo for m in messaggi] == ["Mi chiamo Giulia", "Piacere!"]


def test_postgres_non_raggiungibile():
    archivio = ArchivioPostgres("postgresql://x:y@127.0.0.1:1/nessuno")
    with pytest.raises(ErroreDatabase):
        archivio.prepara(attesa=0)


@pytest.mark.parametrize(
    "domanda, titolo",
    [
        ("  Che   ore sono? ", "Che ore sono?"),
        ("parola " * 20, ("parola " * 8).strip() + "…"),
    ],
)
def test_titolo_da(domanda, titolo):
    assert titolo_da(domanda) == titolo


def test_domanda_di_conferma_salvata(archivio):
    chat = archivio.crea()
    archivio.salva_scambio(
        chat.id, domanda="elimina la nota", risposta=None, strumenti=[],
        stato=StatoAgente([], "", "id-1", "Eliminare la nota 1?"),
    )
    assert archivio.stato_agente(chat.id).domanda_conferma == "Eliminare la nota 1?"
