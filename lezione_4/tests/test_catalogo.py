import json

import pytest

from assistente.catalogo import (
    CATEGORIE,
    Articolo,
    ErroreCatalogo,
    MAX_RISULTATI,
    carica_catalogo,
    cerca_articoli,
    dettaglio_articolo,
    valida_catalogo,
)


def articolo(**campi) -> dict:
    base = {
        "codice": "SEN-001",
        "nome": "Sensore di temperatura DS18B20",
        "categoria": "sensori",
        "descrizione": "Sonda digitale impermeabile.",
        "quantita": 3,
        "posizione": "Armadio B, ripiano 2",
    }
    base.update(campi)
    return base


# --- caricamento e validazione ---


def test_file_reale_valido():
    catalogo = carica_catalogo()
    assert 18 <= len(catalogo) <= 25
    assert {a.categoria for a in catalogo} == set(CATEGORIE.values())
    assert any(a.quantita == 0 for a in catalogo)
    per_codice = {a.codice: a for a in catalogo}
    assert "umidità" in per_codice["SEN-004"].nome.casefold()
    assert any("temperatura" in a.nome.casefold() for a in catalogo)
    assert not any(
        "stampant" in (a.nome + a.descrizione).casefold() for a in catalogo
    )


def test_articolo_valido_diventa_articolo():
    assert valida_catalogo([articolo()]) == (
        Articolo(
            codice="SEN-001",
            nome="Sensore di temperatura DS18B20",
            categoria="sensori",
            descrizione="Sonda digitale impermeabile.",
            quantita=3,
            posizione="Armadio B, ripiano 2",
        ),
    )


def senza(campo: str) -> dict:
    dati = articolo()
    del dati[campo]
    return dati


@pytest.mark.parametrize(
    "dati, motivo",
    [
        ({}, "lista"),
        ([], "vuot"),
        (["x"], "articolo 1"),
        ([senza("posizione")], "posizione"),
        ([articolo(prezzo=3)], "prezzo"),
        ([articolo(nome="   ")], "nome"),
        ([articolo(nome=5)], "nome"),
        ([articolo(codice="SEN-04")], "SEN-04"),
        ([articolo(codice="sen-004")], "sen-004"),
        ([articolo(codice="ATT-001")], "ATT-001"),
        ([articolo(categoria="robot")], "robot"),
        ([articolo(quantita=-1)], "quantita"),
        ([articolo(quantita=True)], "quantita"),
        ([articolo(quantita=2.5)], "quantita"),
        ([articolo(), articolo()], "duplicato"),
    ],
)
def test_errori_di_validazione(dati, motivo):
    with pytest.raises(ErroreCatalogo, match=motivo):
        valida_catalogo(dati)


def test_errore_indica_posizione_e_codice():
    with pytest.raises(ErroreCatalogo, match=r"articolo 2 \(SEN-002\)"):
        valida_catalogo([articolo(), articolo(codice="SEN-002", quantita=-1)])


def test_file_mancante(tmp_path):
    with pytest.raises(ErroreCatalogo, match="no.json"):
        carica_catalogo(tmp_path / "no.json")


def test_json_non_valido(tmp_path):
    percorso = tmp_path / "rotto.json"
    percorso.write_text("{", encoding="utf-8")
    with pytest.raises(ErroreCatalogo, match="rotto.json"):
        carica_catalogo(percorso)


def test_file_non_utf8(tmp_path):
    percorso = tmp_path / "ansi.json"
    percorso.write_bytes(json.dumps([articolo(nome="Sensore di umidità")], ensure_ascii=False).encode("cp1252"))
    with pytest.raises(ErroreCatalogo, match="ansi.json.*UTF-8"):
        carica_catalogo(percorso)


def test_file_con_bom(tmp_path):
    percorso = tmp_path / "bom.json"
    percorso.write_text(json.dumps([articolo()]), encoding="utf-8-sig")
    assert carica_catalogo(percorso)[0].codice == "SEN-001"


# --- ricerca e dettaglio ---


def voce(codice, nome, categoria, descrizione="Descrizione.", quantita=1, posizione="Banco 1"):
    return Articolo(codice, nome, categoria, descrizione, quantita, posizione)


@pytest.fixture
def piccolo():
    return (
        voce("CAV-001", "Cavo USB-C", "cavi", "Cavo da 1 m per dati."),
        voce("SCH-001", "Scheda Arduino Uno", "schede", "Microcontrollore."),
        voce(
            "SEN-004",
            "Sensore di temperatura e umidità DHT22",
            "sensori",
            "Misura anche l'umidità relativa.",
            6,
            "Armadio B, ripiano 2",
        ),
        voce("SEN-001", "Sensore di temperatura DS18B20", "sensori", "Sonda impermeabile.", 0),
    )


