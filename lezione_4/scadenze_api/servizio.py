"""Servizio HTTP (libreria standard) che espone giorni e scadenze in JSON."""

import json
import logging
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

from scadenze_api.scadenze import ErroreScadenze, calcola_scadenza, giorni_tra_date

log = logging.getLogger(__name__)


class ErroreRichiesta(ValueError):
    """Parametri della richiesta mancanti o non validi."""


def _parametri(query: str, obbligatori: set[str], facoltativi: set[str]) -> dict[str, str]:
    grezzi = parse_qs(query, keep_blank_values=True)
    sconosciuti = set(grezzi) - obbligatori - facoltativi
    if sconosciuti:
        raise ErroreRichiesta(f"parametri sconosciuti: {', '.join(sorted(sconosciuti))}")
    mancanti = obbligatori - set(grezzi)
    if mancanti:
        raise ErroreRichiesta(f"parametri mancanti: {', '.join(sorted(mancanti))}")
    ripetuti = [nome for nome, valori in grezzi.items() if len(valori) > 1]
    if ripetuti:
        raise ErroreRichiesta(f"parametri ripetuti: {', '.join(sorted(ripetuti))}")
    return {nome: valori[0] for nome, valori in grezzi.items()}


def _booleano(valore: str) -> bool:
    if valore not in ("true", "false"):
        raise ErroreRichiesta(f"solo_lavorativi deve essere true o false: {valore!r}")
    return valore == "true"


def _intero(valore: str) -> int:
    # Solo cifre ASCII e lunghezza limitata: int() rifiuterebbe altrimenti con errori interni.
    if not re.fullmatch(r"-?[0-9]{1,6}", valore):
        raise ErroreRichiesta(f"giorni deve essere un numero intero: {valore[:20]!r}")
    return int(valore)


def _giorni(query: str) -> str:
    p = _parametri(query, {"inizio", "fine"}, {"solo_lavorativi"})
    return giorni_tra_date(p["inizio"], p["fine"], _booleano(p.get("solo_lavorativi", "false")))


def _scadenza(query: str) -> str:
    p = _parametri(query, {"inizio", "giorni"}, {"solo_lavorativi"})
    return calcola_scadenza(
        p["inizio"], _intero(p["giorni"]), _booleano(p.get("solo_lavorativi", "false"))
    )


_PERCORSI = {"/giorni": _giorni, "/scadenza": _scadenza}


class GestoreScadenze(BaseHTTPRequestHandler):
    def _rispondi(self, codice: int, corpo: dict) -> None:
        dati = json.dumps(corpo, ensure_ascii=False).encode("utf-8")
        self.send_response(codice)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(dati)))
        self.end_headers()
        self.wfile.write(dati)

    def do_GET(self) -> None:
        parti = urlsplit(self.path)
        if parti.path == "/salute":
            self._rispondi(200, {"stato": "ok"})
            return
        gestore = _PERCORSI.get(parti.path)
        if gestore is None:
            self._rispondi(404, {"errore": f"percorso sconosciuto: {parti.path}"})
            return
        try:
            self._rispondi(200, {"risultato": gestore(parti.query)})
        except (ErroreRichiesta, ErroreScadenze) as errore:
            self._rispondi(400, {"errore": str(errore)})
        except Exception:
            log.exception("errore interno su %s", self.path)
            self._rispondi(500, {"errore": "errore interno"})

    def _non_consentito(self) -> None:
        self._rispondi(405, {"errore": f"metodo non consentito: {self.command}"})

    do_POST = do_PUT = do_DELETE = do_PATCH = _non_consentito

    def log_message(self, formato: str, *args) -> None:
        log.info("%s %s", self.address_string(), formato % args)


def crea_server(host: str, porta: int) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, porta), GestoreScadenze)
