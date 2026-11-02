"""Giorni tra date e scadenze, con le festività nazionali lette da un file locale."""

import json
import re
from datetime import date, timedelta
from functools import cache
from pathlib import Path

AVVERTENZA = "(Risultato indicativo, non ha valore normativo.)"
GIORNI_MASSIMI = 3650
FILE_FESTIVITA = Path(__file__).parent / "dati" / "festivita_it.json"
NOMI_GIORNI = ("lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica")

Festivita = dict[int, dict[date, str]]

_FORMATO_ISO = re.compile(r"\d{4}-\d{2}-\d{2}")


class ErroreScadenze(ValueError):
    """Input non valido per il calcolo di giorni e scadenze."""


def leggi_data(testo: str) -> date:
    if not _FORMATO_ISO.fullmatch(testo):
        raise ErroreScadenze(f"data non nel formato AAAA-MM-GG: {testo!r}")
    try:
        return date.fromisoformat(testo)
    except ValueError:
        raise ErroreScadenze(f"data inesistente: {testo!r}") from None


@cache
def _festivita_predefinite() -> Festivita:
    return carica_festivita(FILE_FESTIVITA)


def carica_festivita(percorso: Path | None = None) -> Festivita:
    if percorso is None:
        return _festivita_predefinite()
    dati = json.loads(percorso.read_text(encoding="utf-8"))
    return {
        int(anno): {date.fromisoformat(giorno): nome for giorno, nome in giorni.items()}
        for anno, giorni in dati["anni"].items()
    }


def _lavorativo(giorno: date, festivita: Festivita) -> bool:
    if giorno.year not in festivita:
        coperti = ", ".join(str(anno) for anno in sorted(festivita))
        raise ErroreScadenze(
            f"festività non disponibili per il {giorno.year} (anni coperti: {coperti})"
        )
    return giorno.weekday() < 5 and giorno not in festivita[giorno.year]


def giorni_tra_date(
    inizio: str, fine: str, solo_lavorativi: bool = False, festivita: Festivita | None = None
) -> str:
    da, a = leggi_data(inizio), leggi_data(fine)
    differenza = (a - da).days
    if abs(differenza) > GIORNI_MASSIMI:
        raise ErroreScadenze(f"intervallo oltre il limite di {GIORNI_MASSIMI} giorni")
    tipo = "giorni"
    if solo_lavorativi:
        festivita = festivita or carica_festivita()
        primo, ultimo = sorted((da, a))
        conteggio = sum(
            _lavorativo(primo + timedelta(days=i), festivita)
            for i in range(1, (ultimo - primo).days + 1)
        )
        differenza = conteggio if a >= da else -conteggio
        tipo = "giorni lavorativi"
    return f"{differenza} {tipo} dal {inizio} (escluso) al {fine} (incluso). {AVVERTENZA}"


def calcola_scadenza(
    inizio: str, giorni: int, solo_lavorativi: bool = False, festivita: Festivita | None = None
) -> str:
    da = leggi_data(inizio)
    if not 0 <= giorni <= GIORNI_MASSIMI:
        raise ErroreScadenze(f"i giorni devono essere tra 0 e {GIORNI_MASSIMI}: {giorni}")
    festivita = festivita or carica_festivita()
    if solo_lavorativi:
        scadenza, contati = da, 0
        while contati < giorni:
            scadenza += timedelta(days=1)
            contati += _lavorativo(scadenza, festivita)
    else:
        scadenza = da + timedelta(days=giorni)

    nome_giorno = NOMI_GIORNI[scadenza.weekday()]
    testo = f"Scadenza: {scadenza.isoformat()} ({nome_giorno})"
    if scadenza.weekday() >= 5:
        testo += f", cade di {nome_giorno}"
    nome_festa = festivita.get(scadenza.year, {}).get(scadenza)
    if nome_festa:
        testo += f", festività: {nome_festa}"
    return f"{testo}. {AVVERTENZA}"
