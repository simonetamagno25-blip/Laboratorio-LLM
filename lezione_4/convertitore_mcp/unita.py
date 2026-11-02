"""Conversione tra unità di misura ammesse come elenco chiuso."""

import math
from typing import Literal, get_args

Unita = Literal[
    "mm", "cm", "m", "km", "in", "ft", "mi",
    "g", "kg", "t", "oz", "lb",
    "C", "F", "K",
    "ml", "l",
    "s", "min", "h", "d",
]

# Simbolo -> (grandezza, fattore verso l'unità base della grandezza).
# La temperatura non ha un fattore: si converte passando per i kelvin.
_TABELLA: dict[str, tuple[str, float | None]] = {
    "mm": ("lunghezza", 0.001),
    "cm": ("lunghezza", 0.01),
    "m": ("lunghezza", 1.0),
    "km": ("lunghezza", 1000.0),
    "in": ("lunghezza", 0.0254),
    "ft": ("lunghezza", 0.3048),
    "mi": ("lunghezza", 1609.344),
    "g": ("massa", 0.001),
    "kg": ("massa", 1.0),
    "t": ("massa", 1000.0),
    "oz": ("massa", 0.028349523125),
    "lb": ("massa", 0.45359237),
    "C": ("temperatura", None),
    "F": ("temperatura", None),
    "K": ("temperatura", None),
    "ml": ("volume", 0.001),
    "l": ("volume", 1.0),
    "s": ("tempo", 1.0),
    "min": ("tempo", 60.0),
    "h": ("tempo", 3600.0),
    "d": ("tempo", 86400.0),
}

GRANDEZZE = {simbolo: grandezza for simbolo, (grandezza, _) in _TABELLA.items()}


class ErroreConversione(ValueError):
    """Conversione non ammessa."""


def _in_kelvin(valore: float, unita: str) -> float:
    if unita == "C":
        return valore + 273.15
    if unita == "F":
        return (valore - 32) * 5 / 9 + 273.15
    return valore


def _da_kelvin(kelvin: float, unita: str) -> float:
    if unita == "C":
        return kelvin - 273.15
    if unita == "F":
        return (kelvin - 273.15) * 9 / 5 + 32
    return kelvin


def converti(valore: float, da: str, a: str) -> float:
    for unita in (da, a):
        if unita not in _TABELLA:
            ammesse = ", ".join(get_args(Unita))
            raise ErroreConversione(f"unità non ammessa: {unita!r} (ammesse: {ammesse})")
    if not math.isfinite(valore):
        raise ErroreConversione(f"valore non finito: {valore}")
    grandezza_da, fattore_da = _TABELLA[da]
    grandezza_a, fattore_a = _TABELLA[a]
    if grandezza_da != grandezza_a:
        raise ErroreConversione(
            f"{da} → {a}: grandezze incompatibili ({grandezza_da}, {grandezza_a})"
        )
    if grandezza_da == "temperatura":
        kelvin = _in_kelvin(valore, da)
        # Tolleranza per gli arrotondamenti di -273.15 C e -459.67 F.
        if kelvin < -1e-9:
            raise ErroreConversione(f"{valore} {da} è sotto lo zero assoluto")
        risultato = _da_kelvin(max(kelvin, 0.0), a)
    else:
        risultato = valore * fattore_da / fattore_a
    if not math.isfinite(risultato):
        raise ErroreConversione(f"risultato non finito convertendo {valore:g} {da} in {a}")
    return risultato


def descrivi_conversione(valore: float, da: str, a: str) -> str:
    try:
        risultato = converti(valore, da, a)
    except ErroreConversione as errore:
        return f"Errore: {errore}"
    return f"{valore:.6g} {da} = {risultato:.6g} {a}"
