from datetime import datetime, timezone

import pytest

from assistente.note import (
    ErroreArchivio,
    aggiungi_nota,
    apri_archivio,
    cerca_note,
    elenca_note,
    elimina_nota,
    formatta_nota,
)

AUTUNNO = lambda: datetime(2026, 10, 26, 16, 5, 12, tzinfo=timezone.utc)


@pytest.fixture
def archivio(tmp_path):
    archivio = apri_archivio(tmp_path / "note.sqlite3", "Europe/Rome", AUTUNNO)
    yield archivio
    archivio.chiudi()


def test_aggiunta_e_numero(archivio):
    esito = aggiungi_nota(archivio, "  il sensore SEN-004 va ricalibrato  ")
    assert esito == "Nota 1 salvata: il sensore SEN-004 va ricalibrato"
    assert (
        formatta_nota(archivio.leggi(1))
        == "Nota 1 (2026-10-26 17:05): il sensore SEN-004 va ricalibrato"
    )


def test_data_salvata_con_fuso(archivio):
    aggiungi_nota(archivio, "x")
    assert archivio.leggi(1).creata.isoformat() == "2026-10-26T17:05:12+01:00"


def test_testo_vuoto(archivio):
    assert aggiungi_nota(archivio, "   ") == "Errore: il testo della nota è vuoto."
    assert archivio.tutte() == []


def test_limite_di_lunghezza(archivio):
    assert aggiungi_nota(archivio, " " + "a" * 500 + " ").startswith("Nota 1 salvata")
    assert aggiungi_nota(archivio, "a" * 501) == "Errore: la nota supera i 500 caratteri."
    assert len(archivio.tutte()) == 1


def test_testo_con_sql_e_a_capo(archivio):
    testo = "riga 1\nl'apice \"doppio\" '; DROP TABLE note; --"
    aggiungi_nota(archivio, testo)
    assert archivio.leggi(1).testo == testo
    assert len(archivio.tutte()) == 1


def test_elenco_vuoto(archivio):
    assert elenca_note(archivio) == "Non ci sono note salvate."


def test_elenco(archivio):
    aggiungi_nota(archivio, "prima")
    aggiungi_nota(archivio, "seconda")
    assert elenca_note(archivio) == (
        "Note salvate: 2\n"
        "Nota 1 (2026-10-26 17:05): prima\n"
        "Nota 2 (2026-10-26 17:05): seconda"
    )


def test_elenco_oltre_20(archivio):
    for i in range(1, 24):
        aggiungi_nota(archivio, f"nota numero {i}")
    righe = elenca_note(archivio).splitlines()
    assert righe[0] == "Note salvate: 23"
    assert righe[1].startswith("Nota 4 ")
    assert righe[20].startswith("Nota 23 ")
    assert righe[-1] == "Altre 3 note non mostrate: usa cerca_note con parole più precise."
    assert len(righe) == 22


def test_ricerca(archivio):
    aggiungi_nota(archivio, "Il sensore di umidità va ricalibrato")
    aggiungi_nota(archivio, "Comprare cavi USB")
    trovate = cerca_note(archivio, "UMIDITA sensore")
    assert trovate.startswith("Note trovate: 1\n")
    assert "Nota 1 " in trovate
    assert "Nota 2" not in cerca_note(archivio, "sensore")


def test_ricerca_senza_risultati(archivio):
    aggiungi_nota(archivio, "Comprare cavi USB")
    assert (
        cerca_note(archivio, "stampante")
        == 'Nessuna nota trovata per "stampante". Non ci sono note corrispondenti.'
    )


def test_ricerca_senza_parole(archivio):
    assert cerca_note(archivio, " ?! ") == (
        "Errore: indica una o più parole da cercare; per vedere tutte le note usa elenca_note."
    )


def test_ricerca_oltre_20(archivio):
    for i in range(1, 23):
        aggiungi_nota(archivio, f"cavo {i}")
    righe = cerca_note(archivio, "cavo").splitlines()
    assert righe[0] == "Note trovate: 22"
    assert righe[1].startswith("Nota 3 ")
    assert righe[-1] == "Altre 2 note non mostrate: usa cerca_note con parole più precise."


def test_eliminazione_e_numero_non_riusato(archivio):
    aggiungi_nota(archivio, "a")
    aggiungi_nota(archivio, "b")
    assert elimina_nota(archivio, 2) == "Nota 2 eliminata."
    assert elimina_nota(archivio, 2) == (
        "Nota 2 non trovata. Usa cerca_note o elenca_note per trovare il numero giusto."
    )
    assert aggiungi_nota(archivio, "c") == "Nota 3 salvata: c"


def test_persistenza_tra_aperture(tmp_path):
    percorso = tmp_path / "note.sqlite3"
    primo = apri_archivio(percorso, "Europe/Rome", AUTUNNO)
    aggiungi_nota(primo, "da ritrovare")
    primo.chiudi()

    secondo = apri_archivio(percorso, "Europe/Rome", AUTUNNO)
    try:
        nota = secondo.leggi(1)
        assert nota.testo == "da ritrovare"
        assert nota.creata.isoformat() == "2026-10-26T17:05:12+01:00"
    finally:
        secondo.chiudi()


def test_file_non_database(tmp_path):
    percorso = tmp_path / "x.sqlite3"
    percorso.write_bytes(b"non sono un database" * 100)
    with pytest.raises(ErroreArchivio):
        apri_archivio(percorso)


def test_cartella_non_creabile(tmp_path):
    (tmp_path / "file").write_text("x")
    with pytest.raises(ErroreArchivio):
        apri_archivio(tmp_path / "file" / "note.sqlite3")


def test_cartella_creata_se_manca(tmp_path):
    apri_archivio(tmp_path / "nuova" / "note.sqlite3").chiudi()
    assert (tmp_path / "nuova" / "note.sqlite3").exists()


def test_archivio_in_memoria():
    archivio = apri_archivio(":memory:")
    try:
        assert aggiungi_nota(archivio, "x") == "Nota 1 salvata: x"
    finally:
        archivio.chiudi()


def test_file_in_sola_lettura(tmp_path):
    import os
    import stat

    percorso = tmp_path / "note.sqlite3"
    apri_archivio(percorso).chiudi()
    os.chmod(percorso, stat.S_IREAD)
    try:
        with pytest.raises(ErroreArchivio):
            apri_archivio(percorso)
    finally:
        os.chmod(percorso, stat.S_IREAD | stat.S_IWRITE)
