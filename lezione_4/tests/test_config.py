import pytest

from assistente.config import ErroreConfigurazione, carica_configurazione

BASE = {"LMSTUDIO_BASE_URL": "http://localhost:1234/v1", "LMSTUDIO_MODEL": "google/gemma-4-e2b"}


def test_valori_predefiniti():
    c = carica_configurazione(BASE)
    assert c.base_url == "http://localhost:1234/v1"
    assert c.modello == "google/gemma-4-e2b"
    assert c.fuso_predefinito == "Europe/Rome"
    assert c.max_passaggi_strumenti == 3
    assert c.log_level == "INFO"


@pytest.mark.parametrize("mancante", ["LMSTUDIO_BASE_URL", "LMSTUDIO_MODEL"])
def test_variabile_obbligatoria_mancante(mancante):
    env = {k: v for k, v in BASE.items() if k != mancante}
    with pytest.raises(ErroreConfigurazione, match=mancante):
        carica_configurazione(env)


def test_variabile_obbligatoria_vuota():
    env = {**BASE, "LMSTUDIO_MODEL": "   "}
    with pytest.raises(ErroreConfigurazione, match="LMSTUDIO_MODEL"):
        carica_configurazione(env)


def test_fuso_predefinito_non_valido():
    env = {**BASE, "FUSO_ORARIO_PREDEFINITO": "Marte/Base"}
    with pytest.raises(ErroreConfigurazione, match="FUSO_ORARIO_PREDEFINITO"):
        carica_configurazione(env)


@pytest.mark.parametrize("valore", ["0", "-1", "tre"])
def test_max_passaggi_non_valido(valore):
    env = {**BASE, "MAX_PASSAGGI_STRUMENTI": valore}
    with pytest.raises(ErroreConfigurazione, match="MAX_PASSAGGI_STRUMENTI"):
        carica_configurazione(env)


def test_valori_ripuliti_e_log_level_maiuscolo():
    env = {**BASE, "LMSTUDIO_MODEL": "  m  ", "LOG_LEVEL": " debug ", "MAX_PASSAGGI_STRUMENTI": " 5 "}
    c = carica_configurazione(env)
    assert c.modello == "m"
    assert c.log_level == "DEBUG"
    assert c.max_passaggi_strumenti == 5


def test_log_level_non_valido():
    env = {**BASE, "LOG_LEVEL": "verbose"}
    with pytest.raises(ErroreConfigurazione, match="LOG_LEVEL"):
        carica_configurazione(env)
