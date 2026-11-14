"""Lettura e validazione della configurazione dalle variabili d'ambiente."""

import logging
import os
from collections.abc import Mapping
from dataclasses import dataclass
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


class ErroreConfigurazione(ValueError):
    """Configurazione mancante o non valida."""


@dataclass(frozen=True)
class Configurazione:
    base_url: str
    modello: str
    fuso_predefinito: str
    max_passaggi_strumenti: int
    log_level: str
    scadenze_api_url: str
    percorso_db_note: str
    ambito: str
    max_revisioni: int = 2


def _obbligatoria(env: Mapping[str, str], nome: str) -> str:
    valore = env.get(nome, "").strip()
    if not valore:
        raise ErroreConfigurazione(f"Variabile d'ambiente obbligatoria mancante o vuota: {nome}")
    return valore


def _intero_positivo(env: Mapping[str, str], nome: str, predefinito: str) -> int:
    grezzo = env.get(nome, "").strip() or predefinito
    try:
        valore = int(grezzo)
    except ValueError as errore:
        raise ErroreConfigurazione(f"{nome} deve essere un intero positivo: {grezzo!r}") from errore
    if valore < 1:
        raise ErroreConfigurazione(f"{nome} deve essere un intero positivo: {grezzo!r}")
    return valore


def carica_configurazione(env: Mapping[str, str] | None = None) -> Configurazione:
    if env is None:
        env = os.environ

    base_url = _obbligatoria(env, "LMSTUDIO_BASE_URL")
    modello = _obbligatoria(env, "LMSTUDIO_MODEL")

    fuso = env.get("FUSO_ORARIO_PREDEFINITO", "").strip() or "Europe/Rome"
    try:
        ZoneInfo(fuso)
    except (ZoneInfoNotFoundError, ValueError) as errore:
        raise ErroreConfigurazione(
            f"FUSO_ORARIO_PREDEFINITO non valido: {fuso!r}"
        ) from errore

    max_passaggi = _intero_positivo(env, "MAX_PASSAGGI_STRUMENTI", "3")

    log_level = (env.get("LOG_LEVEL", "").strip() or "INFO").upper()
    if log_level not in logging.getLevelNamesMapping():
        raise ErroreConfigurazione(f"LOG_LEVEL non valido: {log_level!r}")

    scadenze_api_url = _obbligatoria(env, "SCADENZE_API_URL").rstrip("/")
    parti = urlsplit(scadenze_api_url)
    if parti.scheme not in ("http", "https") or not parti.netloc:
        raise ErroreConfigurazione(f"SCADENZE_API_URL non valido: {scadenze_api_url!r}")

    percorso_db_note = env.get("PERCORSO_DB_NOTE", "").strip() or "note.sqlite3"

    ambito = _obbligatoria(env, "AMBITO_AGENTE")
    max_revisioni = _intero_positivo(env, "MAX_REVISIONI", "2")

    return Configurazione(
        base_url,
        modello,
        fuso,
        max_passaggi,
        log_level,
        scadenze_api_url,
        percorso_db_note,
        ambito,
        max_revisioni,
    )