@pytest.fixture
def grande():
    return tuple(voce(f"SEN-{n:03d}", f"Sensore {n}", "sensori") for n in range(1, 13))


def test_cerca_per_parola(piccolo):
    righe = cerca_articoli(piccolo, "temperatura").splitlines()
    assert righe[0] == "Articoli trovati: 2"
    assert righe[1].startswith("SEN-001") and righe[2].startswith("SEN-004")


def test_cerca_tutte_le_parole_anche_in_campi_diversi(piccolo):
    assert "SEN-001" in cerca_articoli(piccolo, "DS18B20 impermeabile")
    assert cerca_articoli(piccolo, "DS18B20 cavo").startswith("Nessun articolo trovato")


def test_cerca_senza_maiuscole_e_accenti(piccolo):
    assert "SEN-004" in cerca_articoli(piccolo, "UMIDITA")


def test_cerca_con_punteggiatura(piccolo):
    assert cerca_articoli(piccolo, "DHT22?") == cerca_articoli(piccolo, "dht22")
    assert cerca_articoli(piccolo, "Temperatura,") == cerca_articoli(piccolo, "temperatura")


def test_cerca_per_categoria(piccolo):
    righe = cerca_articoli(piccolo, categoria=" Sensori ").splitlines()
    assert righe[0] == "Articoli trovati: 2"
    assert all(riga.startswith("SEN-") for riga in righe[1:])


def test_cerca_testo_e_categoria(piccolo):
    assert cerca_articoli(piccolo, "temperatura", "cavi") == (
        'Nessun articolo trovato per "temperatura" nella categoria "cavi". '
        "Il catalogo non contiene articoli corrispondenti."
    )


def test_esaurito_segnalato(piccolo):
    riga = next(r for r in cerca_articoli(piccolo, "DS18B20").splitlines() if "SEN-001" in r)
    assert riga == "SEN-001 | Sensore di temperatura DS18B20 | quantità: 0 (esaurito)"


def test_riga_di_risultato(piccolo):
    assert "SEN-004 | Sensore di temperatura e umidità DHT22 | quantità: 6" in (
        cerca_articoli(piccolo, "DHT22").splitlines()
    )


def test_nessun_risultato(piccolo):
    assert cerca_articoli(piccolo, "stampante 3D") == (
        'Nessun articolo trovato per "stampante 3D". '
        "Il catalogo non contiene articoli corrispondenti."
    )


def test_categoria_non_valida(piccolo):
    assert cerca_articoli(piccolo, categoria="robot") == (
        'Errore: categoria non valida: "robot". Categorie valide: schede, sensori, '
        "attuatori, cavi, alimentazione, strumenti di misura."
    )


@pytest.mark.parametrize("testo", ["", "   ", "?!"])
def test_testo_e_categoria_vuoti(piccolo, testo):
    assert cerca_articoli(piccolo, testo, "") == (
        "Errore: indica un testo da cercare o una categoria."
    )


def test_troncamento(grande):
    righe = cerca_articoli(grande, categoria="sensori").splitlines()
    assert MAX_RISULTATI == 10
    assert righe[0] == "Articoli trovati: 12"
    assert len([r for r in righe if r.startswith("SEN-")]) == 10
    assert righe[-1] == "Altri 2 articoli non mostrati: restringi la ricerca."


def test_dettaglio(piccolo):
    assert dettaglio_articolo(piccolo, "SEN-004") == "\n".join(
        [
            "codice: SEN-004",
            "nome: Sensore di temperatura e umidità DHT22",
            "categoria: sensori",
            "descrizione: Misura anche l'umidità relativa.",
            "quantità: 6",
            "posizione: Armadio B, ripiano 2",
        ]
    )


def test_dettaglio_esaurito(piccolo):
    assert "quantità: 0 (esaurito)" in dettaglio_articolo(piccolo, "SEN-001").splitlines()


@pytest.mark.parametrize("codice", ["sen-004", " SEN-004 ", "sen 004"])
def test_dettaglio_codice_normalizzato(piccolo, codice):
    assert dettaglio_articolo(piccolo, codice) == dettaglio_articolo(piccolo, "SEN-004")


def test_dettaglio_inesistente(piccolo):
    assert dettaglio_articolo(piccolo, "XYZ-999") == (
        'Codice non trovato: "XYZ-999". Usa cerca_articoli per trovare il codice giusto.'
    )
