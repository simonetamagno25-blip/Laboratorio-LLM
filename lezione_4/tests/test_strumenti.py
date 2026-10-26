from datetime import datetime, timezone

import pytest

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


def test_strumento_esposto():
    [s] = crea_strumenti(AUTUNNO)
    assert s.name == "ora_corrente"
    assert set(s.args) == {"fuso_orario"}
    assert s.invoke({"fuso_orario": "Europe/Rome"}) == "2026-10-26T17:05:12+01:00 (Europe/Rome)"
