import pytest

from assistente.config import ErroreConfigurazione, carica_configurazione

BASE = {
    "LMSTUDIO_BASE_URL": "http://localhost:1234/v1",
    "LMSTUDIO_MODEL": "google/gemma-4-e2b",
    "SCADENZE_API_URL": "http://localhost:8000",
    "AMBITO_AGENTE": "ora e date",
}


def test_valori_predefiniti():
    c = carica_configurazione(BASE)
    assert c.base_url == "http://localhost:1234/v1"
    assert c.modello == "google/gemma-4-e2b"
    assert c.fuso_predefinito == "Europe/Rome"
    assert c.max_passaggi_strumenti == 3
    assert c.log_level == "INFO"
    assert c.ambito == "ora e date"


@pytest.mark.parametrize(
    "mancante", ["LMSTUDIO_BASE_URL", "LMSTUDIO_MODEL", "SCADENZE_API_URL", "AMBITO_AGENTE"]
)
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


def test_indirizzo_api_scadenze_senza_barra_finale():
    c = carica_configurazione({**BASE, "SCADENZE_API_URL": " http://scadenze:8000/ "})
    assert c.scadenze_api_url == "http://scadenze:8000"


@pytest.mark.parametrize("valore", ["ftp://x", "localhost:8000", "http://"])
def test_indirizzo_api_scadenze_non_valido(valore):
    with pytest.raises(ErroreConfigurazione, match="SCADENZE_API_URL"):
        carica_configurazione({**BASE, "SCADENZE_API_URL": valore})


@pytest.mark.parametrize("valore", [None, "", "   "])
def test_percorso_note_predefinito(valore):
    env = dict(BASE) if valore is None else {**BASE, "PERCORSO_DB_NOTE": valore}
    assert carica_configurazione(env).percorso_db_note == "note.sqlite3"


def test_percorso_note_personalizzato():
    env = {**BASE, "PERCORSO_DB_NOTE": " C:/x/n.sqlite3 "}
    assert carica_configurazione(env).percorso_db_note == "C:/x/n.sqlite3"


def test_ambito_vuoto():
    with pytest.raises(ErroreConfigurazione, match="AMBITO_AGENTE"):
        carica_configurazione({**BASE, "AMBITO_AGENTE": "  "})


def test_max_revisioni_predefinito():
    assert carica_configurazione(BASE).max_revisioni == 2


def test_max_revisioni_letto():
    assert carica_configurazione({**BASE, "MAX_REVISIONI": " 1 "}).max_revisioni == 1


@pytest.mark.parametrize("valore", ["0", "-1", "abc", "1.5"])
def test_max_revisioni_non_valido(valore):
    with pytest.raises(ErroreConfigurazione, match="MAX_REVISIONI"):
        carica_configurazione({**BASE, "MAX_REVISIONI": valore})


def test_riassunto_predefinito():
    c = carica_configurazione(BASE)
    assert (c.soglia_riassunto, c.messaggi_conservati) == (20, 6)


def test_riassunto_letto():
    c = carica_configurazione({**BASE, "SOGLIA_RIASSUNTO": "10", "MESSAGGI_CONSERVATI": " 4 "})
    assert (c.soglia_riassunto, c.messaggi_conservati) == (10, 4)


@pytest.mark.parametrize("nome", ["SOGLIA_RIASSUNTO", "MESSAGGI_CONSERVATI"])
@pytest.mark.parametrize("valore", ["0", "-2", "venti"])
def test_riassunto_non_valido(nome, valore):
    with pytest.raises(ErroreConfigurazione, match=nome):
        carica_configurazione({**BASE, nome: valore})


@pytest.mark.parametrize("conservati", ["8", "9"])
def test_messaggi_conservati_minori_della_soglia(conservati):
    env = {**BASE, "SOGLIA_RIASSUNTO": "8", "MESSAGGI_CONSERVATI": conservati}
    with pytest.raises(ErroreConfigurazione, match="MESSAGGI_CONSERVATI"):
        carica_configurazione(env)


def test_percorso_preferenze():
    assert carica_configurazione(BASE).percorso_preferenze == "preferenze.json"
    env = {**BASE, "PERCORSO_PREFERENZE": " C:/x/pref.json "}
    assert carica_configurazione(env).percorso_preferenze == "C:/x/pref.json"
