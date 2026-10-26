"""Strumenti richiamabili dal modello tramite tool calling."""

from collections.abc import Callable
from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from langchain_core.tools import BaseTool, StructuredTool

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


def crea_strumenti(adesso: Orologio = adesso_utc) -> list[BaseTool]:
    def ora_corrente(fuso_orario: str) -> str:
        return formatta_ora(fuso_orario, adesso)

    strumento = StructuredTool.from_function(
        func=ora_corrente,
        name="ora_corrente",
        description=(
            "Restituisce la data e l'ora correnti nel fuso orario indicato. "
            "Passa un nome IANA del fuso, per esempio Europe/Rome."
        ),
    )
    return [strumento]
