import socket

from assistente.client_api import crea_strumenti_api


def _per_nome(strumenti):
    return {s.name: s for s in strumenti}


def test_strumenti_esposti(servizio_scadenze):
    strumenti = crea_strumenti_api(servizio_scadenze)
    assert [s.name for s in strumenti] == ["giorni_tra_date", "calcola_scadenza"]
    schema = _per_nome(strumenti)["calcola_scadenza"].args
    assert schema["giorni"]["type"] == "integer"
    assert schema["solo_lavorativi"]["type"] == "boolean"


def test_giorni_lavorativi_dal_servizio(servizio_scadenze):
    giorni = _per_nome(crea_strumenti_api(servizio_scadenze))["giorni_tra_date"]
    risultato = giorni.invoke(
        {"inizio": "2026-12-20", "fine": "2027-01-10", "solo_lavorativi": True}
    )
    assert risultato.startswith("12 giorni lavorativi")


def test_scadenza_dal_servizio(servizio_scadenze):
    scadenza = _per_nome(crea_strumenti_api(servizio_scadenze))["calcola_scadenza"]
    assert "2026-12-29" in scadenza.invoke(
        {"inizio": "2026-12-23", "giorni": 3, "solo_lavorativi": True}
    )


def test_errore_del_servizio_riportato(servizio_scadenze):
    giorni = _per_nome(crea_strumenti_api(servizio_scadenze))["giorni_tra_date"]
    risultato = giorni.invoke({"inizio": "02/11/2026", "fine": "2026-12-01"})
    assert risultato.startswith("Errore: ")
    assert "AAAA-MM-GG" in risultato


def test_servizio_non_raggiungibile():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        porta = s.getsockname()[1]
    indirizzo = f"http://127.0.0.1:{porta}"
    giorni = _per_nome(crea_strumenti_api(indirizzo, timeout=2))["giorni_tra_date"]
    risultato = giorni.invoke({"inizio": "2026-01-01", "fine": "2026-01-02"})
    assert risultato == f"Errore: servizio scadenze non raggiungibile su {indirizzo}"
