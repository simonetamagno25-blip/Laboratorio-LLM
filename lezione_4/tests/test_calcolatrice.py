from pathlib import Path

import pytest

from assistente.calcolatrice import calcola


@pytest.mark.parametrize(
    "espressione, atteso",
    [
        ("(12 + 8) * 3 / 4", "(12 + 8) * 3 / 4 = 15"),
        ("2 ** 10", "2 ** 10 = 1024"),
        ("-3 + +2", "-3 + +2 = -1"),
        ("7 % 3", "7 % 3 = 1"),
        ("0.1 + 0.2", "0.1 + 0.2 = 0.3"),
        ("2 ** -1", "2 ** -1 = 0.5"),
    ],
)
def test_espressioni_valide(espressione, atteso):
    assert calcola(espressione) == atteso


def test_divisione_periodica():
    assert calcola("1 / 3").startswith("1 / 3 = 0.333333")


@pytest.mark.parametrize(
    "espressione",
    [
        "__import__('os')",
        "abs(-1)",
        "x + 1",
        "(1).real",
        "[1][0]",
        "'a' * 3",
        "1 < 2",
        "1 & 3",
        "1 +",
        "",
        "1 / 0",
        "5 % 0",
        "True + 1",
        "2 ** 101",
        "10 ** 10 ** 10",
        "1e309",
        "9.9e99 * 10",
        "-(2 ** 100) ** 4",
        "1" + "+1" * 150,
    ],
)
def test_input_rifiutati(espressione):
    assert calcola(espressione).startswith("Errore:")


def test_motivo_divisione_per_zero():
    assert calcola("1 / 0") == "Errore: divisione per zero"


def test_motivo_operazione_non_consentita():
    assert "non consentit" in calcola("abs(-1)")


def test_motivo_espressione_troppo_lunga():
    assert "troppo lunga" in calcola("1" + "+1" * 150)


def test_radice_di_negativo_non_reale():
    assert calcola("(-8) ** 0.5") == "Errore: risultato non reale"


def test_nessun_eval_nel_sorgente():
    sorgente = (Path(__file__).parent.parent / "assistente" / "calcolatrice.py").read_text(
        encoding="utf-8"
    )
    for vietato in ("eval(", "exec(", "compile("):
        assert vietato not in sorgente
