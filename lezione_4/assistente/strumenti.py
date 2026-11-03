"""Strumenti richiamabili dal modello tramite tool calling."""

from collections.abc import Callable
from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from langchain_core.tools import BaseTool, StructuredTool

from assistente.calcolatrice import calcola
from assistente.catalogo import Catalogo, carica_catalogo, cerca_articoli, dettaglio_articolo

Orologio = Callable[[], datetime]


def adesso_utc() -> datetime:
    return datetime.now(timezone.utc)


def formatta_ora(fuso_orario: str, adesso: Orologio) -> str:
    try:
        fuso = ZoneInfo(fuso_orario)
    except (ZoneInfoNotFoundError, ValueError):
        return f"Fuso orario non valido: {fuso_orario!r}"
    locale = adesso().astimezone(fuso)
    return f"{locale.isoformat(timespec='seconds')} ({fuso_orario})"


def crea_strumenti(
    adesso: Orologio = adesso_utc, catalogo: Catalogo | None = None
) -> list[BaseTool]:
    if catalogo is None:
        catalogo = carica_catalogo()

    def ora_corrente(fuso_orario: str) -> str:
        return formatta_ora(fuso_orario, adesso)

    def cerca(testo: str = "", categoria: str = "") -> str:
        return cerca_articoli(catalogo, testo, categoria)

    def dettaglio(codice: str) -> str:
        return dettaglio_articolo(catalogo, codice)

    strumento = StructuredTool.from_function(
        func=ora_corrente,
        name="ora_corrente",
        description=(
            "Restituisce la data e l'ora correnti nel fuso orario indicato. "
            "Passa un nome IANA del fuso, per esempio Europe/Rome."
        ),
    )
    calcolatrice = StructuredTool.from_function(
        func=calcola,
        name="calcola",
        description=(
            "Calcola un'espressione aritmetica e restituisce il risultato esatto. "
            "Ammessi solo numeri, + - * / % ** e parentesi, per esempio (12 + 8) * 3 / 4. "
            "Usalo sempre per i calcoli invece di farli a mente."
        ),
    )
    ricerca = StructuredTool.from_function(
        func=cerca,
        name="cerca_articoli",
        description=(
            "Cerca nel catalogo del materiale del laboratorio per parole chiave e/o categoria. "
            "Usa una o due parole chiave brevi, al singolare (per esempio temperatura, cavo). "
            "Categorie: schede, sensori, attuatori, cavi, alimentazione, strumenti di misura. "
            "Restituisce codice, nome e quantità; per descrizione e posizione usa "
            "dettaglio_articolo."
        ),
    )
    scheda = StructuredTool.from_function(
        func=dettaglio,
        name="dettaglio_articolo",
        description=(
            "Restituisce la scheda completa di un articolo del catalogo dato il suo codice, "
            "per esempio SEN-004, con descrizione, quantità e posizione. "
            "Se non conosci il codice usa prima cerca_articoli."
        ),
    )
    return [strumento, calcolatrice, ricerca, scheda]
