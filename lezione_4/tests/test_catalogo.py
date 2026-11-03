import json

import pytest

from assistente.catalogo import (
    CATEGORIE,
    Articolo,
    ErroreCatalogo,
    carica_catalogo,
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


def test_file_con_bom(tmp_path):
    percorso = tmp_path / "bom.json"
    percorso.write_text(json.dumps([articolo()]), encoding="utf-8-sig")
    assert carica_catalogo(percorso)[0].codice == "SEN-001"
