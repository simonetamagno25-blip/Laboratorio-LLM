from datetime import date

import pytest

from scadenze_api.scadenze import (
    AVVERTENZA,
    ErroreScadenze,
    calcola_scadenza,
    carica_festivita,
    giorni_tra_date,
    leggi_data,
)


def test_giorni_di_calendario():
    risultato = giorni_tra_date("2026-12-20", "2027-01-10")
    assert risultato.startswith("21 giorni ")
    assert risultato.endswith(AVVERTENZA)


def test_giorni_lavorativi_tra_natale_ed_epifania():
    risultato = giorni_tra_date("2026-12-20", "2027-01-10", solo_lavorativi=True)
    assert risultato.startswith("12 giorni lavorativi ")
    assert risultato.endswith(AVVERTENZA)


def test_date_invertite_danno_risultato_negativo():
    assert giorni_tra_date("2026-01-10", "2026-01-01").startswith("-9 giorni ")


def test_stessa_data():
    assert giorni_tra_date("2026-03-01", "2026-03-01").startswith("0 giorni ")


def test_scadenza_lavorativa_salta_natale_e_weekend():
    assert "2026-12-29" in calcola_scadenza("2026-12-23", 3, solo_lavorativi=True)


def test_scadenza_di_calendario_segnala_il_sabato():
    risultato = calcola_scadenza("2026-12-23", 3)
    assert "2026-12-26" in risultato
    assert "sabato" in risultato
    assert risultato.endswith(AVVERTENZA)


def test_scadenza_di_calendario_segnala_la_festivita():
    risultato = calcola_scadenza("2026-10-01", 3)
    assert "2026-10-04" in risultato
    assert "domenica" in risultato
    assert "San Francesco" in risultato


def test_scadenza_zero_giorni():
    assert "2026-05-05" in calcola_scadenza("2026-05-05", 0)


def test_scadenza_di_calendario_senza_limite_di_anno():
    assert "2028-02-29" in calcola_scadenza("2028-02-28", 1)


@pytest.mark.parametrize(
    "testo",
    ["02/11/2026", "2026-2-3", "2026-02-30", "2027-02-29", "", " 2026-01-01", "2026-01-01T10:00"],
)
def test_date_rifiutate(testo):
    with pytest.raises(ErroreScadenze):
        leggi_data(testo)


def test_data_valida():
    assert leggi_data("2028-02-29") == date(2028, 2, 29)


def test_anno_non_coperto_con_lavorativi():
    with pytest.raises(ErroreScadenze) as errore:
        giorni_tra_date("2027-12-20", "2028-01-10", solo_lavorativi=True)
    assert "2026" in str(errore.value) and "2027" in str(errore.value)


def test_scadenza_lavorativa_oltre_gli_anni_coperti():
    with pytest.raises(ErroreScadenze):
        calcola_scadenza("2027-12-20", 30, solo_lavorativi=True)


@pytest.mark.parametrize(
    "chiamata",
    [
        lambda: calcola_scadenza("2026-01-01", -1),
        lambda: calcola_scadenza("2026-01-01", 3651),
        lambda: giorni_tra_date("2026-01-01", "2036-01-02"),
    ],
)
def test_limiti(chiamata):
    with pytest.raises(ErroreScadenze):
        chiamata()


def test_file_festivita():
    festivita = carica_festivita()
    assert set(festivita) == {2026, 2027}
    assert all(len(giorni) == 13 for giorni in festivita.values())
    assert date(2026, 10, 4) in festivita[2026]
    assert festivita[2027][date(2027, 3, 29)] == "Lunedì dell'Angelo"
