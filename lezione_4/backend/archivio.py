"""Archivio delle chat: PostgreSQL in produzione, in memoria per i test dell'API.

Le due implementazioni hanno la stessa interfaccia e superano gli stessi test di contratto.
"""

import logging
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone

log = logging.getLogger(__name__)

TITOLO_INIZIALE = "Nuova chat"
LUNGHEZZA_TITOLO = 60


class ErroreDatabase(RuntimeError):
    """Database non raggiungibile."""


@dataclass(frozen=True)
class Chat:
    id: int
    titolo: str
    creata: datetime
    ultimo_messaggio: datetime | None


@dataclass(frozen=True)
class Messaggio:
    ruolo: str  # "utente" | "assistente"
    testo: str
    strumenti: list[dict]
    creato: datetime


@dataclass(frozen=True)
class StatoAgente:
    """Quello che il back-end conserva per l'agente senza stato."""

    cronologia: list[dict]
    riassunto: str
    id_conferma: str | None


def titolo_da(domanda: str) -> str:
    parole = " ".join(domanda.split())
    if len(parole) <= LUNGHEZZA_TITOLO:
        return parole
    return parole[: LUNGHEZZA_TITOLO - 1].rsplit(" ", 1)[0] + "…"


class ArchivioMemoria:
    def __init__(self):
        self._chat: dict[int, dict] = {}
        self._prossimo = 1
        self._lucchetto = threading.Lock()

    def crea(self) -> Chat:
        with self._lucchetto:
            id_chat, self._prossimo = self._prossimo, self._prossimo + 1
            self._chat[id_chat] = {
                "titolo": TITOLO_INIZIALE,
                "creata": datetime.now(timezone.utc),
                "messaggi": [],
                "stato": StatoAgente([], "", None),
            }
        return self._vista(id_chat)

    def _vista(self, id_chat: int) -> Chat:
        dati = self._chat[id_chat]
        ultimo = dati["messaggi"][-1].creato if dati["messaggi"] else None
        return Chat(id_chat, dati["titolo"], dati["creata"], ultimo)

    def elenca(self) -> list[Chat]:
        with self._lucchetto:
            chat = [self._vista(i) for i in self._chat]
        return sorted(chat, key=lambda c: c.ultimo_messaggio or c.creata, reverse=True)

    def leggi(self, id_chat: int) -> tuple[Chat, list[Messaggio]] | None:
        with self._lucchetto:
            if id_chat not in self._chat:
                return None
            return self._vista(id_chat), list(self._chat[id_chat]["messaggi"])

    def stato_agente(self, id_chat: int) -> StatoAgente | None:
        with self._lucchetto:
            dati = self._chat.get(id_chat)
            return dati["stato"] if dati else None

    def salva_scambio(
        self,
        id_chat: int,
        *,
        domanda: str | None,
        risposta: str | None,
        strumenti: list[dict],
        stato: StatoAgente,
    ) -> None:
        with self._lucchetto:
            dati = self._chat[id_chat]
            adesso = datetime.now(timezone.utc)
            if domanda is not None:
                dati["messaggi"].append(Messaggio("utente", domanda, [], adesso))
                if dati["titolo"] == TITOLO_INIZIALE:
                    dati["titolo"] = titolo_da(domanda)
            if risposta is not None:
                dati["messaggi"].append(Messaggio("assistente", risposta, strumenti, adesso))
            dati["stato"] = stato

    def elimina(self, id_chat: int) -> bool:
        with self._lucchetto:
            return self._chat.pop(id_chat, None) is not None

    def controlla(self) -> None:
        return None


SCHEMA = """
CREATE TABLE IF NOT EXISTS chat (
    id BIGSERIAL PRIMARY KEY,
    titolo TEXT NOT NULL,
    creata TIMESTAMPTZ NOT NULL DEFAULT now(),
    cronologia_agente JSONB NOT NULL DEFAULT '[]',
    riassunto TEXT NOT NULL DEFAULT '',
    id_conferma TEXT
);
CREATE TABLE IF NOT EXISTS messaggio (
    id BIGSERIAL PRIMARY KEY,
    chat_id BIGINT NOT NULL REFERENCES chat(id) ON DELETE CASCADE,
    ruolo TEXT NOT NULL CHECK (ruolo IN ('utente', 'assistente')),
    testo TEXT NOT NULL,
    strumenti JSONB NOT NULL DEFAULT '[]',
    creato TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);
CREATE INDEX IF NOT EXISTS messaggio_chat ON messaggio (chat_id, id);
"""

