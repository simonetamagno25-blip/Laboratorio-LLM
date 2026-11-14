import json
import logging

import pytest

from assistente.client_mcp import ErroreMCP
from assistente.preferenze import (
    Preferenze,
    blocco_preferenze,
    carica_preferenze,
    interpreta,
    predefinite,
)

PREDEFINITE = predefinite("Europe/Rome")


def avvisi(caplog):
    return [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]


def test_predefinite():
    assert PREDEFINITE == Preferenze(lingua="italiano", fuso_orario="Europe/Rome", stile="sintetico")


def test_interpreta_valori_validi():
    testo = json.dumps(
        {"lingua": " inglese ", "fuso_orario": "America/New_York", "stile": "Dettagliato"}
    )
    assert interpreta(testo, PREDEFINITE) == Preferenze("inglese", "America/New_York", "dettagliato")


@pytest.mark.parametrize(
    "campo, valore",
    [("fuso_orario", "Marte/Base"), ("stile", "poetico"), ("lingua", "  "), ("lingua", 3)],
)
def test_interpreta_campo_non_valido_usa_il_predefinito(caplog, campo, valore):
    dati = {"lingua": "inglese", "fuso_orario": "America/New_York", "stile": "dettagliato"}
    dati[campo] = valore
    risultato = interpreta(json.dumps(dati), PREDEFINITE)
    assert getattr(risultato, campo) == getattr(PREDEFINITE, campo)
    # Gli altri campi restano quelli del file.
    altri = {k: v for k, v in dati.items() if k != campo}
    for k in altri:
        assert getattr(risultato, k) != getattr(PREDEFINITE, k)
    assert any(a.startswith(f"preferenze: {campo} non valido") for a in avvisi(caplog))


def test_interpreta_campo_mancante(caplog):
    risultato = interpreta(json.dumps({"lingua": "inglese"}), PREDEFINITE)
    assert risultato == Preferenze("inglese", "Europe/Rome", "sintetico")
    assert any(a.startswith("preferenze: fuso_orario mancante") for a in avvisi(caplog))


@pytest.mark.parametrize("testo", ["non json", "[1, 2]"])
def test_interpreta_json_non_valido(caplog, testo):
    assert interpreta(testo, PREDEFINITE) == PREDEFINITE
    assert any(a.startswith("preferenze: contenuto non valido") for a in avvisi(caplog))


class ClientFinto:
    def __init__(self, esito):
        self._esito = esito
        self.letture = []

    def leggi_risorsa(self, uri):
        self.letture.append(uri)
        if isinstance(self._esito, Exception):
            raise self._esito
        return self._esito


def test_carica_preferenze_dalla_resource(caplog):
    caplog.set_level(logging.INFO)
    client = ClientFinto(json.dumps({"lingua": "inglese", "fuso_orario": "Asia/Tokyo", "stile": "sintetico"}))
    assert carica_preferenze(client, PREDEFINITE).fuso_orario == "Asia/Tokyo"
    assert client.letture == ["utente://preferenze"]
    assert "preferenze: lingua=inglese fuso_orario=Asia/Tokyo stile=sintetico" in [
        r.getMessage() for r in caplog.records
    ]


def test_carica_preferenze_resource_non_disponibile(caplog):
    client = ClientFinto(ErroreMCP("file mancante"))
    assert carica_preferenze(client, PREDEFINITE) == PREDEFINITE
    assert any(
        a.startswith("preferenze: resource utente://preferenze non disponibile (file mancante)")
        for a in avvisi(caplog)
    )


def test_blocco_preferenze():
    testo = blocco_preferenze(Preferenze("inglese", "America/New_York", "dettagliato"))
    assert testo.startswith("Preferenze dell'utente")
    assert "inglese" in testo
    assert "America/New_York" in testo
    assert "dettagliat" in testo
