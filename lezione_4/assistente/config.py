"""Lettura e validazione della configurazione dalle variabili d'ambiente."""

import logging
import os
from collections.abc import Mapping
from dataclasses import dataclass
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


def _obbligatoria(env: Mapping[str, str], nome: str) -> str:
    valore = env.get(nome, "").strip()
    if not valore:
        raise ErroreConfigurazione(f"Variabile d'ambiente obbligatoria mancante o vuota: {nome}")
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

    grezzo = env.get("MAX_PASSAGGI_STRUMENTI", "").strip() or "3"
    try:
        max_passaggi = int(grezzo)
    except ValueError as errore:
        raise ErroreConfigurazione(
            f"MAX_PASSAGGI_STRUMENTI deve essere un intero positivo: {grezzo!r}"
        ) from errore
    if max_passaggi < 1:
        raise ErroreConfigurazione(
            f"MAX_PASSAGGI_STRUMENTI deve essere un intero positivo: {grezzo!r}"
        )

    log_level = (env.get("LOG_LEVEL", "").strip() or "INFO").upper()
    if log_level not in logging.getLevelNamesMapping():
        raise ErroreConfigurazione(f"LOG_LEVEL non valido: {log_level!r}")

    return Configurazione(base_url, modello, fuso, max_passaggi, log_level)
