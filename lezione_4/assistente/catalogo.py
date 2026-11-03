"""Catalogo del materiale del laboratorio: dati da un file JSON, sola lettura."""

import json
import re
import unicodedata
from dataclasses import dataclass, fields
from pathlib import Path

FILE_CATALOGO = Path(__file__).parent / "dati" / "catalogo.json"
MAX_RISULTATI = 10

CATEGORIE: dict[str, str] = {
    "SCH": "schede",
    "SEN": "sensori",
    "ATT": "attuatori",
    "CAV": "cavi",
    "ALI": "alimentazione",
    "MIS": "strumenti di misura",
}


class ErroreCatalogo(ValueError):
    """Il file del catalogo manca o non rispetta il formato atteso."""


@dataclass(frozen=True)
class Articolo:
    codice: str
    nome: str
    categoria: str
    descrizione: str
    quantita: int
    posizione: str


Catalogo = tuple[Articolo, ...]

_CAMPI = {campo.name for campo in fields(Articolo)}
_CAMPI_TESTO = ("codice", "nome", "categoria", "descrizione", "posizione")
_FORMATO_CODICE = re.compile(r"[A-Z]{3}-\d{3}")


def _valida_articolo(dati: object, numero: int) -> Articolo:
    if not isinstance(dati, dict):
        raise ErroreCatalogo(f"articolo {numero}: deve essere un oggetto JSON")
    codice = dati.get("codice")
    etichetta = f"articolo {numero}" + (f" ({codice})" if isinstance(codice, str) else "")

    mancanti = sorted(_CAMPI - dati.keys())
    if mancanti:
        raise ErroreCatalogo(f"{etichetta}: campi mancanti: {', '.join(mancanti)}")
    in_piu = sorted(dati.keys() - _CAMPI)
    if in_piu:
        raise ErroreCatalogo(f"{etichetta}: campi non previsti: {', '.join(in_piu)}")

    for campo in _CAMPI_TESTO:
        valore = dati[campo]
        if not isinstance(valore, str) or not valore.strip():
            raise ErroreCatalogo(f"{etichetta}: il campo {campo} deve essere un testo non vuoto")

    if not _FORMATO_CODICE.fullmatch(codice):
        raise ErroreCatalogo(f"{etichetta}: codice {codice!r} non nel formato AAA-000")
    if dati["categoria"] not in CATEGORIE.values():
        valide = ", ".join(CATEGORIE.values())
        raise ErroreCatalogo(
            f"{etichetta}: categoria {dati['categoria']!r} non valida (valide: {valide})"
        )
    atteso = CATEGORIE.get(codice[:3])
    if atteso != dati["categoria"]:
        raise ErroreCatalogo(
            f"{etichetta}: il prefisso del codice {codice} non corrisponde "
            f"alla categoria {dati['categoria']!r}"
        )

    quantita = dati["quantita"]
    if type(quantita) is not int or quantita < 0:
        raise ErroreCatalogo(f"{etichetta}: quantita deve essere un intero maggiore o uguale a 0")

    return Articolo(**dati)


def valida_catalogo(dati: object) -> Catalogo:
    if not isinstance(dati, list):
        raise ErroreCatalogo("il catalogo deve essere una lista di articoli")
    if not dati:
        raise ErroreCatalogo("il catalogo è vuoto")
    articoli = tuple(_valida_articolo(voce, numero) for numero, voce in enumerate(dati, start=1))
    visti: set[str] = set()
    for numero, voce in enumerate(articoli, start=1):
        if voce.codice in visti:
            raise ErroreCatalogo(f"articolo {numero} ({voce.codice}): codice duplicato")
        visti.add(voce.codice)
    return articoli


def carica_catalogo(percorso: Path = FILE_CATALOGO) -> Catalogo:
    try:
        testo = percorso.read_text(encoding="utf-8-sig")
    except OSError as errore:
        raise ErroreCatalogo(f"impossibile leggere {percorso}: {errore.strerror}") from errore
    try:
        dati = json.loads(testo)
    except json.JSONDecodeError as errore:
        raise ErroreCatalogo(f"{percorso} non è JSON valido: {errore}") from errore
    return valida_catalogo(dati)


def _normalizza(testo: str) -> str:
    """Minuscole e senza accenti, per confronti tolleranti."""
    scomposto = unicodedata.normalize("NFKD", testo)
    return "".join(c for c in scomposto if not unicodedata.combining(c)).casefold()


def _quantita(articolo: Articolo) -> str:
    return f"{articolo.quantita} (esaurito)" if articolo.quantita == 0 else str(articolo.quantita)


def cerca_articoli(catalogo: Catalogo, testo: str = "", categoria: str = "") -> str:
    testo, categoria = testo.strip(), categoria.strip()
    parole = re.findall(r"\w+", _normalizza(testo))
    if not parole and not categoria:
        return "Errore: indica un testo da cercare o una categoria."
    if categoria:
        trovata = next(
            (c for c in CATEGORIE.values() if _normalizza(c) == _normalizza(categoria)), None
        )
        if trovata is None:
            valide = ", ".join(CATEGORIE.values())
            return f'Errore: categoria non valida: "{categoria}". Categorie valide: {valide}.'
    else:
        trovata = None

    risultati = sorted(
        (
            a
            for a in catalogo
            if (trovata is None or a.categoria == trovata)
            and all(
                p in _normalizza(f"{a.nome} {a.descrizione} {a.categoria}") for p in parole
            )
        ),
        key=lambda a: a.codice,
    )
    if not risultati:
        dove = f' nella categoria "{categoria}"' if categoria else ""
        return (
            f'Nessun articolo trovato per "{testo}"{dove}. '
            "Il catalogo non contiene articoli corrispondenti."
        )

    righe = [f"Articoli trovati: {len(risultati)}"]
    righe += [
        f"{a.codice} | {a.nome} | quantità: {_quantita(a)}" for a in risultati[:MAX_RISULTATI]
    ]
    omessi = len(risultati) - MAX_RISULTATI
    if omessi > 0:
        righe.append(f"Altri {omessi} articoli non mostrati: restringi la ricerca.")
    return "\n".join(righe)


def dettaglio_articolo(catalogo: Catalogo, codice: str) -> str:
    # Spazi e trattini ignorati: "sen 004", "SEN004" e " sen-004 " indicano SEN-004.
    cercato = re.sub(r"[\s-]", "", codice).upper()
    articolo = next((a for a in catalogo if a.codice.replace("-", "") == cercato), None)
    if articolo is None:
        return f'Codice non trovato: "{codice.strip()}". Usa cerca_articoli per trovare il codice giusto.'
    return "\n".join(
        [
            f"codice: {articolo.codice}",
            f"nome: {articolo.nome}",
            f"categoria: {articolo.categoria}",
            f"descrizione: {articolo.descrizione}",
            f"quantità: {_quantita(articolo)}",
            f"posizione: {articolo.posizione}",
        ]
    )
