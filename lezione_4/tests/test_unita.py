from typing import get_args

import pytest

from convertitore_mcp.unita import GRANDEZZE, Unita, converti, descrivi_conversione


def test_miglia_in_chilometri():
    assert descrivi_conversione(26, "mi", "km") == "26 mi = 41.8429 km"


@pytest.mark.parametrize(
    "valore, da, a, atteso",
    [
        (100, "C", "F", 212),
        (0, "F", "C", -17.7778),
        (0, "K", "C", -273.15),
        (-273.15, "C", "K", 0),
        (1, "d", "h", 24),
        (90, "min", "h", 1.5),
        (1, "lb", "kg", 0.45359237),
        (16, "oz", "lb", 1),
        (1, "in", "cm", 2.54),
        (1, "t", "g", 1_000_000),
        (5, "m", "m", 5),
        (1, "l", "ml", 1000),
    ],
)
def test_conversioni(valore, da, a, atteso):
    assert converti(valore, da, a) == pytest.approx(atteso, abs=1e-4)


def test_grandezze_incompatibili():
    assert (
        descrivi_conversione(5, "kg", "m")
        == "Errore: kg → m: grandezze incompatibili (massa, lunghezza)"
    )


@pytest.mark.parametrize(
    "valore, da, a",
    [
        (1, "furlong", "m"),
        (1, "KG", "g"),
        (1, "m", ""),
        (float("inf"), "m", "km"),
        (float("nan"), "m", "km"),
        (-1, "K", "C"),
        (-300, "C", "K"),
        (-500, "F", "C"),
    ],
)
def test_conversioni_rifiutate(valore, da, a):
    assert descrivi_conversione(valore, da, a).startswith("Errore:")


def test_unita_sconosciuta_elenca_le_ammesse():
    assert "km" in descrivi_conversione(1, "furlong", "m")


def test_ogni_unita_ammessa_ha_una_grandezza():
    assert set(get_args(Unita)) == set(GRANDEZZE)


@pytest.mark.parametrize("valore, da, a", [(1e308, "mi", "mm"), (1e308, "F", "C")])
def test_risultato_non_finito_rifiutato(valore, da, a):
    assert descrivi_conversione(valore, da, a).startswith("Errore:")
