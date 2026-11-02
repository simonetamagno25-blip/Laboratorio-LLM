import httpx
import pytest

import scadenze_api.servizio as servizio


def test_salute(servizio_scadenze):
    risposta = httpx.get(f"{servizio_scadenze}/salute")
    assert risposta.status_code == 200
    assert risposta.json() == {"stato": "ok"}
    assert risposta.headers["content-type"] == "application/json; charset=utf-8"


def test_giorni_lavorativi(servizio_scadenze):
    risposta = httpx.get(
        f"{servizio_scadenze}/giorni",
        params={"inizio": "2026-12-20", "fine": "2027-01-10", "solo_lavorativi": "true"},
    )
    assert risposta.status_code == 200
    assert risposta.json()["risultato"].startswith("12 giorni lavorativi")


def test_giorni_senza_solo_lavorativi(servizio_scadenze):
    risposta = httpx.get(
        f"{servizio_scadenze}/giorni", params={"inizio": "2026-12-20", "fine": "2027-01-10"}
    )
    assert risposta.json()["risultato"].startswith("21 giorni ")


def test_scadenza(servizio_scadenze):
    risposta = httpx.get(
        f"{servizio_scadenze}/scadenza",
        params={"inizio": "2026-12-23", "giorni": "3", "solo_lavorativi": "true"},
    )
    assert risposta.status_code == 200
    assert "2026-12-29" in risposta.json()["risultato"]


@pytest.mark.parametrize(
    "percorso, query",
    [
        ("/giorni", "inizio=02/11/2026&fine=2026-12-01"),
        ("/scadenza", "inizio=2026-01-01&giorni=tre"),
        ("/scadenza", "inizio=2026-01-01&giorni=-1"),
        ("/giorni", "inizio=2026-01-01&fine=2026-02-01&solo_lavorativi=True"),
        ("/giorni", "inizio=2026-01-01&fine=2026-02-01&solo_lavorativi=si"),
        ("/giorni", "inizio=2026-01-01"),
        ("/giorni", "inizio=2026-01-01&inizio=2026-01-02&fine=2026-02-01"),
        ("/giorni", "inizio=2026-01-01&fine=2026-02-01&extra=1"),
        ("/giorni", "inizio=2027-12-20&fine=2028-01-10&solo_lavorativi=true"),
    ],
)
def test_richieste_non_valide(servizio_scadenze, percorso, query):
    risposta = httpx.get(f"{servizio_scadenze}{percorso}?{query}")
    assert risposta.status_code == 400
    assert risposta.json()["errore"]


def test_percorso_sconosciuto(servizio_scadenze):
    risposta = httpx.get(f"{servizio_scadenze}/altro")
    assert risposta.status_code == 404
    assert "errore" in risposta.json()


def test_metodo_non_consentito(servizio_scadenze):
    risposta = httpx.post(f"{servizio_scadenze}/giorni")
    assert risposta.status_code == 405
    assert "errore" in risposta.json()


def test_errore_interno(servizio_scadenze, monkeypatch):
    def guasto(*args, **kwargs):
        raise RuntimeError("guasto")

    monkeypatch.setattr(servizio, "giorni_tra_date", guasto)
    risposta = httpx.get(
        f"{servizio_scadenze}/giorni", params={"inizio": "2026-01-01", "fine": "2026-01-02"}
    )
    assert risposta.status_code == 500
    assert risposta.json() == {"errore": "errore interno"}