_ELENCO = """
SELECT c.id, c.titolo, c.creata, max(m.creato)
FROM chat c LEFT JOIN messaggio m ON m.chat_id = c.id
GROUP BY c.id
ORDER BY coalesce(max(m.creato), c.creata) DESC, c.id DESC
"""


class ArchivioPostgres:
    """Una connessione per operazione: semplice e sufficiente per il laboratorio."""

    def __init__(self, url: str):
        self._url = url

    def _connetti(self):
        import psycopg

        try:
            return psycopg.connect(self._url, connect_timeout=5)
        except psycopg.OperationalError as errore:
            raise ErroreDatabase(f"database non raggiungibile: {errore}") from errore

    def prepara(self, attesa: float = 30.0) -> None:
        """Aspetta il database (fino a `attesa` secondi) e crea lo schema se manca."""
        scadenza = time.monotonic() + attesa
        while True:
            try:
                with self._connetti() as conn:
                    conn.execute(SCHEMA)
                log.info("database pronto, schema verificato")
                return
            except ErroreDatabase as errore:
                if time.monotonic() >= scadenza:
                    raise
                log.info("database non ancora pronto (%s), riprovo", errore)
                time.sleep(1)

    def controlla(self) -> None:
        with self._connetti() as conn:
            conn.execute("SELECT 1")

    def crea(self) -> Chat:
        with self._connetti() as conn:
            riga = conn.execute(
                "INSERT INTO chat (titolo) VALUES (%s) RETURNING id, titolo, creata",
                (TITOLO_INIZIALE,),
            ).fetchone()
        return Chat(riga[0], riga[1], riga[2], None)

    def elenca(self) -> list[Chat]:
        with self._connetti() as conn:
            return [Chat(*riga) for riga in conn.execute(_ELENCO).fetchall()]

    def leggi(self, id_chat: int) -> tuple[Chat, list[Messaggio]] | None:
        with self._connetti() as conn:
            chat = conn.execute(
                "SELECT c.id, c.titolo, c.creata, max(m.creato) FROM chat c "
                "LEFT JOIN messaggio m ON m.chat_id = c.id WHERE c.id = %s GROUP BY c.id",
                (id_chat,),
            ).fetchone()
            if chat is None:
                return None
            messaggi = conn.execute(
                "SELECT ruolo, testo, strumenti, creato FROM messaggio "
                "WHERE chat_id = %s ORDER BY id",
                (id_chat,),
            ).fetchall()
        return Chat(*chat), [Messaggio(*m) for m in messaggi]

    def stato_agente(self, id_chat: int) -> StatoAgente | None:
        with self._connetti() as conn:
            riga = conn.execute(
                "SELECT cronologia_agente, riassunto, id_conferma FROM chat WHERE id = %s",
                (id_chat,),
            ).fetchone()
        return StatoAgente(*riga) if riga else None

    def salva_scambio(
        self,
        id_chat: int,
        *,
        domanda: str | None,
        risposta: str | None,
        strumenti: list[dict],
        stato: StatoAgente,
    ) -> None:
        from psycopg.types.json import Jsonb

        # Una sola transazione: domanda, risposta e stato dell'agente insieme, o niente.
        with self._connetti() as conn, conn.transaction():
            if domanda is not None:
                conn.execute(
                    "INSERT INTO messaggio (chat_id, ruolo, testo) VALUES (%s, 'utente', %s)",
                    (id_chat, domanda),
                )
                conn.execute(
                    "UPDATE chat SET titolo = %s WHERE id = %s AND titolo = %s",
                    (titolo_da(domanda), id_chat, TITOLO_INIZIALE),
                )
            if risposta is not None:
                conn.execute(
                    "INSERT INTO messaggio (chat_id, ruolo, testo, strumenti) "
                    "VALUES (%s, 'assistente', %s, %s)",
                    (id_chat, risposta, Jsonb(strumenti)),
                )
            conn.execute(
                "UPDATE chat SET cronologia_agente = %s, riassunto = %s, id_conferma = %s "
                "WHERE id = %s",
                (Jsonb(stato.cronologia), stato.riassunto, stato.id_conferma, id_chat),
            )

    def elimina(self, id_chat: int) -> bool:
        with self._connetti() as conn:
            return conn.execute("DELETE FROM chat WHERE id = %s", (id_chat,)).rowcount > 0
