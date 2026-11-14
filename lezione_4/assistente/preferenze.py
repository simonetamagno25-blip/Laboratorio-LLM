"""Preferenze dell'utente lette dalla resource MCP utente://preferenze a inizio sessione."""

import json
import logging
from dataclasses import dataclass, replace
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from assistente.client_mcp import ErroreMCP

log = logging.getLogger(__name__)

URI_PREFERENZE = "utente://preferenze"
STILI = ("sintetico", "dettagliato")


@dataclass(frozen=True)
class Preferenze:
    lingua: str
    fuso_orario: str
    stile: str


def predefinite(fuso_predefinito: str) -> Preferenze:
    """Valori usati quando la resource manca: lo stesso comportamento di prima dello step 4."""
    return Preferenze(lingua="italiano", fuso_orario=fuso_predefinito, stile="sintetico")


def _lingua(valore) -> str | None:
    return valore.strip() if isinstance(valore, str) and valore.strip() else None


def _fuso(valore) -> str | None:
    if not isinstance(valore, str) or not valore.strip():
        return None
    try:
        ZoneInfo(valore.strip())
    except (ZoneInfoNotFoundError, ValueError):
        return None
    return valore.strip()


def _stile(valore) -> str | None:
    if isinstance(valore, str) and valore.strip().casefold() in STILI:
        return valore.strip().casefold()
    return None


def interpreta(testo: str, base: Preferenze) -> Preferenze:
    """JSON della resource → Preferenze. Ogni campo mancante o non valido prende il valore di
    `base`, con un WARNING: un errore in un campo non fa perdere gli altri."""
    try:
        dati = json.loads(testo)
    except json.JSONDecodeError:
        dati = None
    if not isinstance(dati, dict):
        log.warning("preferenze: contenuto non valido (serve un oggetto JSON), uso i predefiniti")
        return base
    valori = {}
    for campo, controlla in (("lingua", _lingua), ("fuso_orario", _fuso), ("stile", _stile)):
        if campo not in dati:
            log.warning("preferenze: %s mancante, uso %r", campo, getattr(base, campo))
            continue
        valore = controlla(dati[campo])
        if valore is None:
            log.warning(
                "preferenze: %s non valido (%r), uso %r", campo, dati[campo], getattr(base, campo)
            )
            continue
        valori[campo] = valore
    return replace(base, **valori)


def carica_preferenze(client, base: Preferenze) -> Preferenze:
    """Legge la resource una volta, a inizio sessione. Se non è disponibile usa `base`."""
    try:
        testo = client.leggi_risorsa(URI_PREFERENZE)
    except ErroreMCP as errore:
        log.warning(
            "preferenze: resource %s non disponibile (%s), uso i valori predefiniti",
            URI_PREFERENZE,
            errore,
        )
        preferenze = base
    else:
        preferenze = interpreta(testo, base)
    log.info(
        "preferenze: lingua=%s fuso_orario=%s stile=%s",
        preferenze.lingua,
        preferenze.fuso_orario,
        preferenze.stile,
    )
    return preferenze


def blocco_preferenze(p: Preferenze) -> str:
    """Blocco da mettere in cima al prompt di sistema."""
    stile = (
        "sintetico: risposte brevi, solo l'essenziale"
        if p.stile == "sintetico"
        else "dettagliato: risposte complete, con spiegazioni ed esempi"
    )
    return (
        "Preferenze dell'utente (valgono per tutta la conversazione):\n"
        f"- lingua delle risposte: {p.lingua};\n"
        f"- fuso orario predefinito: {p.fuso_orario};\n"
        f"- stile: {stile}."
    )
