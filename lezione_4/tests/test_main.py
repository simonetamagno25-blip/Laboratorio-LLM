import sys

import pytest

import assistente.__main__ as punto_di_ingresso
from assistente.catalogo import ErroreCatalogo

ENV = {
    "LMSTUDIO_BASE_URL": "http://localhost:1234/v1",
    "LMSTUDIO_MODEL": "m",
    "SCADENZE_API_URL": "http://localhost:8000",
}


@pytest.fixture(autouse=True)
def archivio_temporaneo(monkeypatch, tmp_path):
    # Nessun test deve creare note.sqlite3 nella cartella del progetto.
    monkeypatch.setenv("PERCORSO_DB_NOTE", str(tmp_path / "note.sqlite3"))


def test_server_mcp_che_non_parte_blocca_l_avvio(monkeypatch, capsys):
    for nome, valore in ENV.items():
        monkeypatch.setenv(nome, valore)
    monkeypatch.setattr(
        punto_di_ingresso,
        "comando_convertitore",
        lambda: (sys.executable, ["-c", "import sys; sys.exit(1)"]),
    )
    assert punto_di_ingresso.main() == 3
    assert "Server MCP del convertitore non avviato" in capsys.readouterr().err


def test_avvio_con_tutti_gli_strumenti(monkeypatch, capsys):
    for nome, valore in ENV.items():
        monkeypatch.setenv(nome, valore)
    nomi = []

    def ciclo_finto(sessione, base_url):
        nomi.extend(sessione.nomi_strumenti)

    class SessioneFinta:
        def __init__(self, grafo, limite):
            pass

    def crea_modello_finto(config, strumenti):
        SessioneFinta.nomi_strumenti = [s.name for s in strumenti]
        return object()

    monkeypatch.setattr(punto_di_ingresso, "crea_modello", crea_modello_finto)
    monkeypatch.setattr(punto_di_ingresso, "Sessione", SessioneFinta)
    monkeypatch.setattr(punto_di_ingresso, "esegui_ciclo", ciclo_finto)
    assert punto_di_ingresso.main() == 0
    assert nomi == [
        "ora_corrente",
        "calcola",
        "cerca_articoli",
        "dettaglio_articolo",
        "aggiungi_nota",
        "elenca_note",
        "cerca_note",
        "elimina_nota",
        "converti_unita",
        "giorni_tra_date",
        "calcola_scadenza",
    ]


def test_catalogo_non_valido_blocca_l_avvio(monkeypatch, capsys):
    for nome, valore in ENV.items():
        monkeypatch.setenv(nome, valore)
    avviato = []

    def catalogo_rotto():
        raise ErroreCatalogo("articolo 3: codice duplicato")

    monkeypatch.setattr(punto_di_ingresso, "carica_catalogo", catalogo_rotto)
    monkeypatch.setattr(punto_di_ingresso.ClientMCP, "avvia", lambda self: avviato.append(True))
    assert punto_di_ingresso.main() == 4
    assert "Catalogo non valido: articolo 3" in capsys.readouterr().err
    assert not avviato


def test_ctrl_c_durante_l_avvio_del_server_mcp(monkeypatch):
    for nome, valore in ENV.items():
        monkeypatch.setenv(nome, valore)
    chiuso = []

    def interrotto(self):
        raise KeyboardInterrupt

    monkeypatch.setattr(punto_di_ingresso.ClientMCP, "avvia", interrotto)
    monkeypatch.setattr(punto_di_ingresso.ClientMCP, "chiudi", lambda self: chiuso.append(True))
    assert punto_di_ingresso.main() == 130
    assert chiuso


def test_archivio_non_disponibile_blocca_l_avvio(monkeypatch, capsys, tmp_path):
    for nome, valore in ENV.items():
        monkeypatch.setenv(nome, valore)
    (tmp_path / "file").write_text("x")
    monkeypatch.setenv("PERCORSO_DB_NOTE", str(tmp_path / "file" / "note.sqlite3"))
    avviato = []
    monkeypatch.setattr(punto_di_ingresso.ClientMCP, "avvia", lambda self: avviato.append(True))
    assert punto_di_ingresso.main() == 5
    assert "Archivio note non disponibile:" in capsys.readouterr().err
    assert not avviato


def test_archivio_chiuso_se_mcp_non_parte(monkeypatch):
    from assistente.note import ArchivioNote

    for nome, valore in ENV.items():
        monkeypatch.setenv(nome, valore)
    chiuso = []
    originale = ArchivioNote.chiudi

    def registra(self):
        chiuso.append(True)
        originale(self)

    monkeypatch.setattr(ArchivioNote, "chiudi", registra)
    monkeypatch.setattr(
        punto_di_ingresso,
        "comando_convertitore",
        lambda: (sys.executable, ["-c", "import sys; sys.exit(1)"]),
    )
    assert punto_di_ingresso.main() == 3
    assert chiuso


def test_archivio_chiuso_a_fine_sessione(monkeypatch):
    from assistente.note import ArchivioNote

    for nome, valore in ENV.items():
        monkeypatch.setenv(nome, valore)
    chiuso = []
    originale = ArchivioNote.chiudi

    def registra(self):
        chiuso.append(True)
        originale(self)

    monkeypatch.setattr(ArchivioNote, "chiudi", registra)
    monkeypatch.setattr(punto_di_ingresso, "crea_modello", lambda config, strumenti: object())
    monkeypatch.setattr(punto_di_ingresso, "esegui_ciclo", lambda sessione, base_url: None)
    assert punto_di_ingresso.main() == 0
    assert chiuso
