from datetime import datetime, timezone

import pytest

from assistente.catalogo import Articolo
from assistente.strumenti import crea_strumenti, formatta_ora

AUTUNNO = lambda: datetime(2026, 10, 26, 16, 5, 12, tzinfo=timezone.utc)
ESTATE = lambda: datetime(2026, 7, 1, 10, 0, 0, tzinfo=timezone.utc)


def test_ora_solare_roma():
    assert formatta_ora("Europe/Rome", AUTUNNO) == "2026-10-26T17:05:12+01:00 (Europe/Rome)"


def test_ora_legale_roma():
    assert formatta_ora("Europe/Rome", ESTATE) == "2026-07-01T12:00:00+02:00 (Europe/Rome)"


def test_new_york_ancora_in_ora_legale():
    assert formatta_ora("America/New_York", AUTUNNO) == "2026-10-26T12:05:12-04:00 (America/New_York)"


def test_tokyo_giorno_dopo():
    assert formatta_ora("Asia/Tokyo", AUTUNNO) == "2026-10-27T01:05:12+09:00 (Asia/Tokyo)"


@pytest.mark.parametrize("fuso", ["Marte/Base", "", "Europe/../Rome"])
def test_fuso_non_valido(fuso):
    assert formatta_ora(fuso, AUTUNNO) == f"Fuso orario non valido: {fuso!r}"


def test_strumenti_locali_esposti():
    assert [s.name for s in crea_strumenti(AUTUNNO)] == [
        "ora_corrente",
        "calcola",
        "cerca_articoli",
        "dettaglio_articolo",
    ]


def test_strumenti_del_catalogo_esposti():
    _, _, cerca, dettaglio = crea_strumenti(AUTUNNO)
    assert set(cerca.args) == {"testo", "categoria"}
    assert set(dettaglio.args) == {"codice"}
    assert "al singolare" in cerca.description
    assert "cerca_articoli" in dettaglio.description


def test_strumenti_usano_il_catalogo_passato():
    catalogo = (
        Articolo("SEN-001", "Sensore di temperatura", "sensori", "Sonda.", 2, "Banco 3"),
    )
    _, _, cerca, dettaglio = crea_strumenti(AUTUNNO, catalogo=catalogo)
    assert "Articoli trovati: 1" in cerca.invoke({"testo": "temperatura"})
    assert "posizione: Banco 3" in dettaglio.invoke({"codice": "SEN-001"})


def test_calcolatrice_esposta():
    calcolatrice = crea_strumenti(AUTUNNO)[1]
    assert set(calcolatrice.args) == {"espressione"}
    assert calcolatrice.invoke({"espressione": "2 + 2"}) == "2 + 2 = 4"


def test_strumento_esposto():
    s = crea_strumenti(AUTUNNO)[0]
    assert s.name == "ora_corrente"
    assert set(s.args) == {"fuso_orario"}
    assert s.invoke({"fuso_orario": "Europe/Rome"}) == "2026-10-26T17:05:12+01:00 (Europe/Rome)"
