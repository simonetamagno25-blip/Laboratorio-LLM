import pytest

from scadenze_api.__main__ import indirizzo_ascolto


def test_ascolto_predefinito_solo_locale():
    assert indirizzo_ascolto({}) == ("127.0.0.1", 8000)


def test_ascolto_configurato():
    assert indirizzo_ascolto({"SCADENZE_API_HOST": "0.0.0.0", "SCADENZE_API_PORTA": "9000"}) == (
        "0.0.0.0",
        9000,
    )


@pytest.mark.parametrize("porta", ["abc", "70000", "-1"])
def test_porta_non_valida(porta):
    with pytest.raises(ValueError, match="SCADENZE_API_PORTA"):
        indirizzo_ascolto({"SCADENZE_API_PORTA": porta})
