"""Note personali dell'utente su un archivio SQLite che sopravvive alla sessione."""

import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from assistente.testo import normalizza, parole

MAX_CARATTERI = 500
MAX_RISULTATI = 20

_SCHEMA = """
CREATE TABLE IF NOT EXISTS note (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    testo TEXT NOT NULL,
    creata TEXT NOT NULL
)
"""


class ErroreArchivio(Exception):
    """Archivio delle note non apribile."""


@dataclass(frozen=True)
class Nota:
    numero: int
    testo: str
    creata: datetime


def _adesso_utc() -> datetime:
    return datetime.now(timezone.utc)


class ArchivioNote:
    def __init__(
        self, connessione: sqlite3.Connection, fuso: str, adesso: Callable[[], datetime]
    ):
        self._conn = connessione
        self._fuso = ZoneInfo(fuso)
        self._adesso = adesso

    def aggiungi(self, testo: str) -> Nota:
        creata = self._adesso().astimezone(self._fuso).replace(microsecond=0)
        with self._conn:
            cursore = self._conn.execute(
                "INSERT INTO note (testo, creata) VALUES (?, ?)", (testo, creata.isoformat())
            )
        return Nota(cursore.lastrowid, testo, creata)

    def tutte(self) -> list[Nota]:
        righe = self._conn.execute("SELECT id, testo, creata FROM note ORDER BY id").fetchall()
        return [_nota(riga) for riga in righe]

    def leggi(self, numero: int) -> Nota | None:
        riga = self._conn.execute(
            "SELECT id, testo, creata FROM note WHERE id = ?", (numero,)
        ).fetchone()
        return None if riga is None else _nota(riga)

    def elimina(self, numero: int) -> bool:
        with self._conn:
            cursore = self._conn.execute("DELETE FROM note WHERE id = ?", (numero,))
        return cursore.rowcount > 0

    def chiudi(self) -> None:
        self._conn.close()


def _nota(riga: tuple) -> Nota:
    return Nota(riga[0], riga[1], datetime.fromisoformat(riga[2]))


def apri_archivio(
    percorso: str | Path,
    fuso: str = "Europe/Rome",
    adesso: Callable[[], datetime] = _adesso_utc,
) -> ArchivioNote:
    try:
        if str(percorso) != ":memory:":
            Path(percorso).parent.mkdir(parents=True, exist_ok=True)
        # Una sola connessione: LangGraph può eseguire i nodi in un altro thread.
        connessione = sqlite3.connect(percorso, check_same_thread=False)
    except (OSError, sqlite3.Error) as errore:
        raise ErroreArchivio(f"{percorso}: {errore}") from errore
    try:
        with connessione:
            connessione.execute(_SCHEMA)
            # Una scrittura vera: su un file in sola lettura CREATE TABLE IF NOT EXISTS non scrive.
            connessione.execute("PRAGMA user_version = 1")
    except sqlite3.Error as errore:
        connessione.close()
        raise ErroreArchivio(f"{percorso}: {errore}") from errore
    return ArchivioNote(connessione, fuso, adesso)


def formatta_nota(nota: Nota) -> str:
    return f"Nota {nota.numero} ({nota.creata:%Y-%m-%d %H:%M}): {nota.testo}"


def _elenco(intestazione: str, note: list[Nota]) -> str:
    righe = [f"{intestazione}: {len(note)}"]
    righe += [formatta_nota(n) for n in note[-MAX_RISULTATI:]]
    omesse = len(note) - MAX_RISULTATI
    if omesse > 0:
        righe.append(f"Altre {omesse} note non mostrate: usa cerca_note con parole più precise.")
    return "\n".join(righe)


def aggiungi_nota(archivio: ArchivioNote, testo: str) -> str:
    testo = testo.strip()
    if not testo:
        return "Errore: il testo della nota è vuoto."
    if len(testo) > MAX_CARATTERI:
        return f"Errore: la nota supera i {MAX_CARATTERI} caratteri."
    nota = archivio.aggiungi(testo)
    return f"Nota {nota.numero} salvata: {nota.testo}"


def elenca_note(archivio: ArchivioNote) -> str:
    note = archivio.tutte()
    if not note:
        return "Non ci sono note salvate."
    return _elenco("Note salvate", note)


def cerca_note(archivio: ArchivioNote, testo: str) -> str:
    cercate = parole(testo)
    if not cercate:
        return (
            "Errore: indica una o più parole da cercare; "
            "per vedere tutte le note usa elenca_note."
        )
    trovate = [
        n for n in archivio.tutte() if all(p in normalizza(n.testo) for p in cercate)
    ]
    if not trovate:
        return f'Nessuna nota trovata per "{testo.strip()}". Non ci sono note corrispondenti.'
    return _elenco("Note trovate", trovate)


def elimina_nota(archivio: ArchivioNote, numero: int) -> str:
    if archivio.elimina(numero):
        return f"Nota {numero} eliminata."
    return f"Nota {numero} non trovata. Usa cerca_note o elenca_note per trovare il numero giusto."
