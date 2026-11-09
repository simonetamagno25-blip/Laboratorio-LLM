"""Strumenti richiamabili dal modello tramite tool calling."""

from collections.abc import Callable
from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from langchain_core.tools import BaseTool, StructuredTool

from assistente.calcolatrice import calcola
from assistente.catalogo import Catalogo, carica_catalogo, cerca_articoli, dettaglio_articolo
from assistente.note import ArchivioNote, aggiungi_nota, cerca_note, elenca_note, elimina_nota

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
    adesso: Orologio = adesso_utc,
    catalogo: Catalogo | None = None,
    archivio: ArchivioNote | None = None,
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
    strumenti = [strumento, calcolatrice, ricerca, scheda]
    if archivio is not None:
        strumenti += _strumenti_note(archivio)
    return strumenti


def _strumenti_note(archivio: ArchivioNote) -> list[BaseTool]:
    def aggiungi(testo: str) -> str:
        return aggiungi_nota(archivio, testo)

    def elenca() -> str:
        return elenca_note(archivio)

    def cerca(testo: str) -> str:
        return cerca_note(archivio, testo)

    def elimina(numero: int) -> str:
        return elimina_nota(archivio, numero)

    return [
        StructuredTool.from_function(
            func=aggiungi,
            name="aggiungi_nota",
            description=(
                "Salva una nota personale dell'utente, che resta disponibile anche nelle "
                "sessioni successive. Riporta il testo come l'utente l'ha detto."
            ),
        ),
        StructuredTool.from_function(
            func=elenca,
            name="elenca_note",
            description="Elenca le note salvate dall'utente.",
        ),
        StructuredTool.from_function(
            func=cerca,
            name="cerca_note",
            description=(
                "Cerca tra le note salvate quelle che contengono tutte le parole indicate. "
                "Usa una o due parole chiave brevi, al singolare."
            ),
        ),
        StructuredTool.from_function(
            func=elimina,
            name="elimina_nota",
            description=(
                "Elimina una nota dato il suo numero. Se non conosci il numero usa prima "
                "cerca_note o elenca_note. Il programma chiederà conferma all'utente "
                "prima di eliminare."
            ),
        ),
    ]
