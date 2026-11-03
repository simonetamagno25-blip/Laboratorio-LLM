"""Strumenti che chiamano il servizio HTTP di giorni e scadenze."""

import logging

import httpx
from langchain_core.tools import BaseTool, StructuredTool

log = logging.getLogger(__name__)


def _chiama(base_url: str, percorso: str, parametri: dict, timeout: float) -> str:
    try:
        risposta = httpx.get(f"{base_url}{percorso}", params=parametri, timeout=timeout)
    except httpx.TransportError as errore:
        log.warning("servizio scadenze non raggiungibile: %s", errore)
        return f"Errore: servizio scadenze non raggiungibile su {base_url}"
    try:
        corpo = risposta.json()
    except ValueError:
        return f"Errore: risposta non valida dal servizio scadenze ({risposta.status_code})"
    if risposta.is_success:
        return corpo["risultato"]
    return f"Errore: {corpo.get('errore', risposta.status_code)}"


def _booleano(valore: bool) -> str:
    return "true" if valore else "false"


def crea_strumenti_api(base_url: str, timeout: float = 10.0) -> list[BaseTool]:
    def giorni_tra_date(inizio: str, fine: str, solo_lavorativi: bool = False) -> str:
        parametri = {"inizio": inizio, "fine": fine, "solo_lavorativi": _booleano(solo_lavorativi)}
        return _chiama(base_url, "/giorni", parametri, timeout)

    def calcola_scadenza(inizio: str, giorni: int, solo_lavorativi: bool = False) -> str:
        parametri = {
            "inizio": inizio,
            "giorni": str(giorni),
            "solo_lavorativi": _booleano(solo_lavorativi),
        }
        return _chiama(base_url, "/scadenza", parametri, timeout)

    return [
        StructuredTool.from_function(
            func=giorni_tra_date,
            name="giorni_tra_date",
            description=(
                "Conta i giorni dalla data inizio (esclusa) alla data fine (inclusa). "
                "Date nel formato AAAA-MM-GG. Con solo_lavorativi=true conta solo i giorni "
                "lavorativi, escluse le festività nazionali italiane."
            ),
        ),
        StructuredTool.from_function(
            func=calcola_scadenza,
            name="calcola_scadenza",
            description=(
                "Calcola la data di scadenza aggiungendo un numero di giorni alla data inizio "
                "(formato AAAA-MM-GG). Con solo_lavorativi=true conta solo i giorni lavorativi."
            ),
        ),
    ]
