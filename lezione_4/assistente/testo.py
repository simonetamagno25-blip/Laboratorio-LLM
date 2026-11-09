"""Normalizzazione del testo per ricerche tolleranti, condivisa da catalogo e note."""

import re
import unicodedata


def normalizza(testo: str) -> str:
    """Minuscole e senza accenti, per confronti tolleranti."""
    scomposto = unicodedata.normalize("NFKD", testo)
    return "".join(c for c in scomposto if not unicodedata.combining(c)).casefold()


def parole(testo: str) -> list[str]:
    """Parole normalizzate del testo, senza punteggiatura."""
    return re.findall(r"\w+", normalizza(testo))
